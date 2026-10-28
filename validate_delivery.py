"""로컬 산출물의 내용과 HTML 내장 데이터가 일치하는지 검증한다."""
import csv
import json
import re
import subprocess
from pathlib import Path
from curate import excluded,art_matches

root=Path(__file__).resolve().parent
data=json.loads((root/'songs_filled.json').read_text(encoding='utf-8'))
sections=json.loads((root/'section_overrides.json').read_text(encoding='utf-8'))
catalog=json.loads((root/'recording_catalog.json').read_text(encoding='utf-8'))
audio_audit=json.loads((root/'audio_boundary_audit.json').read_text(encoding='utf-8'))
with (root/'songs.csv').open(encoding='utf-8-sig',newline='') as f:
    original=list(csv.DictReader(f))
expected=[101,103,104,42,102,105]
assert len(data)==len(original)==6
assert [s['id'] for s in data]==expected
assert [s['round_label'] for s in data]==['1R','2R','3R','4R','5R','연장']
assert [s['round_points'] for s in data]==[1,1,1,1,2,1]
assert set(sections)==set(catalog)=={str(i) for i in expected}
# 교체한 곡(101~105)은 싱크 가사 기준 구간이며 실제 오디오 분석 기록이 없습니다.
analyzed=[s for s in data if s.get('audio_analyzed')]
assert [r['song_id'] for r in audio_audit]==[s['id'] for s in analyzed]
assert {s['id'] for s in data}-{s['id'] for s in analyzed}=={101,102,103,104,105}
for s,a in zip(analyzed,audio_audit):
    assert s['youtube_id']==a['youtube_id'] and s['audio_sha256']==a['audio_sha256']
    assert a['review_state']=='signal_and_lyric_reviewed_not_listened'
    for key in ['lead_in_start_sec','start_sec','end_sec']:
        assert s[key]==a[key]
# 사용자 지정 구간: (도입, 시작, 끝, 첫 줄, 마지막 줄)
user_sections={
    101:(91.16,118.82,137.16,'어제의 나를 담은 일기장과는','나아가려던 꼬마 아이잖아'),
    103:(161.75,182.49,199.06,'짧은 머리 눈이 부신 그대가 좋아','드라마도 끊겠어요'),
    104:(27.64,42.09,55.81,'그날 이후로 난 이렇게 살고','웃기지 그런데'),
    102:(50.04,64.68,79.59,'혹시 그대가 미안해한다면','저 붉은 노을을 닮아 더 슬퍼지는 걸'),
    105:(51.54,67.89,87.06,'매일의 새로운 면도','"펑" 하고 터질 것 같은 기분'),
}
for s in data:
    if s['id'] in user_sections:
        lead,start,end,first,last=user_sections[s['id']]
        assert (s['lead_in_start_sec'],s['start_sec'],s['end_sec'])==(lead,start,end)
        assert s['answer_lyrics'].splitlines()[0]==first
        assert s['answer_lyrics'].splitlines()[-1]==last
    if s['id']==42:
        assert s['answer_lyrics'].splitlines()[-1].endswith('예쁘장한 savage')
        assert s['end_sec']<36.62
for s, source in zip(data,original):
    assert s['id']==int(source['id']) and s['artist']==source['artist'] and s['title']==source['title']
    if s.get('youtube_id'):
        assert re.fullmatch(r'[A-Za-z0-9_-]{11}',s['youtube_id'])
        spec=sections[str(s['id'])]
        assert s['section_method']=='editorial_passage_lrc_boundary'
        assert s['section_content_reviewed'] is True and s['section_revision']==spec.get('revision',2)
        assert s['lyric_id']==spec['lyric_id'] and s['youtube_id']==spec['youtube_id']
        bounds=spec.get('audio_boundaries',spec)
        assert s['start_sec']==bounds['start_sec'] and s['end_sec']==bounds['end_sec']
        if 'audio_boundaries' in spec:
            assert s['audio_analyzed'] is True
            assert s['audio_sha256']==bounds['audio_sha256']
            assert s['lead_in_start_sec']==bounds['lead_in_start_sec']
        assert s['section_rationale']==spec['reason']
        assert s['section_context_reviewed'] is True and s['playback_mode']=='continuous_context'
        assert s['lead_in_rationale']==spec['lead_in_reason'] and s['lead_in_rationale']
        assert 0<=s['lead_in_start_sec']<s['start_sec']
        assert s['boundary_verified'] is False  # No listening claim inferred from text review.
        assert len(s['answer_lyrics'].splitlines())>=4
        if s['id'] not in [60,79,82,97,98,91,94]: assert len(re.findall('[가-힣]',s['answer_lyrics']))>=10
        assert not re.search('[ぁ-ヿ一-鿿]',s['answer_lyrics'])
        assert s['embed_verified'] is True
        assert s['source_type']=='official_art_track' and s['audit_version']==4
        assert s['evidence']['auto_generated'] is True
        assert s['evidence']['provider'].startswith('Provided to YouTube by')
        assert not excluded(s['video_title'])
        recording=catalog[str(s['id'])]
        assert recording['id']==s['youtube_id'] and recording['title']==s['video_title']
        assert recording['duration']==s['video_duration'] and art_matches(recording,s)
        assert s['duration_delta_sec']<=2.5
        assert 0<=s['start_sec']<s['end_sec']<=s['video_duration']
html=(root/'index.html').read_text(encoding='utf-8')
assert 'id="leadInBtn"' not in html
assert '여기서부터 받쓰입니다 · 설명 후 이어서 재생' not in html
embedded=html.split('<script id="songData" type="application/json">')[1].split('</script>')[0]
assert json.loads(embedded)==data
report=json.loads((root/'preparation_report.json').read_text(encoding='utf-8'))
assert report['filled_candidates']==sum(bool(s.get('youtube_id')) for s in data)
assert report['target']==report['total']==6 and report['target_met'] is True
assert report['audio_analyzed']==len(analyzed)==1
with (root/'needs_review.csv').open(encoding='utf-8-sig',newline='') as f:
    review=list(csv.DictReader(f))
assert {int(s['id']) for s in review}=={s['id'] for s in data if s['status']!='verified'}
check=root/'.check.js'
try:
    check.write_text(html.split('<script>')[1].split('</script>')[0],encoding='utf-8')
    subprocess.run(['node','--check',str(check)],check=True)
finally:
    check.unlink(missing_ok=True)
print(f"PASS: selected six rounds only; {report['filled_candidates']} valid candidates; HTML/JSON/report consistent; JS syntax valid")
