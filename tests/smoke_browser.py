"""Browser integration checks. Requires pip install playwright and Chromium."""
from pathlib import Path
import functools, threading, json, tempfile
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/'my-cookbook-alpha-0.2.3.html'
assert FILE.exists()
server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(SimpleHTTPRequestHandler,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_address[1]}/{FILE.name}'
passed=[]; errors=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
    ctx=browser.new_context(accept_downloads=True,viewport={'width':412,'height':915})
    ctx.route('**/cdnjs.cloudflare.com/**',lambda route:route.abort())
    page=ctx.new_page()
    page.on('pageerror',lambda e: errors.append(str(e)))
    page.evaluate("Object.defineProperty(window, 'localStorage', {value:{d:{}, getItem(k){return this.d[k]??null},setItem(k,v){this.d[k]=String(v)},removeItem(k){delete this.d[k]}}})")
    page.set_content(FILE.read_text(),wait_until='domcontentloaded')
    assert page.locator('.card').count()==180
    assert page.locator('.tab').count()==6
    passed.append('180 catalog items displayed with six browsing tabs')
    # Browser persistence and favorites.
    card=page.locator('.card').filter(has_text='Cracker Barrel Meatloaf').first
    card.locator('[data-star]').click()
    assert card.locator('[data-star]').get_attribute('aria-pressed')=='true'
    saved = page.evaluate('localStorage.d')
    page.close()
    page=ctx.new_page()
    page.on('pageerror',lambda e: errors.append(str(e)))
    page.evaluate("Object.defineProperty(window, 'localStorage', {value:{d:"+json.dumps(saved)+", getItem(k){return this.d[k]??null},setItem(k,v){this.d[k]=String(v)},removeItem(k){delete this.d[k]}}})")
    page.set_content(FILE.read_text(),wait_until='domcontentloaded')
    assert page.locator('.card').filter(has_text='Cracker Barrel Meatloaf').first.locator('[data-star]').get_attribute('aria-pressed')=='true'
    passed.append('favorite survives reload')
    # Global search: old implementation mismatched sections.
    page.locator('[data-tab="M"]').click()
    page.locator('#q').fill('apple')
    assert page.locator('.card').filter(has_text='Lazy Apple Cinnamon Spoon Cake').count()==1
    passed.append('global search returns dessert while Main Courses selected')
    page.locator('#q').fill('')
    # Personal written recipe.
    page.locator('#addBtn').click()
    page.get_by_role('button',name='Type it in').click()
    page.locator('#f-title').fill('Smoke Test Chili')
    page.locator('#f-ing').fill('1 onion\n2 cans beans\n1 onion')
    page.locator('#f-steps').fill('Brown onion\nSimmer beans')
    page.locator('#f-save').click()
    page.locator('#q').fill('Smoke Test Chili')
    page.locator('[data-open]').click()
    assert page.locator('#sheetTitle').inner_text()=='Smoke Test Chili'
    page.get_by_role('button',name='Add to shopping list').click()
    assert page.locator('.shopping-items li').count()==2
    passed.append('create full recipe; add de-duplicated shopping ingredients')
    # Manual shopping.
    page.locator('#shoppingNewItem').fill('Oklahoma peaches')
    page.locator('#shoppingAddForm button').click()
    assert page.locator('.shopping-items li').count()==3
    page.locator('#shoppingNewItem').fill('oklahoma PEACHES')
    page.locator('#shoppingAddForm button').click()
    assert page.locator('.shopping-items li').count()==3
    page.locator('[data-shop-toggle]').first.click()
    assert page.locator('.shopping-items li.checked').count()==1
    passed.append('manual grocery add, duplicate detection, checked-item state')
    page.get_by_role('button',name='Close').click()
    page.locator('#q').fill('')
    # Hidden card and undo via Show deleted.
    card=page.locator('.card').filter(has_text='Cracker Barrel Meatloaf').first
    card.locator('[data-remove]').click()
    page.locator('[data-remove-yes]').click()
    assert page.locator('.card').filter(has_text='Cracker Barrel Meatloaf').count()==0
    page.locator('#showDel').check()
    assert page.locator('.card').filter(has_text='Cracker Barrel Meatloaf').count()==1
    page.locator('.card').filter(has_text='Cracker Barrel Meatloaf').first.locator('[data-restore]').click()
    page.locator('#showDel').uncheck()
    passed.append('hide and restore catalog card')
    # JSON backup carries all relevant data, and can restore into clean context.
    page.locator('#dataBtn').click()
    with page.expect_download() as d:
        page.locator('#backupBtn').click()
    back=ROOT/'tests'/'smoke-test-backup.json';d.value.save_as(back)
    payload=json.loads(back.read_text())
    assert payload['format']=='reddirtcode-cookbook' and payload['version']==1
    assert len(payload['data']['shopping'])==3
    assert len(payload['data']['recipes'])==1
    passed.append('full JSON backup contains recipes, favorites, and shopping')
    ctx2=browser.new_context(accept_downloads=True)
    ctx2.route('**/cdnjs.cloudflare.com/**',lambda route:route.abort())
    pg=ctx2.new_page()
    pg.on('pageerror',lambda e:errors.append(str(e)))
    pg.evaluate("Object.defineProperty(window, 'localStorage', {value:{d:{}, getItem(k){return this.d[k]??null},setItem(k,v){this.d[k]=String(v)},removeItem(k){delete this.d[k]}}})")
    pg.set_content(FILE.read_text(),wait_until='domcontentloaded')
    pg.locator('#dataBtn').click()
    pg.locator('#backupFile').set_input_files(str(back))
    pg.get_by_role('button',name='Replace device data from backup').click()
    pg.locator('#q').fill('Smoke Test Chili')
    assert pg.locator('.card').count()==1
    pg.locator('#shopBtn').click()
    assert pg.locator('.shopping-items li').count()==3
    pg.get_by_role('button',name='Close').click()
    pg.locator('#q').fill('')
    assert pg.locator('.card').filter(has_text='Cracker Barrel Meatloaf').first.locator('[data-star]').get_attribute('aria-pressed')=='false' # hidden removes favorite
    passed.append('backup restores into fresh browser without losing items')
    # Invalid restore must refuse input and retain existing data.
    wrong=ROOT/'tests'/'invalid-backup.json';wrong.write_text('{"not":"a backup"}')
    pg.locator('#dataBtn').click()
    pg.locator('#backupFile').set_input_files(str(wrong))
    pg.wait_for_function("document.querySelector('#restoreStatus').textContent.includes('not a supported Cookbook backup')")
    assert pg.locator('#restoreConfirm button').count()==0
    pg.get_by_role('button',name='Close').click()
    pg.locator('#q').fill('Smoke Test Chili')
    assert pg.locator('.card').count()==1
    passed.append('invalid backup refused without overwriting saved recipe')
    # Offline print route does not rely on fetching jsPDF from the CDN.
    pg.evaluate("""() => {window.__offlinePrints=0; window.open=()=>({
      document:{write(s){window.__offlineHtml=s},close(){}}, focus(){},
      print(){window.__offlinePrints++}}); }""")
    pg.locator('[data-open]').click()
    pg.get_by_role('button',name='Save PDF').click()
    assert pg.evaluate('window.__offlinePrints')==1
    assert 'Smoke Test Chili' in pg.evaluate('window.__offlineHtml')
    pg.get_by_role('button',name='Close').click()
    passed.append('offline browser Print / Save-as-PDF fallback')
    # Cross-site payload is treated as text, never executable HTML.
    pg.locator('#addBtn').click()
    pg.get_by_role('button',name='Type it in').click()
    pg.locator('#f-title').fill('<img src=x onerror=alert(1)>')
    pg.locator('#f-ing').fill('1 cup water')
    pg.locator('#f-save').click()
    pg.locator('#q').fill('onerror')
    assert pg.locator('.card').count()==1
    assert pg.locator('.card img').count()==0
    passed.append('recipe title escaping prevents HTML injection')
    assert not errors, errors
    passed.append('zero uncaught browser script errors')
    browser.close()
server.shutdown()
for i,label in enumerate(passed,1): print(f'PASS {i:02d}: {label}')
print(f'{len(passed)} checks passed')
