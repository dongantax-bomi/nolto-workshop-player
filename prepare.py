"""100곡 데이터 준비. Python 3.10+, 선택: YOUTUBE_API_KEY 또는 yt-dlp."""
import argparse, concurrent.futures, csv, difflib, hashlib, json, os, re, subprocess, sys, time,unicodedata
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / '.cache'
ALIASES = json.loads((ROOT/'aliases.json').read_text(encoding='utf-8'))

def names(song):
    return ALIASES['artists'].get(song['artist'],song['artist']), ALIASES['titles'].get(str(song['id']), re.sub(r'\s*\([^)]*\)', '',song['title']).strip())

def request(url, params=None):
    if params: url += '?' + urlencode(params)
    CACHE.mkdir(exist_ok=True)
    path = CACHE / (hashlib.sha256(url.encode()).hexdigest() + '.json')
    if path.exists(): return json.loads(path.read_text(encoding='utf-8'))
    error = None
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'WorkshopDictation/1.0'}), timeout=20) as r:
                data = json.load(r)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            return data
        except Exception as exc:
            error = exc
            time.sleep(attempt + 1)
    raise RuntimeError(str(error))

def norm(s): return re.sub(r'[^a-z0-9가-힣]', '', unicodedata.normalize('NFKC',s).lower().replace('₩','w'))

def parse_lrc(text):
    lines = []
    for line in text.splitlines():
        stamps = re.findall(r'\[(\d+):(\d+(?:\.\d+)?)\]', line)
        lyric = re.sub(r'\[[^]]*\]', '', line).strip()
        for m, s in stamps:
            lines.append((int(m)*60+float(s), lyric))
    return sorted(lines)

def choose_section(lines, duration, hint='', min_seconds=25, max_seconds=35):
    """Choose whole timed lines with no long instrumental break; never pad timing."""
    lines=sorted(set(lines))
    candidates=[]
    counts={}
    for _,text in lines:
        key=norm(text)
        if key: counts[key]=counts.get(key,0)+1
    limit=min(95,duration*.48) if '1절' in hint or '첫 소절' in hint or '랩' not in hint else duration-35
    for i,(start,text) in enumerate(lines):
        if not text or start<3 or start>limit: continue
        for j in range(i+1,min(i+25,len(lines))):
            end=lines[j][0]
            length=end-start
            if length>max_seconds: break
            if length<min_seconds: continue
            part=lines[i:j]
            nonempty=[line for _,line in part if line]
            if not 4<=len(nonempty)<=20: continue
            if any(not lines[k][1] and lines[k+1][0]-lines[k][0]>3 for k in range(i,j)): continue
            if any(lines[k+1][0]-lines[k][0]>12 for k in range(i,j)): continue
            answer='\n'.join(nonempty)
            density=len(re.sub(r'\s','',answer))/length
            if density<.8: continue
            repeated=sum(counts.get(norm(line),0)>1 for line in nonempty)/len(nonempty)
            score=-abs(length-30)*.7-repeated*5-start*.015
            if '랩' in hint or '빠른' in hint: score+=density*2
            else: score-=start*.08
            if '영어' in hint: score+=sum(c.isascii() and c.isalpha() for c in answer)/max(len(answer),1)*5
            candidates.append((score,round(start,2),round(end,2),answer))
    if not candidates: raise ValueError('25~35초의 연속 가창 구간 없음')
    _,start,end,answer=max(candidates,key=lambda x:x[0])
    return start,end,answer

