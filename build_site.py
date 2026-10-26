"""GitHub Pages 배포 폴더 생성."""
from pathlib import Path
from shutil import copy2

root=Path(__file__).resolve().parent
output=root/'_site'
output.mkdir(exist_ok=True)
for name in ['index.html','songs_filled.json','needs_review.csv','preparation_report.json']:
    copy2(root/name,output/name)
(output/'.nojekyll').write_text('',encoding='utf-8')
print('Static website ready: _site/index.html')
