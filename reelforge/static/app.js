"use strict";
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const params = new URLSearchParams(location.hash.slice(1));
let token = params.get("token") || sessionStorage.getItem("reelforge-token") || "";
if (token) sessionStorage.setItem("reelforge-token", token);
history.replaceState(null, "", location.pathname);
let items=[], selected=new Set(), previews=new Map(), selectedPreview=[], mode="playlist", demo=false, scanning=false, editId=null, folderParent="", currentFolder="", previewVersion=0, previewTimer=null, dead=false, busyQueue=false, researching=false;
const ruleIds=["root","show","preset","template","title-regex","container","quality","stitch","collection","combine","combined-title"];
async function api(path, body) {
  const response=await fetch("/api/"+path,{method:body===undefined?"GET":"POST",headers:{"X-ReelForge-Token":token,"Content-Type":"application/json"},body:body===undefined?undefined:JSON.stringify(body)});
  if(!response.ok){let data;try{data=await response.json();}catch{data={detail:response.statusText};}if(response.status===401)dead=true;throw Error(typeof data.detail==="string"?data.detail:JSON.stringify(data.detail));}
  return response.json();
}
function notice(id,text,error=false){const el=$(id);el.textContent=text;el.hidden=!text;el.classList.toggle("error",error);}
let toastTimer;
function toast(text){$("toast").textContent=text;$("toast").hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$("toast").hidden=true,5000);}
function showView(view){document.querySelectorAll(".view").forEach(el=>el.hidden=el.id!==view);document.querySelectorAll(".nav").forEach(el=>el.classList.toggle("active",el.dataset.view===view));$("view-label").textContent={ingest:"Import & organize",queue:"Download queue",setup:"Setup & about",help:"Help & guide"}[view];if(view==="help")window.scrollTo(0,0);}
document.querySelectorAll("[data-view]").forEach(el=>el.addEventListener("click",()=>showView(el.dataset.view)));
function setMode(next){mode=next;document.querySelectorAll(".source-tab").forEach(el=>{el.classList.toggle("active",el.dataset.mode===mode);el.setAttribute("aria-selected",String(el.dataset.mode===mode));});$("url-fields").hidden=!["playlist","website","records"].includes(mode);$("website-fields").hidden=mode!=="website";$("records-fields").hidden=mode!=="records";$("manifest-fields").hidden=mode!=="manifest";}
document.querySelectorAll("[data-mode]").forEach(el=>el.addEventListener("click",()=>setMode(el.dataset.mode)));
function rules(){return {root:$("root").value,show:$("show").value,preset:$("preset").value,template:$("template").value,title_regex:$("title-regex").value,container:$("container").value,quality:$("quality").value,stitch:$("stitch").value};}
function chosen(){return items.filter(i=>selected.has(i.id));}
function effectiveItems(){const selection=chosen();if(!$("combine").checked||!selection.length)return selection;return [{...selection[0],title:$("combined-title").value,filename:$("combined-title").value,parts:selection.flatMap(i=>i.parts?.length?i.parts:[i.url]),referer:""}];}
function visible(){const include=$("search").value.toLowerCase(),exclude=$("exclude").value.toLowerCase(),min=Number($("min-duration").value)*60;return items.filter(i=>i.title.toLowerCase().includes(include)&&(!exclude||!i.title.toLowerCase().includes(exclude))&&(!min||(i.duration!=null&&i.duration>=min))&&(typeof dateVisible!=="function"||dateVisible(i)));}
function duration(seconds){return seconds==null?"Duration unknown":Math.floor(seconds/60)+"m "+Math.floor(seconds%60)+"s";}
function render(){
 const rows=visible();$("result-count").textContent=items.length;$("selected-count").textContent=selected.size+" selected";$("empty").hidden=items.length>0;
 $("export-manifest").disabled=!items.length;
 $("results").innerHTML=rows.map(i=>{const p=previews.get(i.id);return '<div class="video-row"><input type="checkbox" data-select="'+esc(i.id)+'" aria-label="Select '+esc(i.title)+'" '+(selected.has(i.id)?"checked":"")+'><div class="video-info"><div class="video-title">'+esc(i.title)+'</div><div class="video-meta">#'+esc(i.index)+' · '+esc(duration(i.duration))+(i.parts?.length?' · '+i.parts.length+' parts':'')+'</div>'+(typeof dateRow==='function'?dateRow(i):'')+'<div class="video-path '+(p?.error?"error":p?.exists?"existing":"")+'">'+esc(p?.error||(p?.relative?((p.exists?"EXISTS · ":"")+p.relative):"Calculating filename…"))+'</div></div><button class="text-button" data-date="'+esc(i.id)+'">Dates</button><button class="text-button" data-edit="'+esc(i.id)+'">Edit</button></div>';}).join("");
 if(items.length&&!rows.length)$("results").innerHTML='<div class="empty"><h3>No matching videos.</h3><p>Adjust your filters. Hidden videos remain selected until you clear them.</p></div>';
 $("select-all").checked=rows.length>0&&rows.every(i=>selected.has(i.id));$("select-all").indeterminate=rows.some(i=>selected.has(i.id))&&!$("select-all").checked;
 $("show-field").hidden=$("preset").value!=="episodes";$("template-field").hidden=$("preset").value!=="custom";$("combine-fields").hidden=!$("combine").checked;
 const errors=selectedPreview.some(p=>p.error);
 $("first-preview").textContent=selectedPreview[0]?.error||selectedPreview[0]?.relative||"Your filename preview appears here.";
 $("queue-selected").disabled=busyQueue||!selected.size||errors||!selectedPreview.length||demo||scanning||researching;
 if(typeof dateControls==="function")dateControls();
 $("queue-selected").textContent=demo?"Sample preview · replace source URLs":busyQueue?"Adding jobs…":$("combine").checked?"Queue joined video ↓":"Queue "+selected.size+" selected ↓";
}
function saveRules(){const saved={};ruleIds.forEach(id=>saved[id]=$(id).type==="checkbox"?$(id).checked:$(id).value);localStorage.setItem("reelforge-rules",JSON.stringify(saved));}
async function preview(){
 const revision=++previewVersion;render();if(!items.length)return;
 try{
   const selection=effectiveItems();
   const requests=[api("preview",{items:items.map(i=>({...i,collection:$("collection").value})),rules:rules()}),selection.length?api("preview",{items:selection.map(i=>({...i,collection:$("collection").value})),rules:rules()}):Promise.resolve({rows:[]})];
   const [all,selectedResult]=await Promise.all(requests);
   if(revision!==previewVersion)return;
   previews=new Map(all.rows.map(p=>[p.item.id,p]));selectedPreview=selectedResult.rows;
   // Show resolved season/episode metadata in the editor without rewriting source titles.
   all.rows.forEach(p=>{const original=items.find(i=>i.id===p.item.id);if(original){original.season=p.item.season;original.episode=p.item.episode;}});
   selectedResult.rows.forEach(p=>{if(!$("combine").checked)previews.set(p.item.id,p);});
   notice("queue-feedback","");render();
 }catch(e){if(revision!==previewVersion)return;selectedPreview=[];notice("queue-feedback",e.message,true);render();}
}
function schedulePreview(){selectedPreview=[];$("queue-selected").disabled=true;saveRules();clearTimeout(previewTimer);previewTimer=setTimeout(preview,220);render();}
ruleIds.forEach(id=>$(id).addEventListener("input",schedulePreview));
["search","exclude","min-duration"].forEach(id=>$(id).addEventListener("input",render));
$("select-all").addEventListener("change",()=>{visible().forEach(i=>$("select-all").checked?selected.add(i.id):selected.delete(i.id));schedulePreview();});
$("clear-selection").addEventListener("click",()=>{selected.clear();schedulePreview();});
$("results").addEventListener("change",e=>{const id=e.target.dataset.select;if(id){e.target.checked?selected.add(id):selected.delete(id);schedulePreview();}});
$("results").addEventListener("click",e=>{const id=e.target.dataset.edit;if(!id)return;const item=items.find(i=>i.id===id);editId=id;["title","url","season","episode","index","filename","subfolder"].forEach(field=>$("edit-"+field).value=item[field]??"");$("edit-parts").value=(item.parts||[]).join("\n");$("edit-dialog").showModal();});
$("edit-form").addEventListener("submit",e=>{
 if(e.submitter?.value!=="save")return;
 const item=items.find(i=>i.id===editId);
 const oldTitle=item.title,oldUrl=item.url;
 ["title","url","filename","subfolder"].forEach(field=>item[field]=$("edit-"+field).value);
 ["season","episode","index"].forEach(field=>item[field]=$("edit-"+field).value===""?null:Number($("edit-"+field).value));
 if(item.title!==oldTitle||item.url!==oldUrl)item.dating={confidence:"unknown",evidence:[],notes:["Source title or URL changed; research again."],reviewed:false};
 if(item.url!==oldUrl){item.description="";item.upload_date="";}
 item.parts=$("edit-parts").value.split("\n").map(s=>s.trim()).filter(Boolean);
 demo=items.some(i=>(i.parts?.length?i.parts:[i.url]).some(url=>new URL(url).hostname==="example.com"));
 schedulePreview();
});
async function scanSource(isDemo=false){
 if(scanning||researching)return;
 if(!isDemo&&typeof demoDateReferences!=="undefined")demoDateReferences=null;
 scanning=true;selectedPreview=[];render();notice("scan-feedback","Reading the source… Large playlists can take a few minutes.");
 ["scan","scan-manifest","demo"].forEach(id=>$(id).disabled=true);
 const req={mode,url:$("source-url").value,collection:$("collection").value,depth:Number($("depth").value),link_contains:$("link-filter").value,records_path:$("records-path").value,url_field:$("record-url").value,title_field:$("record-title").value,season_field:$("record-season").value,episode_field:$("record-episode").value,year_field:$("record-year").value,filename_field:$("record-filename").value,subfolder_field:$("record-subfolder").value,base_url:$("record-base").value,manifest:$("manifest").value,limit:500};
 try{
  const start=await api("scans",req);let result;
  do{await new Promise(resolve=>setTimeout(resolve,500));result=await api("scans/"+start.id);}while(result.state==="running");
  if(result.state==="failed")throw Error(result.error);
  items=result.items;selected=new Set(items.map(i=>i.id));previews.clear();
  if(items[0]?.collection&&$("collection").value==="Collection")$("collection").value=items[0].collection;
  demo=isDemo||items.some(i=>(i.parts?.length?i.parts:[i.url]).some(url=>new URL(url).hostname==="example.com"));
  notice("scan-feedback",isDemo?"Sample metadata loaded. URLs are placeholders; replace them before downloading.":items.length+" videos found."+(result.warnings.length?"\n"+result.warnings.join("\n"):""));
  if($("preset").value==="episodes"){const temp=await api("preview",{items,rules:rules()});const byId=new Map(temp.rows.map(p=>[p.item.id,p.item]));items.sort((a,b)=>(byId.get(a.id).season??9999)-(byId.get(b.id).season??9999)||(byId.get(a.id).episode??9999)-(byId.get(b.id).episode??9999));}
 }catch(e){notice("scan-feedback",e.message,true);}finally{scanning=false;["scan","scan-manifest","demo"].forEach(id=>$(id).disabled=false);await preview();}
}
["scan","scan-manifest"].forEach(id=>$(id).addEventListener("click",()=>scanSource()));
const sample=[
 {url:"https://example.com/reelforge-demo/episode-1.mp4",title:"Morning Landscape (Season 1 Episode 1)",duration:1680},
 {url:"https://example.com/reelforge-demo/episode-2.mp4",title:"Mountain Trail (Season 1 Episode 2)",duration:1680},
 {url:"https://example.com/reelforge-demo/episode-3.mp4",title:"Evening Harbor (Season 1 Episode 3)",duration:1680},
 {url:"https://example.com/reelforge-demo/episode-4.mp4",title:"Winter Walk (Season 1 Episode 4)",duration:1680}
];
$("demo").addEventListener("click",()=>{setMode("manifest");$("manifest").value=JSON.stringify(sample,null,2);$("collection").value="Sample Series";$("show").value="Sample Series";$("preset").value="episodes";scanSource(true);});
$("manifest-file").addEventListener("change",async e=>{const file=e.target.files[0];if(!file)return;if(file.size>2*1024*1024){toast("Manifest is too large; use a file under 2 MB.");return;}$("manifest").value=await file.text();toast("Manifest opened. Click Read manifest to review it.");});
function downloadBlob(blob,name){const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$("export-manifest").addEventListener("click",()=>{const output=items.map(i=>{const p=previews.get(i.id);return {...i,season:p?.item.season??i.season,episode:p?.item.episode??i.episode};});downloadBlob(new Blob([JSON.stringify(output,null,2)],{type:"application/json"}),"reelforge-manifest.json");});
$("queue-selected").addEventListener("click",async()=>{
 if(busyQueue||demo||!selectedPreview.length)return;
 busyQueue=true;render();
 try{const result=await api("queue",{items:chosen().map(i=>({...i,collection:$("collection").value})),rules:rules(),combine:$("combine").checked,combined_title:$("combined-title").value});const added=result.jobs.filter(j=>j.added).length;toast(added+" jobs queued"+(result.jobs.length>added?" · existing queue entries kept":""));showView("queue");await refreshQueue();}
 catch(e){notice("queue-feedback",e.message,true);}finally{busyQueue=false;render();}
});
async function refreshQueue(){
 if(dead)return;
 try{
 const result=await api("queue");const jobs=result.jobs;
 $("queue-count").textContent=jobs.filter(j=>["queued","running","merging"].includes(j.state)).length;
 $("stat-active").textContent=jobs.filter(j=>["queued","running","merging"].includes(j.state)).length;
 $("stat-completed").textContent=jobs.filter(j=>j.state==="completed").length;
 $("stat-review").textContent=jobs.filter(j=>["failed","paused"].includes(j.state)).length;
 $("queue-empty").hidden=!!jobs.length;
 $("jobs").innerHTML=jobs.map(j=>{
 const buttons=["queued","running","merging"].includes(j.state)?["pause","cancel"]:["paused","failed","cancelled"].includes(j.state)?[j.state==="failed"?"retry":"resume",...(j.state==="cancelled"?[]:["cancel"])]:[];
 return '<article class="job"><div class="job-top"><h3>'+esc(j.payload.item.title)+'</h3><span class="badge '+esc(j.state)+'">'+esc(j.state)+'</span></div><div class="job-target">'+esc(j.payload.target)+'</div><div class="progress-track"><div class="progress-fill" data-progress="'+Number(j.progress)+'"></div></div><div class="job-detail"><span>'+Math.round(j.progress)+'% · '+esc(j.detail)+'</span><div class="job-actions">'+buttons.map(action=>'<button class="text-button" data-job="'+esc(j.id)+'" data-action="'+action+'">'+action[0].toUpperCase()+action.slice(1)+'</button>').join("")+'</div></div>'+(j.error?'<details><summary class="text-button">Error details</summary><pre class="job-error">'+esc(j.error)+'</pre></details>':"")+'</article>';
 }).join("");
 document.querySelectorAll("[data-progress]").forEach(el=>el.style.width=Math.min(100,Number(el.dataset.progress))+"%");
 }catch(e){toast(e.message);}
}
$("jobs").addEventListener("click",async e=>{const id=e.target.dataset.job,action=e.target.dataset.action;if(!id)return;e.target.disabled=true;try{await api("queue/"+id+"/"+action,{});await refreshQueue();}catch(error){toast(error.message);}});
$("download-report").addEventListener("click",async()=>{try{const response=await fetch("/api/export",{headers:{"X-ReelForge-Token":token}});if(!response.ok)throw Error("Could not export report.");downloadBlob(await response.blob(),"reelforge-download-report.csv");}catch(e){toast(e.message);}});
async function browse(path=""){
 try{const result=await api("folders?path="+encodeURIComponent(path));currentFolder=result.path;folderParent=result.parent;$("folder-path").value=result.path;$("folder-list").innerHTML=result.folders.map(f=>'<button class="folder-row" data-folder="'+esc(f.path)+'">▱ '+esc(f.name)+'</button>').join("")||'<p class="field-help">No subfolders in this location.</p>';$("folder-error").textContent=result.truncated?"Showing the first 200 folders. Enter a path to open another folder.":"";}
 catch(e){$("folder-error").textContent=e.message;}
}
$("browse").addEventListener("click",()=>{$("folder-dialog").showModal();browse();});
$("folder-go").addEventListener("click",()=>browse($("folder-path").value));
$("folder-path").addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();browse($("folder-path").value);}});
$("folder-up").addEventListener("click",()=>browse(folderParent));
$("folder-list").addEventListener("click",e=>{if(e.target.dataset.folder)browse(e.target.dataset.folder);});
$("folder-close").addEventListener("click",()=>$("folder-dialog").close());
$("folder-choose").addEventListener("click",()=>{if(currentFolder){$("root").value=currentFolder;$("folder-dialog").close();schedulePreview();}});
async function init(){
 try{const saved=JSON.parse(localStorage.getItem("reelforge-rules")||"{}");ruleIds.forEach(id=>{if(id in saved){if($(id).type==="checkbox")$(id).checked=saved[id];else $(id).value=saved[id];}});}catch{}
 render();
 try{const status=await api("status");if(!$("root").value)$("root").value=status.default_root;$("system-pill").textContent=status.ffmpeg&&status.ffprobe?"● Engine ready":"● FFmpeg setup needed";$("health").innerHTML=[["yt-dlp",status.yt_dlp],["FFmpeg",status.ffmpeg?"Ready":"Missing"],["ffprobe",status.ffprobe?"Ready":"Missing"],["Deno",status.deno?"Ready":"Recommended · not installed"]].map(([name,value])=>'<div class="health-row"><span>'+name+'</span><b class="'+(value==="Missing"?"missing":"")+'">'+esc(value)+'</b></div>').join("");await refreshQueue();setInterval(refreshQueue,1500);}
 catch(e){$("system-pill").textContent="Session unavailable";notice("scan-feedback",e.message,true);}
}
init();
