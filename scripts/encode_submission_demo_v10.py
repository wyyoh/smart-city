"""Rewrite subtitles over the unchanged continuous application recording."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from encode_submission_demo_v8 import clock

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/editorial-v10/demo'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    original=ROOT/'artifacts/submission-v8/demo/recording.json'
    recording=json.loads(original.read_text(encoding='utf-8'))
    raw=ROOT/recording['raw_video']['path']
    assert sha(raw)==recording['raw_video']['sha256']
    assert recording['recording_pace']==1.0 and not recording['page_errors']
    edits={
        6:'原始数值与要求线同时呈现，便于逐项查看候选差异。',
        11:'草案保留原需求和实际改动，新设计性能以待验证状态登记。',
        13:'资源条件与性能要求一起保存，确认后另存本次调整记录。',
        14:'C5的84条目录含缺测，先查看待补证据与资料核对方向。',
        16:'展开冲突子集与删除见证，核对当前范围中的要求组合，再选择后续操作。'
    }
    for index,value in edits.items():recording['subtitles'][index-1]['text']=value
    OUT.mkdir(parents=True,exist_ok=True)
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
    rows=[f"Dialogue: 0,{clock(x['start'])},{clock(x['end'])},Default,,0,0,0,,{x['text']}" for x in recording['subtitles']]
    (OUT/'operation.ass').write_text(header+'\n'.join(rows)+'\n',encoding='utf-8')
    (OUT/'subtitles.json').write_text(json.dumps(recording['subtitles'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    output=OUT/'五案实际操作.mp4';ffmpeg=shutil.which('ffmpeg');probe=shutil.which('ffprobe')
    assert ffmpeg and probe
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(raw),
                    '-vf','pad=1600:1112:0:0:color=0x142930,ass=artifacts/editorial-v10/demo/operation.ass',
                    '-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p','-r','25','-an',
                    '-metadata','title=数智选材五案实际操作','-metadata','artist=',
                    '-movflags','+faststart',str(output)],cwd=ROOT,check=True)
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-i',str(output),'-f','null','-'],check=True)
    meta=json.loads(subprocess.check_output([probe,'-v','error','-show_format','-show_streams','-of','json',str(output)],encoding='utf-8'))
    video=next(x for x in meta['streams'] if x['codec_type']=='video')
    duration=float(meta['format']['duration'])
    assert video['width']==1600 and video['height']==1112 and duration>=recording['subtitles'][-1]['end']-.5
    result={'status':'encoded_and_full_decode_passed','created_on':'2026-10-24',
            'path':output.relative_to(ROOT).as_posix(),'sha256':sha(output),'bytes':output.stat().st_size,
            'duration_seconds':duration,'resolution':[1600,1112],
            'raw_recording_sha256':sha(raw),'page_recording_unchanged':True,
            'subtitle_edits':list(edits),'subtitle_count':len(recording['subtitles']),
            'operations':'AI browser self-test from the frozen v8 recording; subtitles rewritten.'}
    (OUT/'video.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
