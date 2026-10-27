"""Actual-audio feasibility probe. Produces evidence, never edits game timings.

Run with the isolated Python 3.12 environment in .cache/audio-analysis/venv.
Audio, model weights, stems, and reports stay in the ignored .cache directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
WORK=ROOT/'.cache/audio-analysis'
os.environ['TORCH_HOME']=str(WORK/'models')
sys.path.insert(0,str(WORK/'ffmpeg'))

def quiet_intervals(db,times,threshold=-30,minimum=.12):
    import numpy as np
    mask=db<threshold
    edges=np.diff(np.r_[False,mask,False].astype(int))
    starts=np.where(edges==1)[0];ends=np.where(edges==-1)[0]
    result=[]
    for a,b in zip(starts,ends):
        start=float(times[a]-.005);end=float(times[min(b,len(times)-1)]-.005)
        if end-start>=minimum:result.append((round(start,3),round(end,3)))
    return result

def analyze(song,threads=2):
    import numpy as np
    import soundfile as sf
    import torch
    import imageio_ffmpeg
    from beat_this.inference import File2Beats
    import demucs.separate

    torch.set_num_threads(threads)
    media=next((p for p in (WORK/'media').glob(song['youtube_id']+'.*')
                if p.suffix in {'.webm','.m4a','.mp3','.ogg','.opus','.wav'}),None)
    if not media:raise FileNotFoundError('The exact catalog recording must be acquired before analysis')
    job=WORK/'probes'/str(song['id']);job.mkdir(parents=True,exist_ok=True)
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    os.environ['PATH']=str(Path(ffmpeg).parent)+os.pathsep+os.environ.get('PATH','')
    crop_start=max(0,song.get('lead_in_start_sec',song['start_sec'])-10)
    crop_end=min(song['video_duration'],song['end_sec']+10)
    digest=hashlib.sha256(media.read_bytes()).hexdigest()
    signature=dict(audio_sha256=digest,crop_start=crop_start,crop_end=crop_end,model='htdemucs')
    manifest=job/'stem-input.json'
    cache_valid=manifest.exists() and json.loads(manifest.read_text(encoding='utf-8'))==signature
    clip=job/'context.wav'
    subprocess.run([ffmpeg,'-nostdin','-v','error','-y','-i',str(media),'-ss',str(crop_start),'-t',str(crop_end-crop_start),'-ac','2','-ar','44100',str(clip)],check=True)
    print(json.dumps(dict(stage='decoded_actual_audio',song_id=song['id'],seconds=round(crop_end-crop_start,2))),flush=True)
    stems=job/'stems/htdemucs/context'
    vocals=stems/'vocals.wav'
    began=time.monotonic()
    if not vocals.exists() or not cache_valid:
        demucs.separate.main(['-n','htdemucs','--two-stems','vocals','--shifts','0','-d','cpu','-j','1','-o',str(job/'stems'),str(clip)])
        manifest.write_text(json.dumps(signature),encoding='utf-8')
    print(json.dumps(dict(stage='vocals_separated',elapsed=round(time.monotonic()-began,1))),flush=True)
    signal,sr=sf.read(vocals,dtype='float32',always_2d=True)
    power=np.mean(signal.astype('float64')**2,axis=1)
    frame=round(sr*.04);hop=round(sr*.01)
    cumulative=np.r_[0,np.cumsum(power)]
    positions=np.arange(0,len(signal)-frame,hop)
    rms=np.sqrt(np.maximum(0,(cumulative[positions+frame]-cumulative[positions])/frame))
    reference=max(float(np.percentile(rms,95)),1e-8)
    db=20*np.log10(np.maximum(rms,1e-10)/reference)
    times=(positions+frame/2)/sr+crop_start
    intervals=quiet_intervals(db,times)
    tracker=File2Beats(checkpoint_path='small0',device='cpu',dbn=False)
    beats,downbeats=tracker(str(clip))
    beats=np.asarray(beats)+crop_start;downbeats=np.asarray(downbeats)+crop_start
    print(json.dumps(dict(stage='beats_detected',beats=len(beats),downbeats=len(downbeats))),flush=True)
    edge_reports={}
    for key in ['lead_in_start_sec','start_sec','end_sec']:
        original=float(song[key])
        around=np.abs(times-original)<=.1
        near_gaps=[dict(start=a,end=b) for a,b in intervals if a<original+3 and b>original-3]
        near_bars=[round(float(t),3) for t in downbeats if abs(t-original)<=3]
        vocal_db=float(np.median(db[around])) if around.any() else None
        edge_reports[key]=dict(original=original,vocal_db=vocal_db,
                               quiet_gaps=near_gaps,downbeats=near_bars,
                               review_required=vocal_db is None or vocal_db>-18,
                               caution='Energy is a diagnostic, not proof of a syllable or phrase boundary')
    report=dict(song_id=song['id'],youtube_id=song['youtube_id'],audio_sha256=digest,
                audio_duration=round(len(signal)/sr,3),crop_offset=crop_start,
                separation_model='htdemucs',beat_model='BeatThis small0',
                evidence_type='actual_audio_analysis_not_listening',
                status='probe_only_not_applied',elapsed_sec=round(time.monotonic()-began,1),edges=edge_reports,
                quiet_intervals=[dict(start=a,end=b) for a,b in intervals],
                downbeats=[round(float(t),3) for t in downbeats])
    (job/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--song',type=int,default=9);parser.add_argument('--threads',type=int,default=2)
    args=parser.parse_args()
    songs=json.loads((ROOT/'songs_filled.json').read_text(encoding='utf-8'))
    analyze(next(s for s in songs if s['id']==args.song),args.threads)