def video_candidates(song):
    artist_en,title_en=names(song)
    query = f"{artist_en} {title_en} official audio"
    key = os.environ.get('YOUTUBE_API_KEY')
    if key:
        found = request('https://www.googleapis.com/youtube/v3/search', dict(key=key, part='snippet', q=query, type='video', videoEmbeddable='true', maxResults=6))
        ids = ','.join(x['id']['videoId'] for x in found.get('items', []))
        data = request('https://www.googleapis.com/youtube/v3/videos', dict(key=key, part='snippet,status,contentDetails', id=ids))
        result = []
        for x in data.get('items', []):
            if not x['status'].get('embeddable'): continue
            restriction = x['contentDetails'].get('regionRestriction', {})
            if 'KR' in restriction.get('blocked', []) or ('allowed' in restriction and 'KR' not in restriction['allowed']): continue
            d = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', x['contentDetails']['duration'])
            if not d: continue
            result.append(dict(id=x['id'], title=x['snippet']['title'], channel=x['snippet']['channelTitle'], duration=sum(int(v or 0)*k for v,k in zip(d.groups(), (3600,60,1))), embed_verified=True))
        return result
    env = dict(os.environ)
    env['PYTHONPATH'] = str(ROOT / '.deps') + os.pathsep + env.get('PYTHONPATH', '')
    CACHE.mkdir(exist_ok=True)
    path=CACHE/f"youtube-v3-{song['id']}.json"
    if path.exists(): return json.loads(path.read_text(encoding='utf-8'))
    result=[]
    for q in [f'{artist_en} {title_en} topic',query]:
        run = subprocess.run([sys.executable, '-m', 'yt_dlp', '--dump-single-json', '--flat-playlist', '--no-warnings', f'ytsearch6:{q}'], capture_output=True, text=True, encoding='utf-8', env=env, timeout=75)
        if run.returncode:
            if result: break
            continue
        result.extend(dict(id=x['id'],title=x.get('title',''),channel=x.get('channel',''),channel_verified=x.get('channel_is_verified'),duration=x.get('duration') or 0,embed_verified=False) for x in json.loads(run.stdout).get('entries',[]))
        if any(rank(v,song)>=100 for v in result): break
    if not result: raise RuntimeError('YouTube 검색 실패: API 키 설정 또는 yt-dlp 설치/네트워크 확인')
    path.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    return result

