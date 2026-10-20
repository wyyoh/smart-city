"""Isolated UI QA server with delayed responses and one explicit error fixture."""
import argparse
import asyncio
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'scripts'))
from v2_isolation import copy_baseline

from fastapi.responses import JSONResponse
import uvicorn
from app.main import create_app
from app.storage import make_engine


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8768)
    parser.add_argument('--delay-ms',type=int,default=2400)
    args=parser.parse_args()
    path=ROOT/'artifacts/next-phase/ui-review.sqlite'
    if not path.exists():
        copy_baseline(path)
    app=create_app(make_engine(path))

    @app.middleware('http')
    async def review_fixtures(request,call_next):
        delayed=request.method=='POST' and request.url.path in ['/v2/demand-resolutions','/v2/decisions']
        if request.method=='POST' and request.url.path=='/v2/demand-resolutions':
            body=await request.json()
            if body.get('name')=='UI_ERROR_FIXTURE':
                return JSONResponse({'detail':'UI验收模拟：服务暂时不可用，请修改名称后重试'},status_code=503)
        response=await call_next(request)
        if delayed:
            await asyncio.sleep(args.delay_ms/1000)
        return response

    print(f'Isolated UI QA: http://127.0.0.1:{args.port}/ ; response delay {args.delay_ms} ms',flush=True)
    uvicorn.run(app,host='127.0.0.1',port=args.port)


if __name__=='__main__':main()
