from pathlib import Path
import re
from PIL import Image,ImageDraw
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/'my-cookbook-alpha-0.2.3.html'
PHOTO=ROOT/'tests'/'test-recipe-card.png'
img=Image.new('RGB',(1100,850),'white')
d=ImageDraw.Draw(img)
d.text((90,90),'Okie Chili',fill='black')
d.text((90,140),'Ingredients',fill='black')
d.text((90,185),'2 cups pinto beans',fill='black')
d.text((90,230),'1 onion',fill='black')
d.text((90,290),'Directions',fill='black')
d.text((90,335),'Simmer beans 30 minutes',fill='black')
img.save(PHOTO)
passed=[]; errors=[]
with sync_playwright() as pw:
    b=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
    pg=b.new_page(viewport={'width':412,'height':915})
    pg.on('pageerror',lambda e: errors.append(str(e)))
    pg.route('**/cdnjs.cloudflare.com/**',lambda r:r.abort())
    pg.evaluate((ROOT/'tests'/'mock_indexeddb.js').read_text())
    pg.evaluate("Object.defineProperty(window, 'localStorage', {value:{d:{}, getItem(k){return this.d[k]??null},setItem(k,v){this.d[k]=String(v)},removeItem(k){delete this.d[k]}}})")
    pg.set_content(FILE.read_text(), wait_until='domcontentloaded')
    pg.locator('#addBtn').click()
    assert pg.get_by_role('button',name='Scan a recipe photo').count()==1
    pg.get_by_role('button',name='Scan a recipe photo').click()
    assert pg.locator('#scanCamera').get_attribute('capture')=='environment'
    assert pg.locator('#scanGallery').get_attribute('accept')=='image/*'
    passed.append('Add a recipe shows camera and gallery scan options')
    pg.evaluate('''window.Tesseract={createWorker: async()=>({recognize:async()=>({data:{text:"Okie Chili\\nIngredients\\n2 cups pinto beans\\n1 onion\\nDirections\\nSimmer beans 30 minutes"}}),terminate:async()=>{}})}''')
    pg.locator('#scanGallery').set_input_files(str(PHOTO))
    pg.wait_for_function("document.querySelector('#scanRaw').value.includes('Okie Chili')")
    assert '2 cups pinto beans' in pg.locator('#scanRaw').input_value()
    assert pg.locator('#scanToForm').is_enabled()
    passed.append('gallery image accepts text from browser OCR and enables review')
    # OCR second page accumulation + human corrections.
    pg.evaluate('''window.Tesseract={createWorker: async()=>({recognize:async()=>({data:{text:"Notes\\nServe warm"}}),terminate:async()=>{}})}''')
    pg.locator('#scanGallery').set_input_files(str(PHOTO))
    pg.wait_for_function("document.querySelector('#scanRaw').value.includes('Serve warm')")
    assert pg.locator('#scanRaw').input_value().count('Notes')==1
    pg.locator('#scanToForm').click()
    assert pg.locator('#f-title').input_value()=='Okie Chili'
    assert pg.locator('#f-ing').input_value()=='2 cups pinto beans\n1 onion'
    assert pg.locator('#f-steps').input_value()=='Simmer beans 30 minutes'
    assert 'Serve warm' in pg.locator('#f-notes').input_value()
    passed.append('multiple photo pages parse into title, ingredients, steps, notes')
    # no autosave until explicit Save; verifies review-first promise.
    assert pg.locator('.card').count()==180
    pg.locator('#f-save').click()
    pg.wait_for_function("document.querySelectorAll('.card').length===181")
    passed.append('scan review requires explicit save, then persists new recipe')
    pg.locator('#addBtn').click()
    pg.get_by_role('button',name='Scan a recipe photo').click()
    pg.locator('#scanRaw').fill('Grandma Pie\n2 apples\nBake for 30 minutes')
    pg.locator('#scanToForm').click()
    assert pg.locator('#f-title').input_value()=='Grandma Pie'
    assert pg.locator('#f-ing').input_value()==''
    assert '2 apples' in pg.locator('#f-notes').input_value()
    passed.append('unstructured scans retain uncertain text in notes, not fabricated ingredient fields')
    pg.locator('[data-close]').first.click()
    # Android bridge simulation: image processed in native bridge, not browser OCR.
    pg.evaluate('''window.CookbookAndroid={scanImageBase64:(id,encoded)=>{
        window.__nativeScans=(window.__nativeScans||0)+1;
        window.CookbookRecipeScan.receive(id,"Apple Tart\\nIngredients\\n1 apple\\nDirections\\nSlice apple","");
    }}''')
    pg.locator('#addBtn').click()
    pg.get_by_role('button',name='Scan a recipe photo').click()
    pg.locator('#scanCamera').set_input_files(str(PHOTO))
    pg.wait_for_function("document.querySelector('#scanRaw').value.includes('Apple Tart')")
    assert pg.evaluate('window.__nativeScans')==1
    passed.append('Android bridge callback reads photo without browser OCR')
    pg.locator('[data-close]').first.click()
    # Empty/no text result should not create a recipe.
    pg.evaluate('delete window.CookbookAndroid; window.Tesseract={createWorker:async()=>({recognize:async()=>({data:{text:""}}),terminate:async()=>{}})}')
    pg.locator('#addBtn').click()
    pg.get_by_role('button',name='Scan a recipe photo').click()
    pg.locator('#scanGallery').set_input_files(str(PHOTO))
    pg.wait_for_function("document.querySelector('#scanStatus').textContent.includes('No text found')")
    assert pg.locator('#scanToForm').is_disabled()
    passed.append('empty OCR result reports error without saving')
    assert not errors,errors
    passed.append('no uncaught browser errors during scanning flow')
    b.close()
for i,item in enumerate(passed,1):print(f'PASS {i:02d}: {item}')
print(f'{len(passed)} scan tests passed')