def embed_allowed(v):
    if v.get('embed_verified'): return True
    with urlopen(Request('https://www.youtube.com/watch?v='+v['id'],headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as response:
        page=response.read().decode('utf-8')
    match=re.search(r'"playableInEmbed"\s*:\s*(true|false)',page)
    return match is not None and match[1]=='true'

def rank(v,song=None):
    s = (v['title']+' '+v['channel']).lower()
    if song:
        artist,title=names(song)
        channel=norm(v['channel'])
        artists=[norm(artist),norm(song['artist'])]
        title_ok=any(norm(t) in norm(v['title']) for t in [title,song['title']] if norm(t))
        artist_ok=any(a in norm(s) for a in artists if a)
        bad=any(w in s for w in ['cover','karaoke','sped up','slowed','live','remix','instrumental','originally','piano','arrangement','노래방']) or bool(re.search(r'(?:^|\s)커버(?:\s|$)|\binst\b',s))
        if not title_ok or not artist_ok or bad: return -1000
        own_channel=any(a in channel for a in artists if a)
        topic='- topic' in s and own_channel
        labels=['smtown','jypentertainment','hybelabels','1thek','stonemusicentertainment','y gentertainment','geniemusic','pledisentertainment']
        own_identity=any(channel in (a,'official'+a,a+'official',a+'topic',a+'music') for a in artists if a)
        official=own_identity or (own_channel and v.get('channel_verified') is True) or channel in [norm(x) for x in labels]
        if topic: return 150
        if official and ('audio' in s or 'provided to youtube' in s): return 130
        if official and ('lyric' in s or '가사' in s): return 100
        if official and not any(w in v['title'].lower() for w in ['m/v',' mv','music video','performance','teaser']): return 125
        if official: return 70
        return 0
    return (100 if '- topic' in s or 'official audio' in s else 60 if 'lyric' in s and 'official' in s else 30 if 'official' in s else 0) - (150 if any(w in s for w in ['cover', 'karaoke', 'sped up', 'slowed', 'live performance']) else 0)

def fill(song):
    song = dict(song)
    issues = []
    try:
        videos = [v for v in video_candidates(song) if rank(v,song)>-1000]
        videos.sort(key=lambda v:rank(v,song),reverse=True)
        if not videos: raise ValueError('임베드 가능한 영상 후보 없음')
        matches = request('https://lrclib.net/api/search', dict(track_name=song['title'], artist_name=song['artist']))
        matches = [m for m in matches if m.get('syncedLyrics')]
        if not matches:
            matches = [m for m in request('https://lrclib.net/api/search', {'q':song['artist']+' '+song['title']}) if m.get('syncedLyrics')]
        artist_en,title_en=names(song)
        if not matches:
            matches=[m for m in request('https://lrclib.net/api/search',dict(artist_name=artist_en,track_name=title_en)) if m.get('syncedLyrics')]
        if not matches:
            matches=[m for m in request('https://lrclib.net/api/search',{'q':artist_en+' '+title_en}) if m.get('syncedLyrics')]
        if not matches: raise ValueError('싱크 가사 없음 (제목/가수 영문 표기 확인)')
        def similarity(m):
            def sim(value, candidates):
                v=norm(value)
                return max(1 if norm(c) and norm(c) in v else difflib.SequenceMatcher(None,v,norm(c)).ratio() for c in candidates)
            return sim(m.get('trackName',''),[song['title'],title_en])+sim(m.get('artistName',''),[song['artist'],artist_en])
        matches.sort(key=similarity, reverse=True)
        lyric=None
        for match in matches:
            if similarity(match)<1.3: continue
            try:
                start,end,answer=choose_section(parse_lrc(match['syncedLyrics']),match['duration'],song.get('section_hint',''))
                lyric=match
                break
            except ValueError: continue
        if lyric is None: raise ValueError('일치하는 싱크 가사에서 8~15초, 2~4줄 구간 확보 실패')
        videos.sort(key=lambda v:rank(v,song)-min(abs(v['duration']-lyric['duration']),60),reverse=True)
        v=None
        for candidate in videos:
            try:
                if embed_allowed(candidate):
                    v=candidate
                    v['embed_verified']=True
                    break
            except Exception: continue
        if v is None: raise ValueError('임베드 허용 확인 실패: 다음 실행 또는 영상 수동 지정 필요')
        song.update(youtube_id=v['id'],start_sec=start,end_sec=end,answer_lyrics=answer,video_title=v['title'],video_channel=v['channel'],video_duration=v['duration'],audio_duration=lyric['duration'],duration_delta_sec=round(v['duration']-lyric['duration'],2),lyric_source=f"https://lrclib.net/api/get/{lyric['id']}",embed_verified=v['embed_verified'])
        if rank(v,song)==0: issues.append('공식 채널 여부 미확인: 대체 업로드 후보')
        if not v['embed_verified']: issues.append('임베드 허용 미확인: 플레이어 사전 재생 필요')
        if abs(v['duration']-lyric['duration']) > 3: issues.append('영상/음원 길이 차이 3초 초과: 오프셋 수동 확인')
        issues.append('초기 구간 후보(랩/빠른 구간은 글자 밀도 우선): section_hint 화자/랩/후렴 위치 청취 확인 필요')
        song['status'] = 'candidate'
    except Exception as exc:
        song['status'] = 'missing'
        issues.append(str(exc))
    song['review_notes'] = '; '.join(issues)
    return song

def write_outputs(songs):
    raw = json.dumps(songs, ensure_ascii=False, indent=2)
    (ROOT/'songs_filled.json').write_text(raw, encoding='utf-8')
    # file:// fetch 제한 없이 HTML을 더블클릭할 수 있도록 동일 데이터 내장.
    template = (ROOT/'player.template.html').read_text(encoding='utf-8')
    (ROOT/'index.html').write_text(template.replace('__SONGS_JSON__',raw.replace('<','\\u003c')), encoding='utf-8')
    with (ROOT/'needs_review.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['id','artist','title','status','youtube_id','review_notes'])
        w.writeheader()
        for song in songs:
            if song.get('status')!='verified': w.writerow({k:song.get(k,'') for k in w.fieldnames})
    count=sum(bool(s.get('youtube_id') and isinstance(s.get('start_sec'),(int,float)) and s.get('end_sec',0)>s['start_sec']) for s in songs)
    with (ROOT/'구간선정_검토표.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['id','title','artist','lead_in_start_sec','start_sec','end_sec','duration_sec','lines','selection_reason','boundary_basis','recording_title','youtube_id','listening_status']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for s in songs:
            duration=round(s['end_sec']-s['start_sec'],2) if s.get('end_sec') is not None and s.get('start_sec') is not None else ''
            w.writerow(dict(id=s['id'],title=s['title'],artist=s['artist'],lead_in_start_sec=s.get('lead_in_start_sec',''),start_sec=s.get('start_sec'),end_sec=s.get('end_sec'),duration_sec=duration,lines=len(s.get('answer_lyrics','').splitlines()),selection_reason=s.get('section_rationale',''),boundary_basis=s.get('boundary_basis',''),recording_title=s.get('video_title',''),youtube_id=s.get('youtube_id',''),listening_status='가사 내용・발매 정보 검토 / 실제 마디 청취 확인 전' if s.get('section_content_reviewed') else '내용 검토 전'))
    report={'total':len(songs),'filled_candidates':count,'embed_allowed':sum(s.get('embed_verified') is True for s in songs),'verified':sum(s.get('status')=='verified' for s in songs),'missing':len(songs)-count,'needs_review':sum(s.get('status')!='verified' for s in songs),'target':80,'target_met':count>=80}
    report.update(content_reviewed=sum(s.get('section_content_reviewed') is True for s in songs),boundary_listened=sum(s.get('boundary_verified') is True for s in songs))
    (ROOT/'preparation_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--init',action='store_true',help='네트워크 없이 원본 100곡으로 플레이어 생성')
    p.add_argument('--limit',type=int,default=100)
    p.add_argument('--workers',type=int,default=3)
    p.add_argument('--refresh',action='store_true',help='자동 후보도 다시 준비 (직접 verified 항목은 유지)')
    p.add_argument('--rebuild',action='store_true',help='기존 JSON으로 HTML/리포트만 재생성')
    args=p.parse_args()
    if args.rebuild:
        write_outputs(json.loads((ROOT/'songs_filled.json').read_text(encoding='utf-8')))
        return
    if not args.init:
        from curate import main as curate_main
        curate_main()
        return
    with (ROOT/'songs.csv').open(encoding='utf-8-sig',newline='') as f: songs=list(csv.DictReader(f))
    for s in songs:
        for k in ('id','year','difficulty'): s[k]=int(s[k])
        s.update(start_sec=None,end_sec=None,status='missing',review_notes='자동 준비 미실행')
    if not args.init:
        previous={}
        if (ROOT/'songs_filled.json').exists(): previous={s['id']:s for s in json.loads((ROOT/'songs_filled.json').read_text(encoding='utf-8')) if s.get('youtube_id') and (not args.refresh or s.get('status')=='verified')}
        songs=[previous.get(s['id'],s) for s in songs]
        pending=[s for s in songs[:args.limit] if not s.get('youtube_id')]
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(fill,s):s['id'] for s in pending}
            for future in concurrent.futures.as_completed(futures):
                result=future.result()
                songs[result['id']-1]=result
                print(f"{result['id']:3} {result['status']} {result['artist']} - {result['title']}",flush=True)
                write_outputs(songs)
    write_outputs(songs)

if __name__=='__main__': main()
