// Test-only storage shim for Playwright's opaque about:blank origin.
// Production uses the browser's real IndexedDB on its HTTP(S) / appassets origin.
window.__mockPhotoData=window.__mockPhotoData||new Map();
Object.defineProperty(window,"indexedDB",{configurable:true,value:{open(){
 const request={result:null,onupgradeneeded:null,onsuccess:null,onerror:null};
 const db={objectStoreNames:{contains:()=>true},createObjectStore:()=>{},
   transaction(name,mode){
     const tx={oncomplete:null,onabort:null};
     tx.objectStore=()=>({
       put(data,id){return doRequest(()=>{window.__mockPhotoData.set(id,data);return id})},
       get(id){return doRequest(()=>window.__mockPhotoData.get(id))},
       delete(id){return doRequest(()=>window.__mockPhotoData.delete(id))}
     });
     function doRequest(fn){
       const result={onsuccess:null,onerror:null};
       setTimeout(()=>{
         try{result.result=fn();result.onsuccess?.();setTimeout(()=>tx.oncomplete?.(),0)}
         catch(e){result.error=e;result.onerror?.()}
       },0);
       return result;
     }
     return tx;
   }
 };
 setTimeout(()=>{request.result=db;request.onupgradeneeded?.();request.onsuccess?.()},0);
 return request;
}}});
