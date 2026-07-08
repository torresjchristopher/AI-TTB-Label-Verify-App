const profiles = [];
const fields = ["application_id","brand_name","class_type","alcohol_content","net_contents","producer_name","producer_address","country_of_origin","imported"];
let activeJobId = null;
let activeRows = [];
let activeReview = null;

function esc(v){return String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));}
function readForm(){const row={};fields.forEach(f=>{const e=document.getElementById(f);row[f]=e.type==="checkbox"?(e.checked?"true":"false"):e.value.trim();});return row;}
function labelName(r){return r.application_id||[r.brand_name,r.class_type].filter(Boolean).join(" — ")||`Label ${profiles.indexOf(r)+1}`;}
function clearForm(){fields.forEach(f=>{const e=document.getElementById(f);if(e.type==="checkbox")e.checked=false;else e.value="";});}
function renderProfiles(){
  const host=document.getElementById("profileRows");
  host.innerHTML=!profiles.length?"":`<table><thead><tr><th>Label</th><th>Brand</th><th>Class/type</th><th>ABV</th><th>Volume</th><th></th></tr></thead><tbody>${profiles.map((r,i)=>`<tr><td>${esc(labelName(r))}</td><td>${esc(r.brand_name)}</td><td>${esc(r.class_type)}</td><td>${esc(r.alcohol_content)}</td><td>${esc(r.net_contents)}</td><td><button class="secondary compact" onclick="editProfile(${i})">Edit</button> <button class="secondary compact" onclick="removeProfile(${i})">Remove</button></td></tr>`).join("")}</tbody></table>`;
  const select=document.getElementById("profileSelect"); const current=select.value;
  select.innerHTML=`<option value="">Generic TTB Scan</option>`+profiles.map((r,i)=>`<option value="${i}">${esc(labelName(r))}</option>`).join("");
  if([...select.options].some(o=>o.value===current))select.value=current;
  updateModeHelp();
}
window.removeProfile=i=>{profiles.splice(i,1);renderProfiles();};
window.editProfile=i=>{const r=profiles[i];fields.forEach(f=>{const e=document.getElementById(f);if(e.type==="checkbox")e.checked=r[f]==="true";else e.value=r[f]||"";});document.getElementById("addRow").dataset.edit=String(i);window.scrollTo({top:0,behavior:"smooth"});};
document.getElementById("addRow").onclick=()=>{const row=readForm();if(!row.brand_name&&!row.application_id)return alert("Enter an Application ID or Brand name.");const edit=document.getElementById("addRow").dataset.edit;if(edit!==undefined&&edit!==""){profiles[Number(edit)]=row;delete document.getElementById("addRow").dataset.edit;}else profiles.push(row);clearForm();renderProfiles();};
document.getElementById("clearForm").onclick=()=>{clearForm();delete document.getElementById("addRow").dataset.edit;};
document.getElementById("clearProfiles").onclick=()=>{profiles.length=0;renderProfiles();};
function updateModeHelp(){const selected=document.getElementById("profileSelect").value;document.getElementById("modeHelp").textContent=selected===""?"Generic TTB Scan identifies required visible TTB components. Missing items are sent to review rather than failed.":"Comparison mode checks every uploaded image against the selected saved label.";}
document.getElementById("profileSelect").onchange=updateModeHelp;
document.getElementById("files").onchange=e=>{const n=e.target.files.length;document.getElementById("fileCount").textContent=n?`${n} image${n===1?"":"s"} selected`:"Choose one or more label images";};
function setStatus(text,kind=""){const e=document.getElementById("status");e.textContent=text;e.className=`status ${kind}`;}
function metric(label,value){return `<div class="metric"><strong>${esc(value)}</strong><span>${esc(label)}</span></div>`;}
function finalState(row){return row.manual_decision||row.overall;}
function exceptionText(row){return (row.checks||[]).filter(c=>["fail","review"].includes(c.status)).map(c=>`${c.field}: ${c.reason}`).join("; ")||"No exceptions";}
function resultCard(row,index){
  const state=finalState(row);
  const clickable=["review","fail"].includes(row.overall);
  const action=clickable?`<button class="image-button" onclick="openReview(${index})"><img src="/api/jobs/${activeJobId}/images/${encodeURIComponent(row.filename)}" alt="${esc(row.filename)}"><span>Open review</span></button>`:`<div class="image-static"><img src="/api/jobs/${activeJobId}/images/${encodeURIComponent(row.filename)}" alt="${esc(row.filename)}"></div>`;
  let lock="";
  if(row.overall==="fail") lock='<div class="locked-note">Automatic finding: fail — human review available</div>';
  if(row.manual_decision) lock=`<div class="manual-note">Manual decision: ${esc(row.manual_decision)}</div>`;
  return `<article class="result-card ${esc(state)}">${action}<div class="result-body"><div class="result-heading"><strong>${esc(row.filename)}</strong><span class="pill ${esc(state)}">${esc(state)}</span></div><div class="result-meta">${esc(row.elapsed_ms)} ms · OCR ${Math.round((row.ocr_confidence||0)*100)}%</div><p>${esc(exceptionText(row))}</p>${lock}</div></article>`;
}
function renderResults(rows){activeRows=rows;document.getElementById("results").innerHTML=rows.map(resultCard).join("");}
function countFinal(rows,state){return rows.filter(r=>finalState(r)===state).length;}
function renderSummary(summary){
  const approved=countFinal(activeRows,"approved"), denied=countFinal(activeRows,"denied");
  document.getElementById("summary").innerHTML=`<div class="summary-grid">${metric("Total",summary.total)}${metric("Pass",summary.pass)}${metric("Review",summary.review)}${metric("Fail",summary.fail)}${metric("Approved",approved)}${metric("Denied",denied)}${metric("Median",`${summary.median_ms} ms`)}${metric("P95",`${summary.p95_ms} ms`)}</div><p class="downloads"><a href="/api/jobs/${activeJobId}/download/results.csv">Download CSV</a><a href="/api/jobs/${activeJobId}/download/results.json">Download JSON</a><a href="/api/jobs/${activeJobId}/download/summary.json">Download summary</a><a href="/api/jobs/${activeJobId}/download/review-decisions.csv">Download decisions</a></p>`;
}
async function poll(jobId){const res=await fetch(`/api/jobs/${jobId}`);const job=await res.json();if(job.status==="error"){setStatus(job.error||"Batch failed.","error");return;}if(job.status!=="completed"){setStatus(`Batch ${job.status}…`,"running");setTimeout(()=>poll(jobId),1000);return;}setStatus("Batch complete.");activeJobId=jobId;const rr=await fetch(`/api/jobs/${jobId}/results`);renderResults(await rr.json());renderSummary(job.summary);}
document.getElementById("process").onclick=async()=>{const files=[...document.getElementById("files").files];if(!files.length)return alert("Choose label images.");if(files.length>250)return alert("Maximum batch size is 250 images.");const body=new FormData();files.forEach(f=>body.append("files",f));const selected=document.getElementById("profileSelect").value;if(selected!=="")body.append("profile",JSON.stringify(profiles[Number(selected)]));body.append("workers",document.getElementById("workers").value);body.append("aggressive",document.getElementById("aggressive").checked);setStatus(`Uploading ${files.length} images…`,"running");document.getElementById("summary").innerHTML="";document.getElementById("results").innerHTML="";const res=await fetch("/api/jobs",{method:"POST",body});const data=await res.json();if(!res.ok){setStatus(data.detail||"Upload failed.","error");return;}poll(data.job_id);};

