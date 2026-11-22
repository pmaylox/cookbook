"""Alpha 0.2.3 photo storage integration tests with mocked IDB for opaque browser test origin."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/'my-cookbook-alpha-0.2.3.html'
PHOTO=ROOT/'tests/test-recipe-card.png'
passed=[]; errors=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
    ctx=browser.new_context(accept_downloads=True,viewport={'width':412,'height':915})
    ctx.route('**/cdnjs.cloudflare.com/**',lambda route:route.abort())
    page=ctx.new_page()
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.evaluate((ROOT/'tests/mock_indexeddb.js').read_text())
    page.evaluate("Object.defineProperty(window, 'localStorage', {value:{d:{}, getItem(k){return this.d[k]??null},setItem(k,v){this.d[k]=String(v)},removeItem(k){delete this.d[k]}}})")
    page.set_content(FILE.read_text(),wait_until='domcontentloaded')
    page.evaluate('''window.Tesseract={createWorker:async()=>({recognize:async()=>({data:{text:"Pawpaw Pie\\nIngredients\\n3 cups pawpaws\\nDirections\\nStir and bake at 350 F"}}),terminate:async()=>{}})}''')
    page.evaluate('''window.CookbookAndroid={storeRecipePhoto:(id,data)=>{window.__copies=window.__copies||[];window.__copies.push({id,length:data.length})}}''')
    page.locator('#addBtn').click();page.get_by_role('button',name='Scan a recipe photo').click()
    page.locator('#scanGallery').set_input_files(str(PHOTO))
    page.wait_for_function("document.querySelector('#scanRaw').value.includes('Pawpaw Pie')")
    page.locator('#scanGallery').set_input_files(str(PHOTO))
    page.wait_for_function("document.querySelector('#scanPhotoCount').textContent.startsWith('2 / 8')")
    assert page.locator('#scanPhotoPreview img').count()==2
    passed.append('multiple pages kept as compressed previews before recipe save')
    page.locator('#scanToForm').click()
    assert page.get_by_text('2 compressed scan photo(s)').count()==1
    page.locator('#f-save').click()
    page.wait_for_function('state.added.length===1')
    assert page.evaluate('state.added[0].photoIds.length')==2
    assert page.evaluate('window.__mockPhotoData.size')==2
    assert page.evaluate('window.__copies.length')==2
    passed.append('photo IDs saved on recipe; images persisted outside localStorage; Android bridge copies issued')
    page.locator('#q').fill('Pawpaw Pie')
    page.locator('[data-open]').click()
    page.wait_for_function("document.querySelectorAll('#recipePhotos img').length===2")
    assert page.locator('#recipePhotos img').count()==2
    assert page.locator('#recipePhotos [class=btn]').count()==2
    passed.append('saved recipe reopens with two photo thumbnails and photo download links')
    page.locator('[data-edit]').click()
    page.locator('#f-notes').fill('Excellent pie')
    page.locator('#f-save').click()
    page.wait_for_function("state.added[0].notes==='Excellent pie'")
    assert page.evaluate('state.added[0].photoIds.length')==2
    passed.append('editing recipe preserves existing attached photos')
    page.locator('#dataBtn').click()
    with page.expect_download() as d:
        page.locator('#backupBtn').click()
    backup=ROOT/'tests'/'photo-backup-test.json'
    d.value.save_as(backup)
    payload=json.loads(backup.read_text())
    assert payload['version']==1 and payload['format']=='reddirtcode-cookbook'
    ids=next(iter(payload['data']['recipes'].values()))['photoIds']
    assert set(ids)==set(payload['photos']) and len(ids)==2
    assert all(payload['photos'][i].startswith('data:image/jpeg;base64,') for i in ids)
    passed.append('full JSON backup includes compressed photo bytes and recipe associations')
    pg=ctx.new_page()
    pg.on('pageerror',lambda e:errors.append(str(e)))
    pg.evaluate((ROOT/'tests/mock_indexeddb.js').read_text())
    pg.evaluate("Object.defineProperty(window, 'localStorage', {value:{d:{}, getItem(k){return this.d[k]??null},setItem(k,v){this.d[k]=String(v)},removeItem(k){delete this.d[k]}}})")
    pg.set_content(FILE.read_text(),wait_until='domcontentloaded')
    pg.locator('#dataBtn').click()
    pg.locator('#backupFile').set_input_files(str(backup))
    pg.wait_for_function("document.querySelector('#restoreStatus').textContent.includes('2 photos')")
    pg.get_by_role('button',name='Replace device data from backup').click()
    pg.wait_for_function('state.added.length===1')
    assert pg.evaluate('window.__mockPhotoData.size')==2
    pg.locator('#q').fill('Pawpaw Pie')
    pg.locator('[data-open]').click()
    pg.wait_for_function("document.querySelectorAll('#recipePhotos img').length===2")
    passed.append('full photo backup restores recipes and both images into a fresh installation')
    pg.locator('[data-close]').first.click()
    pg.locator('#dataBtn').click()
    invalid=ROOT/'tests'/'photo-missing-test.json'
    broken=json.loads(backup.read_text());broken['photos'].pop(ids[0]);invalid.write_text(json.dumps(broken))
    pg.locator('#backupFile').set_input_files(str(invalid))
    pg.wait_for_function("document.querySelector('#restoreStatus').textContent.includes('missing recipe photo')")
    assert pg.locator('#restoreConfirm button').count()==0
    assert pg.evaluate('window.__mockPhotoData.size')==2
    passed.append('incomplete photo backup rejected before replacing any existing records')
    assert not errors,errors
    passed.append('zero uncaught browser exceptions during photo storage and restore')
    browser.close()
for n,p in enumerate(passed,1):print(f'PASS {n:02d}: {p}')
print(f'{len(passed)} photo storage checks passed')
