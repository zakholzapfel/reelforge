"use strict";
let referenceCatalog={name:"My references",records:[]},demoDateReferences=null;
let dateResearchId=null,dateEditId=null,dateApplied=0,dateReferenceBusy=false;
function dateInfo(item){return item.dating||{confidence:"unknown",evidence:[],notes:[],reviewed:false};}
function dateRange(info){return info.year_start==null?"Undated":info.year_start===info.year_end?String(info.year_start):info.year_start+"–"+info.year_end;}
function dateClass(item){const d=dateInfo(item),start=Number($("date-start").value),end=Number($("date-end").value);if(!Number.isInteger(start)||!Number.isInteger(end)||start<1800||end>2100||start>end)return "invalid";if(d.confidence==="conflicting")return "conflicting";if(d.confidence==="unknown"||d.year_start==null||d.year_end==null)return "unknown";if(d.year_start>=start&&d.year_end<=end)return "inside";if(d.year_end<start||d.year_start>end)return "outside";return "overlap";}
function dateMatches(item){const d=dateInfo(item);return dateClass(item)==="inside"&&(d.confidence==="documented"||$("date-confidence").value==="likely"&&d.confidence==="likely");}
function dateVisible(item){const view=$("date-view").value;if(view==="any")return true;if(view==="inside")return dateMatches(item);if(["likely","documented"].includes(view))return dateInfo(item).confidence===view;return dateClass(item)===view;}
function dateRow(item){const d=dateInfo(item),period=dateClass(item),label={inside:"Within",outside:"Outside",overlap:"Overlaps"}[period];return '<div class="date-badges"><span class="date-badge '+esc(d.confidence)+'">'+esc(dateRange(d))+' · '+esc(d.confidence)+'</span>'+(label?'<span class="date-period '+period+'">'+label+' '+esc($("date-start").value)+'–'+esc($("date-end").value)+'</span>':"")+(d.reviewed?'<span class="date-reviewed">Reviewed</span>':"")+'</div>';}
function dateSummaryButton(view,label,count){return '<button type="button" class="date-count" data-date-view="'+view+'" aria-pressed="'+String($("date-view").value===view)+'">'+count+' '+label+'</button>';}
function dateControls(){
 const busy=scanning||researching;
 ["scan","scan-manifest","demo","date-demo"].forEach(id=>$(id).disabled=busy);
 $("date-research").disabled=busy||!items.length;
 $("date-export").disabled=researching||!items.length;
 $("date-select").disabled=busy||!items.length||Number($("date-start").value)<1800||Number($("date-end").value)>2100||Number($("date-start").value)>Number($("date-end").value);
 $("date-cancel").hidden=!researching;
 document.querySelectorAll("[data-edit],[data-date]").forEach(el=>el.disabled=researching);
 const counts={documented:0,likely:0,unknown:0,conflicting:0};items.forEach(i=>counts[dateInfo(i).confidence]++);
 if(!items.length){$("date-summary").textContent="Scan a source to begin.";return;}
 const valid= dateClass(items[0])!=="invalid";
 $("date-summary").innerHTML='<p>Confidence across all '+items.length+' videos · click a count to view</p><div class="date-counts">'+Object.entries(counts).map(([label,count])=>dateSummaryButton(label,label,count)).join("")+'</div>'+(valid?'<p>Target period '+esc($("date-start").value)+'–'+esc($("date-end").value)+' · matching also requires your selected confidence</p><div class="date-counts">'+dateSummaryButton("inside","match selection rules",items.filter(dateMatches).length)+dateSummaryButton("outside","outside target period",items.filter(i=>dateClass(i)==="outside").length)+dateSummaryButton("overlap","overlap target period",items.filter(i=>dateClass(i)==="overlap").length)+'</div>':'<p>Enter a valid year range to see period matches.</p>');
}
$("date-summary").addEventListener("click",e=>{const view=e.target.closest("[data-date-view]")?.dataset.dateView;if(!view)return;$("date-view").value=view;render();});
["date-start","date-end","date-confidence","date-view"].forEach(id=>$(id).addEventListener("input",render));
$("date-select").addEventListener("click",async()=>{
 try{
 const result=await api("dates/select",{items,year_start:Number($("date-start").value),year_end:Number($("date-end").value),confidence:$("date-confidence").value});
 selected=new Set(result.ids);$("date-view").value="inside";schedulePreview();
 toast(result.ids.length+" matching videos selected. Previous selections were replaced.");
 }catch(e){notice("date-feedback",e.message,true);}
});
$("date-research").addEventListener("click",async()=>{
 if(researching)return;
 const scope=$("date-scope").value==="selected"?chosen():items;
 if(!scope.length){toast("Select videos first or choose All imported videos.");return;}
 researching=true;dateApplied=0;selected.clear();schedulePreview();
 notice("date-feedback","Researching original dates. Download selection cleared; nothing is queued.");
 try{
 const task=await api("dates/research",{items:scope.map(i=>({...i,collection:$("collection").value})),descriptions:$("date-descriptions").checked,references:demo&&demoDateReferences?demoDateReferences:null});
 dateResearchId=task.id;
 let result;
 do{
  await new Promise(resolve=>setTimeout(resolve,450));
  result=await api("dates/research/"+dateResearchId);
  for(const updated of result.items.slice(dateApplied)){
   const index=items.findIndex(i=>i.id===updated.id&&i.url===updated.url);
   if(index>=0)items[index]=updated;
  }
  dateApplied=result.items.length;
  notice("date-feedback","Research "+result.state+" · "+result.done+"/"+result.total+(result.current?"\n"+result.current:"")+(result.warnings.length?"\n"+result.warnings.length+" lookup warning(s); see evidence notes.":""));
  render();
 }while(result.state==="running");
 if(result.state==="failed")notice("date-feedback","Research stopped with an error. Completed results were kept.\n"+result.warnings.join("\n"),true);
 else notice("date-feedback","Research "+result.state+" · "+result.done+"/"+result.total+". Choose your date range and confidence, then Select matches only."+(result.warnings.length?"\n"+result.warnings.length+" lookup(s) failed; title/reference evidence was kept.":""));
 }catch(e){notice("date-feedback",e.message,true);}finally{researching=false;dateResearchId=null;await preview();}
});
$("date-cancel").addEventListener("click",async()=>{if(!dateResearchId)return;try{await api("dates/research/"+dateResearchId+"/cancel",{});notice("date-feedback","Cancelling research; completed results will be kept.");}catch(e){toast(e.message);}});
function safeDateURL(url){try{const u=new URL(url);return ["http:","https:"].includes(u.protocol)&&!u.username&&!u.password?u.href:"";}catch{return "";}}
function dateEvidenceHTML(item){
 const d=dateInfo(item);
 return '<div class="date-verdict">'+dateRow(item)+'</div>'+(d.notes||[]).map(note=>'<p class="field-help">'+esc(note)+'</p>').join("")+((d.evidence||[]).map(e=>{
 const url=safeDateURL(e.url);return '<article class="evidence-item"><b>'+esc(e.year_start===e.year_end?e.year_start:e.year_start+"–"+e.year_end)+' · '+esc(e.label)+'</b><p>'+esc(e.note)+'</p>'+(url?'<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">Open evidence source ↗</a>':"")+'</article>';
 }).join("")||'<p class="field-help">No supported original-date evidence yet. Open the video and search for archive references; record the result below.</p>');
}
function refreshDateDialog(){
 const item=items.find(i=>i.id===dateEditId);if(!item)return;
 const d=dateInfo(item);$("date-title").textContent=item.title;$("date-evidence").innerHTML=dateEvidenceHTML(item);
 const source=safeDateURL(item.url),search="https://www.google.com/search?q="+encodeURIComponent(item.title+" original airdate");
 $("date-links").innerHTML=(source?'<a class="text-button" href="'+esc(source)+'" target="_blank" rel="noopener noreferrer">Watch source ↗</a>':"")+'<a class="text-button" href="'+esc(search)+'" target="_blank" rel="noopener noreferrer">Search original date ↗</a>';
 $("date-upload").textContent=item.upload_date?"Upload date: "+item.upload_date+" · not used as an original air date.":"Upload date not fetched.";
 $("date-description-text").textContent=item.description||"No description fetched. Enable Fetch descriptions online and research this video.";
 $("date-review-start").value=d.year_start??"";$("date-review-end").value=d.year_end??"";
 $("date-review-confidence").value=["documented","likely"].includes(d.confidence)?d.confidence:"unknown";
 const manual=(d.evidence||[]).filter(e=>e.kind==="manual").at(-1);
 $("date-review-note").value=manual?.note||"";$("date-review-url").value=manual?.url||"";
 $("date-read-reference").disabled=d.reviewed||dateReferenceBusy;
}
$("results").addEventListener("click",e=>{const id=e.target.dataset.date;if(!id)return;dateEditId=id;notice("date-review-feedback","");$("date-reference-url").value="";refreshDateDialog();$("date-dialog").showModal();});
$("date-close").addEventListener("click",()=>$("date-dialog").close());
async function saveDateReview(reset=false){
 const item=items.find(i=>i.id===dateEditId);if(!item)return;
 try{
 const start=$("date-review-start").value,end=$("date-review-end").value;
 const result=await api("dates/review",{item,year_start:start===""?null:Number(start),year_end:end===""?(start===""?null:Number(start)):Number(end),confidence:$("date-review-confidence").value,note:$("date-review-note").value,url:$("date-review-url").value,reset});
 items[items.findIndex(i=>i.id===item.id)]=result.item;
 refreshDateDialog();schedulePreview();notice("date-review-feedback",reset?"Automatic evidence restored.":"Date review saved. Rescanning this unchanged source restores it.");
 }catch(e){notice("date-review-feedback",e.message,true);}
}
$("date-save").addEventListener("click",()=>saveDateReview());
$("date-reset").addEventListener("click",()=>saveDateReview(true));
$("date-read-reference").addEventListener("click",async()=>{
 const item=items.find(i=>i.id===dateEditId);if(!item||dateReferenceBusy)return;
 dateReferenceBusy=true;$("date-read-reference").disabled=true;
 notice("date-review-feedback","Reading explicit airdate statements from the reference page…");
 try{const result=await api("dates/reference",{item,url:$("date-reference-url").value});items[items.findIndex(i=>i.id===item.id)]=result.item;refreshDateDialog();schedulePreview();notice("date-review-feedback","Reference claim added. Review whether it matches the exact uploaded edit.");}
 catch(e){notice("date-review-feedback",e.message,true);}finally{dateReferenceBusy=false;refreshDateDialog();}
});
function csvCell(value){let s=String(value??"");if(/^[=+\-@]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';}
$("date-export").addEventListener("click",()=>{
 const rows=[["title","url","year_start","year_end","confidence","reviewed","period_match","evidence_urls","notes"],...items.map(i=>{const d=dateInfo(i);return [i.title,i.url,d.year_start,d.year_end,d.confidence,d.reviewed,dateClass(i),(d.evidence||[]).map(e=>e.url).filter(Boolean).join(" | "),(d.notes||[]).join(" | ")];})];
 downloadBlob(new Blob([rows.map(row=>row.map(csvCell).join(",")).join("\r\n")],{type:"text/csv"}),"reelforge-date-review.csv");
});
$("date-demo").addEventListener("click",()=>{
 setMode("manifest");$("collection").value="Sample Collection";$("preset").value="playlist";
 const sample=[
  {url:"https://example.com/date-demo/sky.mp4",title:"Skyline Study (1080p HD)"},
  {url:"https://example.com/date-demo/harbor.mp4",title:"Evening Harbor (4K)"},
  {url:"https://example.com/date-demo/forest.mp4",title:"Forest Walk 1998"},
  {url:"https://example.com/date-demo/unknown.mp4",title:"Unidentified video"},
  {url:"https://example.com/date-demo/new.mp4",title:"Skyline Study New Edition"},
  {url:"https://example.com/date-demo/conflict.mp4",title:"Skyline Study (1997)"}
 ];
 demoDateReferences=[
  {title:"Skyline Study",year_start:1995,year_end:1995,url:"https://example.com/sample-reference/sky",label:"Sample reference · fictional",note:"Demo metadata only."},
  {title:"Evening Harbor",year_start:1996,year_end:1996,url:"https://example.com/sample-reference/harbor",label:"Sample reference · fictional",note:"Demo metadata only."},
  {title:"Skyline Study New Edition",year_start:2014,year_end:2014,url:"https://example.com/sample-reference/new",label:"Sample reference · fictional",note:"Demo metadata only."}
 ];
 $("manifest").value=JSON.stringify(sample,null,2);$("date-view").value="any";$("date-start").value="1990";$("date-end").value="1999";scanSource(true);
});
function renderReferenceStatus(){
 $("reference-status").textContent=referenceCatalog.records.length?referenceCatalog.name+" · "+referenceCatalog.records.length+" reference records loaded.":"No reference library loaded. Research uses titles, descriptions, and your reviews.";
}
$("reference-file").addEventListener("change",async e=>{
 const file=e.target.files[0];if(!file)return;
 try{
  if(file.size>5*1024*1024)throw Error("Use a reference file under 5 MB.");
  const data=JSON.parse(await file.text());
  referenceCatalog=await api("references",Array.isArray(data)?{name:file.name,records:data}:data);
  renderReferenceStatus();notice("reference-feedback","Reference library imported. Research again to apply it to your videos.");
 }catch(error){notice("reference-feedback",error.message,true);}finally{e.target.value="";}
});
$("reference-export").addEventListener("click",()=>downloadBlob(new Blob([JSON.stringify(referenceCatalog,null,2)],{type:"application/json"}),"reelforge-references.json"));
$("reference-clear").addEventListener("click",async()=>{try{referenceCatalog=await api("references",{name:"My references",records:[]});renderReferenceStatus();notice("reference-feedback","Reference library cleared. Saved video reviews are retained.");}catch(e){notice("reference-feedback",e.message,true);}});
$("demo").addEventListener("click",()=>{demoDateReferences=null;});
api("references").then(data=>{referenceCatalog=data;renderReferenceStatus();}).catch(e=>notice("reference-feedback",e.message,true));
render();
