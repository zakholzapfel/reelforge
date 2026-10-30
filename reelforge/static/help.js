"use strict";
document.addEventListener("click",event=>{
 const button=event.target.closest("[data-help]");if(!button)return;
 const target=document.getElementById(button.dataset.help);if(!target)return;
 showView("help");
 target.scrollIntoView({block:"start"});
 target.querySelector("h2")?.focus({preventScroll:true});
});
const faqSearch=document.getElementById("faq-search");
faqSearch.addEventListener("input",()=>{
 const query=faqSearch.value.toLocaleLowerCase().trim();let count=0;
 document.querySelectorAll("#help-faq details").forEach(entry=>{
  const match=entry.textContent.toLocaleLowerCase().includes(query);
  entry.hidden=!match;if(match)count++;
  entry.open=!!query&&match;
 });
 document.getElementById("faq-empty").hidden=count>0;
 document.getElementById("faq-count").textContent=count+" question"+(count===1?"":"s");
});
