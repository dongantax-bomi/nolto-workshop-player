# 놀토 받쓰 클럽

게임 접속: https://dongantax-bomi.github.io/nolto-workshop-player/

크롬과 인터넷 연결로 실행합니다. 로컬 서버나 파일 선택은 필요 없습니다.

## 진행 방법

1. 곡을 누르면 앞 구절부터 받쓰 구간 끝까지 끊김 없이 재생합니다.
2. 설명할 곳에서 진행자가 일시정지를 누릅니다.
3. 일시정지 옆 이어서 재생은 멈춘 위치에서 계속합니다.
4. 다시 듣기 / Space는 등록된 받쓰 구간만 처음부터 반복합니다. 앞 구절도 다시 들으려면 목록에서 곡을 다시 누릅니다.
5. Enter 또는 정답 공개로 정답을 표시합니다.

받쓰 시작점에서 자동으로 정지하거나 위치를 이동하는 기능은 제거했습니다. 별도의 도입 자동정지 버튼도 없습니다. 받쓰 구간 끝에서는 기존처럼 재생을 종료합니다.

## 100곡 점검

100곡 모두 앞 구절과 받쓰 단락을 연결해 다시 선정했습니다. 일정한 초 수를 빼서 도입을 만드는 대신 곡마다 앞선 가사 구절과 단락 전환을 골랐습니다. 앞부분이 없던 첫 소절 문제는 앞 구절을 들을 수 있는 다른 단락으로 옮겼습니다.

곡별 근거는 section_overrides.json과 구간선정_검토표.csv에 있습니다. 발매 정보는 recording_catalog.json에 고정했습니다. 가사 내용 및 발매 자료 대조와 실제 청취 검증은 구분하며, 전곡의 실제 마디 끝과 잔향은 청취 확인 전입니다.

## 설정 및 개발

시작/끝과 정답은 진행자 설정에서 수정할 수 있습니다. 브라우저별로 저장하며 JSON으로 옮깁니다. 새 구간 버전에서는 이전 자동 구간을 교체합니다.

python prepare.py --rebuild
python -m unittest -v test_prepare test_curate
node test_playback.cjs
python validate_delivery.py
python build_site.py

main에 push하면 GitHub Actions가 검사 후 Pages에 배포합니다. player.template.html은 화면 원본이고 songs_filled.json은 배포 데이터입니다.
