"""로컬 산출물의 내용과 HTML 내장 데이터가 일치하는지 검증한다."""
import csv
import json
import re
import subprocess
from pathlib import Path
from curate import excluded

root=Path(__file__).resolve().parent
data=json.loads((root/'songs_filled.json').read_text(encoding='utf-8'))
with (root/'songs.csv').open(encoding='utf-8-sig',newline='') as f:
    original=list(csv.DictReader(f))
assert len(data)==len(original)==100
assert len({s['id'] for s in data})==100
for s, source in zip(data,original):
    assert s['id']==int(source['id']) and s['artist']==source['artist'] and s['title']==source['title']
    if s.get('youtube_id'):
        assert re.fullmatch(r'[A-Za-z0-9_-]{11}',s['youtube_id'])
        assert 25<=round(s['end_sec']-s['start_sec'],2)<=35
        assert 4<=len(s['answer_lyrics'].splitlines())<=20
        assert s['embed_verified'] is True
        assert s['source_type']=='official_art_track' and s['audit_version']==4
        assert s['evidence']['auto_generated'] is True
        assert s['evidence']['provider'].startswith('Provided to YouTube by')
        assert not excluded(s['video_title'])
        assert s['duration_delta_sec']<=2.5
        assert 0<=s['start_sec']<s['end_sec']<=s['video_duration']
html=(root/'index.html').read_text(encoding='utf-8')
embedded=html.split('<script id="songData" type="application/json">')[1].split('</script>')[0]
assert json.loads(embedded)==data
report=json.loads((root/'preparation_report.json').read_text(encoding='utf-8'))
assert report['filled_candidates']==sum(bool(s.get('youtube_id')) for s in data)
with (root/'needs_review.csv').open(encoding='utf-8-sig',newline='') as f:
    review=list(csv.DictReader(f))
assert {int(s['id']) for s in review}=={s['id'] for s in data if s['status']!='verified'}
check=root/'.check.js'
try:
    check.write_text(html.split('<script>')[1].split('</script>')[0],encoding='utf-8')
    subprocess.run(['node','--check',str(check)],check=True)
finally:
    check.unlink(missing_ok=True)
print(f"PASS: original 100 songs preserved; {report['filled_candidates']} valid candidates; HTML/JSON/report consistent; JS syntax valid")
