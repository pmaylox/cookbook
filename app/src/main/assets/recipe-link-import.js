/* My Cookbook Alpha 0.2.6: recipe website import.
   Parse schema.org Recipe JSON-LD; never execute remote page scripts.
   Android retrieves metadata on demand through the native HTTPS bridge.
   Ordinary browsers can import only sites which permit CORS. */
const CookbookRecipeLinkImport=(()=>{
  let sequence=0, pending=null;
  const entities={amp:"&",lt:"<",gt:">",quot:'"',apos:"'",nbsp:" ",deg:"°",frac12:"½",frac14:"¼",frac34:"¾",ndash:"–",mdash:"—",rsquo:"’"};
  const decode=s=>s.replace(/&(#x[0-9a-f]+|#\d+|[a-z][a-z0-9]+);/gi,(all,key)=>{
    const k=key.toLowerCase();
    if(k[0]==="#"){
      const n=k[1]==="x"?parseInt(k.slice(2),16):parseInt(k.slice(1),10);
      return Number.isFinite(n)&&n>0&&n<=0x10ffff&&!(n>=0xd800&&n<=0xdfff)?String.fromCodePoint(n):all;
    }
    return Object.prototype.hasOwnProperty.call(entities,k)?entities[k]:all;
  });
  function tidy(value){
    if(value==null)return "";
    if(typeof value==="object")value=value.text??value.name??value.value??value.description??"";
    return decode(String(value).replace(/<br\s*\/?>/gi,"\n").replace(/<\/(?:p|li|div|h[1-6])>/gi,"\n").replace(/<[^>]+>/g," "))
      .replace(/\u00a0/g," ").replace(/[ \t]+/g," ").replace(/\s*\n\s*/g,"\n").trim();
  }
  function instructionLines(value){
    if(value==null)return [];
    if(Array.isArray(value))return value.flatMap(instructionLines);
    if(typeof value==="object"){
      if(value.itemListElement)return instructionLines(value.itemListElement);
      if(value.steps)return instructionLines(value.steps);
      if(value.step)return instructionLines(value.step);
      return instructionLines(value.text??value.description??value.name??"");
    }
    const raw=String(value);
    const list=[...raw.matchAll(/<li\b[^>]*>([\s\S]*?)<\/li>/gi)].map(m=>tidy(m[1])).filter(Boolean);
    if(list.length)return list;
    return tidy(raw).split(/\n+/).map(s=>s.replace(/^\s*(?:\d+[.)]|[-•*])\s*/,"").trim()).filter(Boolean);
  }
  function formatDuration(v){
    if(v==null||v==="")return "";
    const input=tidy(v);
    const m=/^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$/i.exec(input);
    if(!m)return input;
    const out=[];
    if(+m[1])out.push(+m[1]+" day"+(+m[1]===1?"":"s"));
    if(+m[2])out.push(+m[2]+" hr");
    if(+m[3])out.push(+m[3]+" min");
    if(+m[4])out.push(+m[4]+" sec");
    return out.join(" ")||input;
  }
  function toRecipe(node,source){
    const rawIngredients=node.recipeIngredient??node.ingredients??[];
    const ingredients=(Array.isArray(rawIngredients)?rawIngredients:[rawIngredients]).map(tidy).filter(Boolean);
    const steps=instructionLines(node.recipeInstructions??node.instructions??[]);
    const rawYield=node.recipeYield??node.yield??"";
    const servings=tidy(Array.isArray(rawYield)?rawYield[0]:rawYield);
    const times=[["Prep",node.prepTime],["Cook",node.cookTime],["Total",node.totalTime]]
      .filter(([,v])=>v!=null&&v!=="").map(([label,v])=>label+" "+formatDuration(v)).join(", ");
    return {title:tidy(node.name??node.headline??""),ingredients,steps,servings,time:times,source};
  }
  function isRecipe(node){
    const types=Array.isArray(node?.["@type"])?node["@type"]:[node?.["@type"]];
    return types.some(type=>typeof type==="string"&&type.split(/[\/#]/).pop().toLowerCase()==="recipe");
  }
  function parseSchemaBlocks(blocks,source){
    let found=null,visited=0;
    function visit(node,depth){
      if(found||depth>10||++visited>12000||!node||typeof node!=="object")return;
      if(Array.isArray(node)){for(const n of node)visit(n,depth+1);return}
      if(isRecipe(node)){found=node;return}
      for(const [k,v] of Object.entries(node)){
        if(k==="recipeInstructions"||k==="recipeIngredient")continue;
        if(v&&typeof v==="object")visit(v,depth+1);
      }
    }
    for(const block of blocks||[]){
      try{visit(typeof block==="string"?JSON.parse(block):block,0)}catch(_){}
      if(found)break;
    }
    return found?toRecipe(found,source):null;
  }
  function schemaBlocksFromHtml(html){
    const blocks=[];
    const re=/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi;
    let match;
    while((match=re.exec(html))&&blocks.length<40){
      if(/\btype\s*=\s*["']?application\/ld\+json(?=["'\s>]|$)/i.test(match[1]))blocks.push(match[2].trim());
    }
    return blocks;
  }
  function complete(requestId,blocks,error){
    if(!pending||pending.id!==requestId)return;
    const current=pending;pending=null;
    if(error){current.onError(error);return}
    const recipe=parseSchemaBlocks(blocks,current.url);
    if(!recipe||(!recipe.ingredients.length&&!recipe.steps.length)){
      current.onError("This website did not provide readable recipe ingredients or directions. You can save the link and enter them manually.");
      return;
    }
    current.onSuccess(recipe);
  }
  function importUrl(url,onSuccess,onError){
    const id="link-"+(++sequence);
    pending={id,url,onSuccess,onError};
    if(window.CookbookAndroid?.fetchRecipeSchema){
      try{window.CookbookAndroid.fetchRecipeSchema(id,url)}
      catch(_){complete(id,[],"The Android recipe importer could not start. You can still save the link manually.")}
    }else{
      fetch(url,{method:"GET",mode:"cors",credentials:"omit",redirect:"follow"})
        .then(r=>{if(!r.ok)throw Error("Website returned "+r.status);return r.text()})
        .then(html=>complete(id,schemaBlocksFromHtml(html),""))
        .catch(()=>complete(id,[],"This browser or website blocked recipe import. The Android app can try a direct import; otherwise save the link manually."));
    }
    return id;
  }
  function receive(requestId,json,error){
    if(error){complete(requestId,[],error);return}
    let blocks;
    try{blocks=JSON.parse(json)}catch(_){complete(requestId,[],"The website returned unreadable recipe metadata.");return}
    complete(requestId,blocks,"");
  }
  function cancel(){pending=null}
  return {importUrl,receive,cancel,parseSchemaBlocks,schemaBlocksFromHtml,toRecipe};
})();
window.CookbookRecipeImport={receive:CookbookRecipeLinkImport.receive};
