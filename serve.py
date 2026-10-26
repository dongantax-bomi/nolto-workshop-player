"""YouTube 출처 정보 제한 대응용 로컬 실행. 외부 네트워크에는 서버를 열지 않는다."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import webbrowser
import argparse
from urllib.request import urlopen

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).resolve().parent), **kwargs)
    def do_GET(self):
        if self.path.split('?')[0] not in ('/', '/index.html', '/songs_filled.json', '/favicon.ico'):
            self.send_error(404)
            return
        super().do_GET()
    def end_headers(self):
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        super().end_headers()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    except OSError:
        existing_url=f'http://127.0.0.1:{args.port}/'
        try:
            with urlopen(existing_url,timeout=2) as response:
                existing_page=response.read().decode('utf-8')
            if '<title>놀토 받쓰 클럽' in existing_page:
                print(existing_url,flush=True)
                if not args.no_browser: webbrowser.open(existing_url)
                raise SystemExit(0)
        except (OSError,UnicodeError):
            pass
        print(f'Port {args.port} is already in use. Open http://127.0.0.1:{args.port}/ or use --port 8767.', flush=True)
        raise SystemExit(1)
    url = f'http://127.0.0.1:{server.server_port}/'
    print(f'플레이어: {url}\n이 창을 닫으면 종료됩니다.', flush=True)
    if not args.no_browser:
        threading.Timer(.4, lambda: webbrowser.open(url)).start()
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
