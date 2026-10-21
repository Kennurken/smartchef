"use strict";
(() => {
 const data=JSON.parse(document.getElementById("cooking-data").textContent);
 const labels=JSON.parse(document.getElementById("cooking-labels").textContent);
 let index=0;let completed=new Set();let lastClick=-Infinity;
 const active=document.getElementById("cooking-active"),complete=document.getElementById("cooking-complete");
 const heading=document.getElementById("step-heading"),text=document.getElementById("step-text");
 const next=document.getElementById("cook-next"),back=document.getElementById("cook-back");
 function render(focus=false){
   const done=index===data.steps.length; active.hidden=done;complete.hidden=!done;
   document.getElementById("cook-progress").value=completed.size;
   document.getElementById("progress-label").textContent=(document.documentElement.lang==="ru"?"Выполнено ":"Орындалды: ")+`${completed.size} / ${data.steps.length}`;
   if(done){document.getElementById("complete-count").textContent=`${data.steps.length} / ${data.steps.length}`;if(focus)document.getElementById("complete-heading").focus();return;}
   document.getElementById("step-number").textContent=`${labels.step} ${index+1} ${labels.of} ${data.steps.length}`;
   heading.textContent=`${labels.step} ${index+1}`;
   text.textContent=data.steps[index];
   back.disabled=index===0;next.textContent=index===data.steps.length-1?labels.finish:labels.next;
   if(focus)heading.focus();
 }
 next.addEventListener("click",event=>{const now=performance.now();if(event.detail>1||now-lastClick<250)return;lastClick=now;if(index<data.steps.length){completed.add(index);index++;}render(true);});
 back.addEventListener("click",()=>{if(index>0)index--;render(true);});
 document.getElementById("cook-restart").addEventListener("click",()=>{index=0;completed.clear();lastClick=-Infinity;render(true);});
 render();
})();