window.openReview=index=>{
  const row=activeRows[index];
  if(!row||!["review","fail"].includes(row.overall))return;
  activeReview={index,row};
  document.getElementById("modalTitle").textContent=row.filename;
  document.getElementById("modalImage").src=`/api/jobs/${activeJobId}/images/${encodeURIComponent(row.filename)}`;
  document.getElementById("modalMeta").textContent=`${row.elapsed_ms} ms · OCR ${Math.round((row.ocr_confidence||0)*100)}%`;
  document.getElementById("modalChecks").innerHTML=`<table class="check-table"><thead><tr><th>Check</th><th>Status</th><th>Expected</th><th>Detected</th><th>Reason</th></tr></thead><tbody>${(row.checks||[]).map(c=>`<tr><td>${esc(c.field)}</td><td><span class="pill ${esc(c.status)}">${esc(c.status)}</span></td><td>${esc(c.expected)}</td><td>${esc(c.detected)}</td><td>${esc(c.reason)}</td></tr>`).join("")}</tbody></table>`;
  document.getElementById("modalText").textContent=row.extracted_text||"No OCR text available.";
  const notice=document.getElementById("decisionNotice");
  notice.textContent=row.manual_decision?`Current manual decision: ${row.manual_decision}`:`Automatic finding: ${row.overall}. Review the image and make the final human decision.`;
  document.getElementById("reviewModal").classList.add("open");
  document.getElementById("reviewModal").setAttribute("aria-hidden","false");
};
function closeModal(){document.getElementById("reviewModal").classList.remove("open");document.getElementById("reviewModal").setAttribute("aria-hidden","true");activeReview=null;}
document.querySelectorAll("[data-close-modal]").forEach(e=>e.onclick=closeModal);
document.addEventListener("keydown",e=>{if(e.key==="Escape")closeModal();});
async function saveDecision(decision){
  if(!activeReview)return;
  const response=await fetch(`/api/jobs/${activeJobId}/decisions`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({filename:activeReview.row.filename,decision})});
  const data=await response.json();
  if(!response.ok)return alert(data.detail||"Decision could not be saved.");
  const rr=await fetch(`/api/jobs/${activeJobId}/results`);
  renderResults(await rr.json());
  const job=await (await fetch(`/api/jobs/${activeJobId}`)).json();
  renderSummary(job.summary);
  closeModal();
}
document.getElementById("approveReview").onclick=()=>saveDecision("approved");
document.getElementById("denyReview").onclick=()=>saveDecision("denied");
renderProfiles();
