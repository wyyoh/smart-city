"""Add a dedicated subtitle band to the verified continuous browser recording."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'artifacts/submission-v8/demo'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def clock(seconds):
    cs=round(seconds*100)
    return f'{cs//360000}.{cs//6000%60:02}.{cs//100%60:02}.{cs%100:02}'.replace('.',':',2)


def main():
    recording=json.loads((FOLDER/'recording.json').read_text(encoding='utf-8'))
    assert recording['recording_pace']==1.0 and not recording['page_errors']
    raw=ROOT/recording['raw_video']['path']
    assert sha(raw)==recording['raw_video']['sha256']
    header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1600
PlayResY: 1112
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,32,&H00FFFFFF,&H00FFFFFF,&H00102020,&H00102020,0,0,0,0,100,100,0,0,1,0,0,2,50,50,28,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    rows=[]
    for item in recording['subtitles']:
        rows.append(f"Dialogue: 0,{clock(item['start'])},{clock(item['end'])},Default,,0,0,0,,{item['text']}")
    (FOLDER/'operation.ass').write_text(header+'\n'.join(rows)+'\n',encoding='utf-8')
    output=FOLDER/'数智选材_五案实际操作.mp4'
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:raise RuntimeError('Install ffmpeg with libass for optional video authoring')
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(raw),
                    '-vf','pad=1600:1112:0:0:color=0x142930,ass=artifacts/submission-v8/demo/operation.ass',
                    '-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p','-r','25','-an',
                    '-metadata','title=数智选材五案实际操作','-metadata','artist=',
                    '-movflags','+faststart',str(output)],cwd=ROOT,check=True)
    # Decode all frames to detect truncation or codec errors.
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-i',str(output),'-f','null','-'],check=True)
    probe=shutil.which('ffprobe')
    if not probe:raise RuntimeError('ffprobe is required to verify the final video')
    metadata=json.loads(subprocess.check_output([probe,'-v','error','-show_format','-show_streams','-of','json',str(output)],encoding='utf-8'))
    video=next(s for s in metadata['streams'] if s['codec_type']=='video')
    duration=float(metadata['format']['duration'])
    assert video['width']==1600 and video['height']==1112 and duration>=recording['subtitles'][-1]['end']-.5
    result={'created_on':'2026-10-23','status':'encoded_and_full_decode_passed',
            'path':output.relative_to(ROOT).as_posix(),'bytes':output.stat().st_size,'sha256':sha(output),
            'duration_seconds':duration,'resolution':[1600,1112],'codec':video['codec_name'],
            'raw_recording_sha256':recording['raw_video']['sha256'],
            'format':'Current application actual continuous browser recording; automated operations; subtitle band; no narration.',
            'editing':'One continuous page recording, no replacement of page results; dedicated subtitle band added.'}
    (FOLDER/'video.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
