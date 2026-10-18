"""Create a portable source/static/model/data bundle with a full hash manifest."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from sqlmodel import Session

from app.importer import import_workbook
from app.main import create_app
from app.domain.contracts import Scenario
from app.services import case_cards, html_report, recommend
from app.settings import ROOT, VERSION
from app.storage import initialize, make_engine, now


def build():
    stamp=now().replace(':','').replace('-','').split('.')[0].replace('+','_')
    destination=ROOT/'artifacts/release'/f'asphalt-workbench-{VERSION}-{stamp}'
    destination.mkdir(parents=True,exist_ok=False)
    folders=['backend','frontend/dist','configs','docs','scripts','tests','planning','design']
    for folder in folders:
        shutil.copytree(ROOT/folder,destination/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.tsbuildinfo'))
    for folder in ['frontend/src']:
        shutil.copytree(ROOT/folder,destination/folder)
    for relative in ['README.md','requirements.lock.txt','pyproject.toml','.gitignore','frontend/package.json',
                     'frontend/pnpm-lock.yaml','frontend/tsconfig.json','frontend/vite.config.ts','frontend/index.html',
                     '再生沥青混合料实验数据表.xlsx','数智选材_领域与前沿技术调研底稿_v1.md']:
        shutil.copy2(ROOT/relative,destination/relative)
    for pdf in ROOT.glob('*.pdf'):shutil.copy2(pdf,destination/pdf.name)
    shutil.copytree(ROOT/'artifacts/models',destination/'artifacts/models')
    for folder in ['artifacts/demo','artifacts/screenshots']:
        if (ROOT/folder).exists():
            shutil.copytree(ROOT/folder,destination/folder,ignore=shutil.ignore_patterns('*before-fix*'))
    for rehearsal in ['final-rehearsal-1','final-rehearsal-2']:
        path=ROOT/'artifacts/acceptance'/rehearsal
        if path.exists():
            shutil.copytree(path,destination/'artifacts/acceptance'/rehearsal,ignore=shutil.ignore_patterns('*.sqlite*','*.log'))
    for name in ['next_test_replay.json','verification.json','development_progress.json']:
        path=ROOT/'artifacts'/name
        if path.exists():shutil.copy2(path,destination/'artifacts'/name)
    database=destination/'data/workbench.sqlite';eng=make_engine(database);initialize(eng)
    with Session(eng) as session:
        ds,_=import_workbook(destination/'再生沥青混合料实验数据表.xlsx',session)
        for case in case_cards():
            result=recommend(session,Scenario.model_validate(case['scenario']))
            output=destination/'artifacts/demo-reports';output.mkdir(exist_ok=True)
            (output/f'{case["id"]}.html').write_text(html_report(result),encoding='utf-8')
            (output/f'{case["id"]}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        data_id=ds.id;sha=ds.sha256
    eng.dispose()
    (destination/'docs/api.openapi.json').write_text(json.dumps(create_app().openapi(),ensure_ascii=False,indent=2),encoding='utf-8')
    files=[{'path':p.relative_to(destination).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
           for p in sorted(destination.rglob('*')) if p.is_file()]
    manifest={'app_version':VERSION,'created_at':now(),'dataset_id':data_id,'dataset_sha256':sha,'files':files,
              'environment':'Python 3.12+ / Node 24 / pnpm 11; dependency installation required on new host',
              'scope':'本地研究原型，自动优化未启用；尚未企业或独立工程验证'}
    (destination/'release-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=Path(str(destination)+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as zip:
        for p in destination.rglob('*'):
            if p.is_file():zip.write(p,Path(destination.name)/p.relative_to(destination))
    print(json.dumps({'directory':str(destination),'zip':str(archive),'files':len(files),
                      'zip_bytes':archive.stat().st_size,'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},ensure_ascii=False,indent=2))


if __name__=='__main__':build()
