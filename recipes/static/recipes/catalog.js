"use strict";
const data = JSON.parse(document.getElementById("product-catalog-data").textContent);
const search = document.getElementById("catalog-search");
const boxes = [...document.querySelectorAll("input[name=selected_products]")];
let category = "all";
function update() {
 const term = search.value.trim().toLowerCase();
 let count = 0;
 document.querySelectorAll("[data-product-id]").forEach(card => {
   const p = data.products.find(p => p.id === card.dataset.productId);
   const show = (category === "all" || p.category === category) && (p.ru + " " + p.kk).toLowerCase().includes(term);
   card.hidden = !show; if(show) count++;
 });
 document.getElementById("catalog-empty").hidden = count > 0;
 const tags = document.getElementById("catalog-selected"); tags.replaceChildren();
 boxes.filter(b=>b.checked).forEach(box=>{
   const p=data.products.find(p=>p.id===box.value);
   const button=document.createElement("button");button.type="button";button.className="tag";
   button.textContent=p[data.language]+" ×";button.setAttribute("aria-label",(data.language==="ru"?"Убрать ":"Алып тастау: ")+p[data.language]);
   button.onclick=()=>{box.checked=false;update();};tags.append(button);
 });
 document.getElementById("catalog-count").textContent=String(boxes.filter(b=>b.checked).length);
}
search.addEventListener("input",update);boxes.forEach(b=>b.addEventListener("change",update));
document.querySelectorAll("button[data-category]").forEach(b=>b.addEventListener("click",()=>{
 category=b.dataset.category;document.querySelectorAll("button[data-category]").forEach(x=>x.setAttribute("aria-pressed",String(x===b)));update();
}));
document.getElementById("catalog-clear").onclick=()=>{boxes.forEach(b=>b.checked=false);update();};update();
