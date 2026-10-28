"""Additional local ASR evidence; singing transcription is not authoritative lyrics."""
import argparse
import json
from audio_analysis_probe import ROOT, WORK


def main():
    from faster_whisper import WhisperModel
    import soundfile as sf
    import soxr
    parser=argparse.ArgumentParser()
    parser.add_argument('--songs',nargs='+',type=int,required=True)
    parser.add_argument('--source',choices=['vocals','mix'],default='vocals')
    args=parser.parse_args()
    cached_model=WORK/'whisper-models/models--Systran--faster-whisper-small/snapshots'
    model=WhisperModel('small',device='cpu',compute_type='int8',cpu_threads=2,
                       download_root=str(WORK/'whisper-models'),
                       local_files_only=cached_model.exists())
    for song_id in args.songs:
        job=WORK/'probes'/str(song_id)
        report=json.loads((job/'report.json').read_text(encoding='utf-8'))
        input_file=job/'context.wav' if args.source=='mix' else job/'stems/htdemucs/context/vocals.wav'
        audio,sr=sf.read(input_file,dtype='float32',always_2d=True)
        audio=soxr.resample(audio.mean(axis=1),sr,16000)
        segments,info=model.transcribe(audio,
                                      language='ko',word_timestamps=True,beam_size=3,
                                      condition_on_previous_text=False,vad_filter=False)
        rows=[]
        for segment in segments:
            rows.append(dict(start=round(segment.start+report['crop_offset'],3),
                             end=round(segment.end+report['crop_offset'],3),text=segment.text,
                             words=[dict(start=round(w.start+report['crop_offset'],3),
                                         end=round(w.end+report['crop_offset'],3),word=w.word,
                                         probability=round(w.probability,3)) for w in segment.words or []]))
        out=dict(song_id=song_id,audio_sha256=report['audio_sha256'],audio_input=args.source,
                 crop_offset=report['crop_offset'],model='faster-whisper small int8',
                 caution='ASR on singing may omit or hallucinate words; compare lyrics and vocal envelope',segments=rows)
        output_name='words-mix.json' if args.source=='mix' else 'words.json'
        (job/output_name).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(out,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
