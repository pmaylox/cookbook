const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");

const source=fs.readFileSync("recipe-link-import.js","utf8");
const androidSource=fs.readFileSync("app/src/main/assets/recipe-link-import.js","utf8");
assert.equal(source,androidSource,"Browser and APK parser copies must match");

const outgoing=[];
const ctx=vm.createContext({window:{CookbookAndroid:{fetchRecipeSchema:(id,url)=>outgoing.push({id,url})}},fetch:()=>{throw Error("Do not fetch in Android bridge test")}});
vm.runInContext(source,ctx);
const link=vm.runInContext("CookbookRecipeLinkImport",ctx);
const schema={"@context":"https://schema.org","@type":"Recipe",name:"Grandma's Cornbread",recipeIngredient:["1 &frac12; cups cornmeal","1 cup flour"],recipeInstructions:[{"@type":"HowToStep",text:"Mix dry ingredients."},{"@type":"HowToStep",text:"Bake at 400 F."}],recipeYield:"8",prepTime:"PT15M",cookTime:"PT25M"};
const graph={"@context":"https://schema.org","@graph":[{"@type":"WebPage",name:"Example"},{"@type":["CreativeWork","https://schema.org/Recipe"],name:"Beef Stew",recipeIngredient:["2 lb beef"],recipeInstructions:[{"@type":"HowToSection",itemListElement:[{"@type":"HowToStep",text:"Brown beef."},{"@type":"HowToStep",text:"Simmer for 2 hours."}]}]}]};
const parsed=link.parseSchemaBlocks([JSON.stringify(schema)],"https://example.com/cornbread");
assert.equal(parsed.title,"Grandma's Cornbread");
assert.deepEqual(Array.from(parsed.ingredients),["1 ½ cups cornmeal","1 cup flour"]);
assert.deepEqual(Array.from(parsed.steps),["Mix dry ingredients.","Bake at 400 F."]);
assert.equal(parsed.servings,"8");
assert.equal(parsed.time,"Prep 15 min, Cook 25 min");
const graphParsed=link.parseSchemaBlocks([JSON.stringify(graph)],"https://example.com/stew");
assert.equal(graphParsed.title,"Beef Stew");
assert.equal(graphParsed.steps.length,2);
assert.equal(link.parseSchemaBlocks([JSON.stringify({"@type":"WebPage"})],"https://example.com"),null);
const blocks=link.schemaBlocksFromHtml('<script type="application/ld+json">'+JSON.stringify(schema)+'</script><script>throw Error("not executed")</script>');
assert.equal(blocks.length,1);
assert.equal(link.parseSchemaBlocks(blocks,"https://example.com/cornbread").ingredients.length,2);
const htmlSteps=link.parseSchemaBlocks([JSON.stringify({"@type":"Recipe",name:"Cake",recipeIngredient:["Flour"],recipeInstructions:"<ol><li>Stir.</li><li>Bake.</li></ol>"})],"https://example.com/cake");
assert.deepEqual(Array.from(htmlSteps.steps),["Stir.","Bake."]);

let response=null,error=null;
const id=link.importUrl("https://example.com/cornbread",data=>response=data,msg=>error=msg);
assert.equal(outgoing.length,1);
assert.equal(outgoing[0].id,id);
ctx.window.CookbookRecipeImport.receive(id,JSON.stringify([JSON.stringify(schema)]),"");
assert.equal(response.title,"Grandma's Cornbread");
assert.equal(response.ingredients.length,2);
assert.equal(error,null);

response=null;error=null;
const blocked=link.importUrl("https://example.com/blocked",data=>response=data,msg=>error=msg);
ctx.window.CookbookRecipeImport.receive(blocked,"[]","Website blocked access");
assert.equal(response,null);
assert.equal(error,"Website blocked access");

response=null;error=null;
const stale=link.importUrl("https://example.com/stale",data=>response=data,msg=>error=msg);
link.cancel();
ctx.window.CookbookRecipeImport.receive(stale,JSON.stringify([JSON.stringify(schema)]),"");
assert.equal(response,null);
assert.equal(error,null);
const browser=fs.readFileSync("my-cookbook-alpha-0.2.5.html","utf8");
const android=fs.readFileSync("app/src/main/assets/index.html","utf8");
assert.equal(browser,android,"Bundled and browser HTML must match");
assert(browser.includes('<script src="recipe-link-import.js"></script>'));
assert(browser.includes('CookbookRecipeLinkImport.importUrl(u'));
assert(android.includes('My Cookbook · Alpha 0.2.6'));
console.log("PASS: JSON-LD recipe parsing, section steps, encoded measurements, missing metadata, Android bridge, errors, cancel, synchronized HTML.");
