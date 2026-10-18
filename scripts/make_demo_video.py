"""Encode recorded UI steps, explicitly a screenshot sequence rather than a live screencast."""
import json
from pathlib import Path
import subprocess
import imageio_ffmpeg

from app.settings import ROOT


def main():
    frames=['C1.jpg','C2.jpg','C3.jpg','C4.jpg','C5.jpg','models.jpg']
    directory=ROOT/'artifacts/screenshots'
    output=ROOT/'artifacts/demo';output.mkdir(exist_ok=True)
    concat=output/'frames.txt'
    # Relative source names are fixed by this script, never user-provided shell text.
    content=''.join(f"file '{(directory/name).as_posix()}'\nduration 5\n" for name in frames)
    content+=f"file '{(directory/frames[-1]).as_posix()}'\n"
    concat.write_text(content,encoding='utf-8')
    result=output/'数智选材_界面步骤回放.mp4'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y',
                    '-f','concat','-safe','0','-i',str(concat),'-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2',
                    '-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart','-r','20',str(result)],check=True)
    manifest={'format':'界面截图步骤回放；非连续现场录屏，无配音','duration_seconds':30,
              'frames':frames,'video':result.name,'source':'本地工作台真实运行截图，构造案例与真实历史记录聚合',
              'continuous_workflow_evidence':'artifacts/acceptance/final-rehearsal-1与final-rehearsal-2'}
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'path':str(result),'bytes':result.stat().st_size,**manifest},ensure_ascii=False))


if __name__=='__main__':main()
