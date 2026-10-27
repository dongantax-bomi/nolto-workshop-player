"""Batch actual-audio audit; never changes or publishes game timings/media.

Run in .cache/audio-analysis/venv with --songs 1 4 7 9 or --all.
Per-song failures are recorded and do not discard successful analysis.
"""
import argparse
import json
import sys
from datetime import datetime, timezone

from audio_analysis_probe import ROOT, WORK, analyze


def acquire(song):
    sys.path.insert(0, str(ROOT / '.deps'))
    import yt_dlp
    target = WORK / 'media'
    target.mkdir(parents=True, exist_ok=True)
    if any(p.suffix in {'.webm', '.m4a', '.mp3', '.ogg', '.opus', '.wav'}
           for p in target.glob(song['youtube_id'] + '.*')):
        return
    with yt_dlp.YoutubeDL(dict(
        quiet=True, no_warnings=True, noplaylist=True, format='bestaudio',
        socket_timeout=20, retries=1, js_runtimes={'node': {}},
        outtmpl=str(target / '%(id)s.%(ext)s'),
    )) as downloader:
        downloader.download(['https://www.youtube.com/watch?v=' + song['youtube_id']])


def main():
    parser = argparse.ArgumentParser()
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--songs', nargs='+', type=int)
    selection.add_argument('--all', action='store_true')
    parser.add_argument('--threads', type=int, default=2)
    args = parser.parse_args()
    songs = json.loads((ROOT / 'songs_filled.json').read_text(encoding='utf-8'))
    selected = songs if args.all else [s for s in songs if s['id'] in args.songs]
    if args.songs and {s['id'] for s in selected} != set(args.songs):
        parser.error('Unknown song ID')
    results = []
    summary_path = WORK / 'batch-report.json'
    for song in selected:
        try:
            print(json.dumps(dict(stage='song_started', song_id=song['id'])), flush=True)
            acquire(song)
            report = analyze(song, args.threads)
            results.append(dict(song_id=song['id'], youtube_id=song['youtube_id'],
                                status=report['status'], edges=report['edges']))
        except Exception as exc:
            results.append(dict(song_id=song['id'], status='failed', error=str(exc)))
            print(json.dumps(results[-1], ensure_ascii=True), flush=True)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(dict(
            updated_at=datetime.now(timezone.utc).isoformat(),
            requested=len(selected), finished=len(results),
            timings_applied=False, results=results,
        ), ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
