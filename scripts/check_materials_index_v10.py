"""Read the local material index at desktop and narrow widths."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/editorial-v10'
def main():
    errors=[];checks=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto((ROOT/'output/submission-v10/00_材料清单与上传说明.html').as_uri())
        page.evaluate('document.querySelectorAll("img").forEach(x=>x.loading="eager")')
        page.wait_for_function('Array.from(document.images).every(x=>x.complete)')
        for width in [1440,390]:
            page.set_viewport_size({'width':width,'height':1000})
            value=page.evaluate('''()=>({width:innerWidth,documentWidth:document.documentElement.scrollWidth,brokenImages:Array.from(document.images).filter(x=>!x.naturalWidth).length,localFileLinks:Array.from(document.querySelectorAll('a')).filter(a=>a.protocol==='file:').length})''')
            assert value['documentWidth']<=width and value['brokenImages']==0
            checks.append(value)
            page.screenshot(path=str(ART/f'materials-index-{width}.png'),full_page=True)
            page.screenshot(path=str(ART/f'materials-index-preview-{width}.png'))
        page.locator('video').evaluate('(v)=>{v.currentTime=52}')
        page.wait_for_function('document.querySelector("video").readyState>=2')
        video=page.locator('video').evaluate('(v)=>({duration:v.duration,width:v.videoWidth,height:v.videoHeight,error:v.error?String(v.error.code):null})')
        assert video['width']==1600 and video['height']==1112 and video['error'] is None
        assert not errors
        browser.close()
    result={'status':'passed','created_on':'2026-10-24','viewports':checks,'video':video,'page_errors':errors}
    (ART/'index-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
