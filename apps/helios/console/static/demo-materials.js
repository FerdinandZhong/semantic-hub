"use strict";
const $=id=>document.getElementById(id);
let library={items:[],embedding_ready:false},detail=null,busy=false,linkLimit=20;
const selected=new Set();
const expandedResults=new Set();
let resultsDocument=null;
const preferredSource=new URL(location.href).searchParams.get("source");
let sourceFilterInitialized=false,workflowKey=null,visualRevisionKey=null;
if(preferredSource){const studio=new URL("/demo/context",location.origin);studio.searchParams.set("source",preferredSource);studio.hash="source";$("return-material-studio").href=studio.pathname+studio.search+studio.hash;$("return-material-studio").hidden=false;$("material-source-context").textContent=`Target source: ${preferredSource}. Review evidence for this model; the library remains shared.`;$("material-source-context").hidden=false;}
function node(tag,text,cls){const element=document.createElement(tag);if(text!==undefined)element.textContent=String(text);if(cls)element.className=cls;return element;}
const tabs=[...document.querySelectorAll('[role=tab][data-tab]')];
function showTab(name){for(const tab of tabs){const on=tab.dataset.tab===name;tab.setAttribute("aria-selected",String(on));tab.tabIndex=on?0:-1;$(tab.getAttribute("aria-controls")).hidden=!on;}}
tabs.forEach((tab,index)=>{tab.addEventListener("click",()=>showTab(tab.dataset.tab));tab.addEventListener("keydown",event=>{const step={ArrowRight:1,ArrowLeft:-1}[event.key];if(!step)return;const next=tabs[(index+step+tabs.length)%tabs.length];showTab(next.dataset.tab);next.focus();});});
function message(text,isError=false){$(isError?"materials-error":"materials-notice").textContent=text;$("materials-error").hidden=!isError;}
async function api(path,body){const response=await fetch(`/demo/api/materials${path}`,{cache:"no-store",...(body?{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}:{})});let data;try{data=await response.json();}catch{throw new Error("The server returned an unreadable response. Reload and try again.");}if(!response.ok){const reason=typeof data.detail==="string"?data.detail:JSON.stringify(data.detail || "Material request failed.");throw new Error(response.status===409?`${reason} Reload the material and review its links against the current model draft.`:reason);}return data;}
function latest(){return detail && Number(detail.revision)===Number(detail.latest_revision || Math.max(...(detail.revisions || [detail.revision])));}
function model(){return (detail?.models || []).find(item=>item.source===$("material-model").value);}
function matchingLinks(){
 const terms=$("link-search").value.toLowerCase().trim().split(/\s+/).filter(Boolean);
 const links=(detail?.links || []).filter(item=>terms.every(term=>[item.model_title,item.source,item.target_label,item.target,typeof item.location==="object"?JSON.stringify(item.location):item.location,item.quote,item.reason].join(" ").toLowerCase().includes(term))&&(!$("link-source").value||item.source===$("link-source").value)&&(!$("link-status").value||($("link-status").value==="stale"?item.stale:item.status===$("link-status").value)));
 const score=item=>Number.isFinite(Number(item.score))?Number(item.score):-1;
 return links.sort((a,b)=>($("link-sort").value==="model"?String(a.model_title || a.source).localeCompare(String(b.model_title || b.source)):0)||score(b)-score(a)||String(a.id).localeCompare(String(b.id)));
}
function linkCounts(){
 const matches=matchingLinks(),count=matches.length;
 const hiddenSelected=selected.size-matches.filter(item=>selected.has(item.id)).length;
 $("link-count").textContent=`${(detail.links || []).length} total · ${count} matching · ${selected.size} selected${hiddenSelected?` (${hiddenSelected} outside these filters)`:""} · Showing ${Math.min(linkLimit,count)}`;
 $("candidate-links-summary").textContent=`Candidate model links · ${count} matching · ${selected.size} selected`;
}

function currentLinks(){return (detail?.links || []).filter(item=>selected.has(item.id));}
function controls(){visualControls();const mutable=Boolean(detail)&&latest()&&!busy&&!detail.fact_review_pending;$("suggest-material").disabled=!mutable;$("analyze-material").disabled=!mutable||visualFrozen()||(detail?.links || []).some(item=>item.status==="approved");for(const id of ["approve-material","reject-material"])$(id).disabled=!mutable||!currentLinks().length||(id==="approve-material"&&currentLinks().some(item=>item.stale));const approved=currentLinks().filter(item=>item.status==="approved"),target=model();$("apply-material").disabled=!mutable||!target||!approved.length||approved.length!==currentLinks().length||approved.some(item=>item.source!==target.source||item.stale);$("upload-submit").disabled=busy;$("material-file").disabled=busy;$("material-dropzone").classList.toggle("busy",busy);$("materials-reload").disabled=busy;$("material-revision").disabled=busy;$("use-embeddings").disabled=busy||!library.embedding_ready;$("material-model").disabled=busy;for(const id of ["link-source","link-status","link-sort","link-search","show-more-links","matching-scope"])$(id).disabled=busy;for(const id of ["select-matching-links","clear-material-selection"])$(id).disabled=!mutable;for(const checkbox of $("material-links").querySelectorAll("input"))checkbox.disabled=busy||!latest();$("apply-revision").textContent=target?`Apply to draft revision ${target.draft_revision}. Select only approved links for this model.`:"No model draft is available.";const studio=new URL("/demo/context",location.origin);if(target)studio.searchParams.set("source",target.source);studio.searchParams.set("draft","ai");studio.hash="source";$("open-material-studio").href=studio.pathname+studio.search+studio.hash;}
function renderLibrary(){const query=$("material-search").value.toLowerCase().trim(),list=$("materials-list");list.replaceChildren();for(const item of library.items.filter(item=>[item.title,item.filename].join(" ").toLowerCase().includes(query))){const button=node("button",undefined,"library-item");button.type="button";button.setAttribute("aria-pressed",String(detail?.document_id===item.document_id));button.title=item.title || item.filename;button.append(node("span",(item.filename.split(".").pop() || "").toUpperCase(),"file-type"),node("strong",item.title || item.filename),node("small",`Revision ${item.revision} · ${String(item.status).replaceAll("_"," ")} · ${item.chunk_count} sections`));button.addEventListener("click",()=>open(item.document_id));list.append(button);}if(!list.children.length)list.append(node("p","No materials match this search.","muted"));const previous=$("upload-document").value;$("upload-document").replaceChildren();const fresh=node("option","New document");fresh.value="";$("upload-document").append(fresh);for(const item of library.items){const option=node("option",`New revision: ${item.title || item.filename}`);option.value=item.document_id;$("upload-document").append(option);}$("upload-document").value=previous;}
function resultDisclosure(key,title,cls){
 const section=node("details",undefined,cls);section.open=expandedResults.has(key);
 section.append(node("summary",title));
 section.querySelector("summary").addEventListener("click",()=>{if(!section.open)expandedResults.add(key);else expandedResults.delete(key);});
 return section;
}
function renderAnalysis(){
 const analysis=$("material-analysis"),value=detail.analysis;
 analysis.replaceChildren();$("analysis-empty").hidden=Boolean(value);$("analysis-results").hidden=!value;
 if(!value)return;
 const claims=value.claims || [];
 $("analysis-results-summary").textContent=`Analysis results · ${claims.length} proposed ${claims.length===1?"claim":"claims"}`;
 const overview=resultDisclosure("overview","Document summary","analysis-overview");
 overview.append(node("p",value.summary || "No summary available."));analysis.append(overview);
 claims.forEach((claim,index)=>{
  const statement=claim.statement || claim.kind || "Proposed claim";
  const title=statement.length>160?`${statement.slice(0,157)}…`:statement;
  const box=resultDisclosure(`claim:${index}:${claim.chunk_id}`,title,"claim");
  const chunk=(detail.chunks || []).find(item=>item.id===claim.chunk_id);
  const location=chunk?.location;
  box.append(node("p",statement),node("blockquote",claim.quote || ""),node("p",`Section: ${typeof location==="object"?JSON.stringify(location):location || claim.chunk_id} · ${claim.kind || "Proposed claim"}`,"muted"));
  analysis.append(box);
 });
}
function renderDetail(){if(!detail)return;const resultsKey=`${detail.document_id}:${detail.revision}:${detail.analysis?.created_at || ""}`;if(resultsDocument!==resultsKey){expandedResults.clear();$("analysis-results").open=false;resultsDocument=resultsKey;}if(workflowKey!==`${detail.document_id}:${detail.revision}:${visualFrozen()}`)linkLimit=20;const address=new URL(location.href);address.searchParams.set("document",detail.document_id);history.replaceState(null,"",address);$("material-detail").hidden=false;$("material-empty").hidden=true;$("material-title").textContent=detail.title || detail.filename;$("material-meta").textContent=`${detail.filename} · Revision ${detail.revision} · ${String(detail.status).replaceAll("_"," ")} · ${detail.chunk_count} sections · SHA-256 ${detail.sha256}`;$("revision-note").textContent=latest()?(visualFrozen()?"This revision created a draft semantic model. You can also link evidence, or analyze more pages in a new document revision.":"Analyze pages, review the results, then create a new semantic model, add evidence to an existing model, or do both."):"This historical revision is read-only. Select the latest revision to analyze, review, or apply evidence.";$("material-revision").replaceChildren();for(const revision of detail.revisions || [detail.revision]){const option=node("option",`Revision ${revision}`);option.value=revision;$("material-revision").append(option);}$("material-revision").value=detail.revision;const chunks=$("material-chunks");chunks.replaceChildren();for(const chunk of detail.chunks || []){const box=node("article",undefined,chunk.extraction_method==="vision"?"chunk chunk-vision":"chunk");box.append(node("strong",typeof chunk.location==="object"?JSON.stringify(chunk.location):chunk.location || chunk.id),node("pre",chunk.text));chunks.append(box);}if(!chunks.children.length)chunks.append(node("p","No text sections are available. Use visual analysis for supported PDF or image pages.","muted"));renderAnalysis();$("embedding-note").textContent=library.embedding_ready?"Embedding configuration is ready. Similarity can help rank candidate links. This optional step stores derived text in Lance.":"Embedding configuration is unavailable. Keyword matching works without embeddings. When enabled, embeddings store derived text in Lance.";if(!library.embedding_ready)$("use-embeddings").checked=false;const previousFilter=$("link-source").value;$("link-source").replaceChildren();const allModels=node("option","All models");allModels.value="";$("link-source").append(allModels);for(const target of detail.models || []){const option=node("option",target.title || target.source);option.value=target.source;$("link-source").append(option);}$("link-source").value=!sourceFilterInitialized&&(detail.models || []).some(item=>item.source===preferredSource)?preferredSource:previousFilter;sourceFilterInitialized=true;renderLinks();const previous=$("material-model").value,preferred=new URL(location.href).searchParams.get("source");$("material-model").replaceChildren();for(const target of detail.models || []){const option=node("option",target.title || target.source);option.value=target.source;$("material-model").append(option);}if((detail.models || []).some(item=>item.source===previous))$("material-model").value=previous;else if((detail.models || []).some(item=>item.source===preferred))$("material-model").value=preferred;const usage=$("material-usage");usage.replaceChildren();for(const item of detail.usage || [])usage.append(node("p",`Document revision ${item.revision} added to ${item.source}, draft revision ${item.draft_revision}.`));renderVisual();renderLibrary();controls();}
function renderLinks(){if(!detail)return;const matching=matchingLinks();linkCounts();$("show-more-links").hidden=matching.length<=linkLimit;const links=$("material-links");links.replaceChildren();for(const item of matching.slice(0,linkLimit)){const box=node("article",undefined,"material-link"),label=node("label"),checkbox=node("input");box.dataset.linkId=item.id;box.dataset.score=item.score??"";checkbox.type="checkbox";checkbox.checked=selected.has(item.id);checkbox.disabled=!latest()||busy;checkbox.addEventListener("change",()=>{if(checkbox.checked)selected.add(item.id);else selected.delete(item.id);linkCounts();controls();});label.append(checkbox,node("span",`${item.model_title || item.source}: ${item.target_label || item.target}`));box.append(label,node("span",item.stale?`${item.status} · Stale target`:item.status,"badge"),node("p",`Section: ${typeof item.location==="object"?JSON.stringify(item.location):item.location || item.chunk_id}${item.score!=null?` · Relevance score: ${Number(item.score).toFixed(3)}`:""}`,"muted"));const evidence=resultDisclosure(`link:${item.id}`,"View evidence and matching reason","link-evidence");evidence.append(node("blockquote",item.quote || ""),node("p",item.reason || ""));box.append(evidence);links.append(box);}if(!links.children.length)links.append(node("p",(detail.links || []).length?"No links match these filters.":"No proposed model links. Find candidate links now, or analyze the content first.","muted"));}
async function loadLibrary(){library=await api("");renderLibrary();controls();}
async function open(id,revision){if(busy)return;const switching=detail?.document_id!==id;busy=true;controls();try{detail=await api(`/${encodeURIComponent(id)}${revision?`?revision=${encodeURIComponent(revision)}`:""}`);selected.clear();renderDetail();if(switching)showTab("extract");const url=new URL(location.href);url.searchParams.set("document",id);history.replaceState(null,"",url);message("");}catch(error){message(error.message,true);}finally{busy=false;controls();}}
async function mutate(action,body,success){if(busy||!detail||!latest())return;busy=true;controls();message("Working…");try{detail=await api(`/${encodeURIComponent(detail.document_id)}/${action}`,{revision:detail.revision,...body});if(action!=="review")selected.clear();await loadLibrary();renderDetail();if(action==="suggest"){$("candidate-links").open=true;showTab("use");}if(action==="analyze")showTab("analyze");if(action==="visual"){showTab("analyze");$("visual-workflow").open=true;$("matching-scope").value="analyzed";}message(success);}catch(error){message(error.message,true);}finally{busy=false;controls();}}
$("material-upload").addEventListener("submit",async event=>{event.preventDefault();if(busy)return;const file=$("material-file").files[0];if(!file)return;if(file.size>5*1024*1024){message("Choose a file up to 5 MiB.",true);return;}if(!/\.(txt|md|pdf|docx|png|jpg|jpeg)$/i.test(file.name)){message("Choose a TXT, Markdown, PDF, DOCX, PNG, or JPG document.",true);return;}busy=true;controls();message(`Uploading ${file.name} (${(file.size/1024/1024).toFixed(2)} MiB)… Scanned pages are transcribed by AI, which can take a minute.`);try{const bytes=new Uint8Array(await file.arrayBuffer());let binary="";for(let offset=0;offset<bytes.length;offset+=32768)binary+=String.fromCharCode(...bytes.subarray(offset,offset+32768));const documentId=$("upload-document").value;detail=await api("/upload",{filename:file.name,content_base64:btoa(binary),...(documentId?{document_id:documentId}:{})});selected.clear();await loadLibrary();renderDetail();$("material-file").value="";showTab(detail.visual_extraction?"analyze":"extract");if(detail.visual_extraction)$("visual-workflow").open=true;message(detail.ocr_notice || "Material uploaded. Inspect the extracted sections before analysis.");}catch(error){message(error.message,true);}finally{busy=false;controls();}});
$("material-search").addEventListener("input",renderLibrary);
$("materials-reload").addEventListener("click",async()=>{try{await loadLibrary();if(detail)await open(detail.document_id);message("Library refreshed.");}catch(error){message(error.message,true);}});
$("material-revision").addEventListener("change",()=>open(detail.document_id,$("material-revision").value));
$("material-model").addEventListener("change",controls);
$("analyze-material").addEventListener("click",()=>mutate("analyze",{mode:"llm"},"Analysis ready. Verify the proposed claims against the extracted text."));
$("suggest-material").addEventListener("click",()=>mutate("suggest",{use_embeddings:$("use-embeddings").checked,...($("matching-scope").value==="analyzed"&&detail.visual_extraction?{pages:detail.visual_extraction.pages}:{})},"Candidate links ready. Select and review the relevant links."));
for(const [id,decision] of [["approve-material","approved"],["reject-material","rejected"]])$(id).addEventListener("click",()=>{const reviewer=$("material-reviewer").value.trim(),note=$("material-review-note").value.trim();if(!reviewer||!note){message("Enter a reviewer name and review note before recording a decision.",true);return;}mutate("review",{link_ids:[...selected],decision,reviewer,note},`Selected links ${decision}.`);});
$("apply-material").addEventListener("click",()=>{const target=model();if(target)mutate("apply",{link_ids:[...selected],source:target.source,expected_revision:target.draft_revision},"Approved evidence and document lineage added to the draft. Open Studio to generate, validate, and review definitions.");});
(async()=>{try{await loadLibrary();const id=new URL(location.href).searchParams.get("document");if(id)await open(id);}catch(error){message(error.message,true);}})();

for(const id of ["link-source","link-status","link-sort"])$(id).addEventListener("change",()=>{linkLimit=20;renderLinks();controls();});
$("show-more-links").addEventListener("click",()=>{linkLimit+=20;renderLinks();controls();});
$("select-matching-links").addEventListener("click",()=>{if(busy||!latest())return;for(const item of matchingLinks())selected.add(item.id);renderLinks();controls();});
$("clear-material-selection").addEventListener("click",()=>{if(busy)return;selected.clear();renderLinks();controls();});

function visualFrozen(){return Boolean((detail?.fact_models || []).length);}
function visualControls(){
 const canAnalyze=Boolean(detail)&&latest()&&!busy&&!detail.fact_review_pending;
 for(const id of ["visual-pages","analyze-visual"])$(id).disabled=!canAnalyze;
 const enabled=canAnalyze&&!visualFrozen();
 for(const id of ["visual-model-title","visual-reviewer","visual-review-note","visual-acknowledged"])$(id).disabled=!enabled;
 for(const input of $("visual-rows").querySelectorAll("input,textarea"))input.disabled=!enabled;
 $("approve-visual").disabled=!enabled||!$("visual-rows").querySelector('input[data-select]:checked')||!$("visual-acknowledged").checked;
 $("visual-preview-page").disabled=busy;
 $("finish-visual-model").disabled=busy||!latest();
}
function previewVisual(){
 if(!detail||!$("visual-preview-page").value)return;
 const url=`/demo/api/materials/${encodeURIComponent(detail.document_id)}/preview?revision=${encodeURIComponent(detail.revision)}&page=${encodeURIComponent($("visual-preview-page").value)}`;
 $("visual-preview").src=url;$("visual-preview-link").href=url;$("visual-preview").alt=`Original document page ${$("visual-preview-page").value}`;
}
function renderVisual(){
 const source=detail.visual_source,extraction=detail.visual_extraction;
 $("visual-results-summary").textContent=extraction?`Review page results · Pages ${extraction.pages.join(", ")} · Revision ${detail.revision}`:"Review page results";
 $("matching-results-scope").textContent=detail.matching?`Last matching scope: ${detail.matching.pages?.length?"pages "+detail.matching.pages.join(", "):"all extracted document text"}. Run Find model links to apply a different scope.`:"Run Find model links to match the selected evidence scope.";
 const key=`${detail.document_id}:${detail.revision}:${visualFrozen()}`;
 if(workflowKey!==key){
  $("evidence-workflow").open=!source?.visual_capable;
  $("candidate-links").open=false;
  workflowKey=key;
 }
 $("evidence-model-stage").hidden=false;
 $("model-actions").hidden=false;$("create-model-stage").hidden=false;
 $("create-model-help").hidden=Boolean(extraction?.observations?.length)||visualFrozen();
 $("create-model-help").textContent=source?.visual_capable?"Analyze pages in step 2, then select and check the proposed rows here.":"Creating a dataset from reviewed rows requires a PDF or image. You can attach this document as evidence instead.";
 const revisionKey=`${detail.document_id}:${detail.revision}`;
 if(visualRevisionKey!==revisionKey){
  $("visual-acknowledged").checked=false;$("visual-approval").open=false;
  $("visual-pages").value=(extraction?.pages || [1]).join(", ");
  $("visual-model-title").value=`${detail.title || detail.filename} — reviewed facts`;
  $("matching-scope").value=extraction?"analyzed":"all";
  visualRevisionKey=revisionKey;
 }
 $("matching-scope").options[0].disabled=!extraction;
 $("matching-scope").options[0].textContent=extraction?`Analyzed pages: ${extraction.pages.join(", ")}`:"Analyzed pages (analyze pages first)";
 $("visual-approval").hidden=!(extraction?.observations || []).length||visualFrozen();
 $("visual-models").replaceChildren();
 const frozen=visualFrozen()||(detail.links || []).some(item=>item.status==="approved");
 $("analysis-availability").hidden=!frozen;
 $("analysis-availability").textContent="This document revision contains reviewed evidence. Analyze pages again to start a new revision, or upload revised content for a text-only document. You can still find and review links using the existing text.";
 $("finish-visual-model").hidden=!detail.fact_review_pending;
 $("visual-stage").hidden=!source?.visual_capable;
 $("text-analysis-stage").hidden=!(detail.chunks || []).length;
 for(const id of ["text-links-stage","text-review-stage","text-apply-stage"])$(id).hidden=!(detail.chunks || []).length&&!(detail.links || []).length;
 if(!source?.visual_capable)return;
 $("visual-pages-help").textContent=`${source.page_count} page(s). Enter up to six page numbers separated by commas. Review each original page before approval.`;
 const pageSelect=$("visual-preview-page");pageSelect.replaceChildren();
 const pages=extraction?.pages?.length?extraction.pages:Array.from({length:source.page_count},(_,i)=>i+1);
 for(const page of pages){const option=node("option",`Page ${page}`);option.value=page;pageSelect.append(option);}previewVisual();
 $("visual-summary").textContent=extraction?`${visualFrozen()?"Reviewed rows · Read-only":"Needs review"} · ${extraction.summary || "Check each proposed row against its original page."}`:"Select pages to extract proposed observations from text, tables, and charts.";
 const rows=$("visual-rows");rows.replaceChildren();
 for(const observation of extraction?.observations || []){
  const card=node("article",undefined,"visual-row");card.dataset.observationId=observation.id;
  const choice=node("label",undefined,"checkbox-label"),check=node("input");check.type="checkbox";check.dataset.select="true";check.addEventListener("change",visualControls);
  choice.append(check,node("strong",`${observation.metric || "Observation"} · Page ${observation.page} · ${observation.extraction_kind || "text"}`));card.append(choice);
  const pageButton=node("button",`Inspect page ${observation.page}`,"secondary");pageButton.type="button";pageButton.addEventListener("click",()=>{pageSelect.value=observation.page;previewVisual();});card.append(pageButton);
  const fields=node("div",undefined,"visual-fields");
  for(const [field,label] of [["entity","Entity"],["metric","Metric"],["value","Value"],["unit","Unit"],["period","Period"],["population","Population"],["denominator","Denominator"],["source_quote","Source quote (verify)"],["uncertainty","Uncertainty"]]){
   const wrapper=node("label",label),input=node(field==="source_quote"||field==="uncertainty"?"textarea":"input");input.dataset.field=field;input.value=observation[field]??"";
   if(field==="value"||field==="denominator"){input.type="number";input.step="any";}else input.maxLength=field==="source_quote"?2000:500;
   wrapper.append(input);fields.append(wrapper);
  }card.append(fields);rows.append(card);
 }
 if(extraction&&!rows.children.length)rows.append(node("p","No observations were proposed. Select other pages or inspect the page text.","muted"));
 for(const transcript of extraction?.transcripts || []){const section=node("details"),pre=node("pre",transcript.text);section.append(node("summary",`Derived text · Page ${transcript.page}`),pre);rows.append(section);}
 $("visual-approval").hidden=!(extraction?.observations || []).length||visualFrozen();
 const models=$("visual-models");models.replaceChildren();
 for(const item of detail.fact_models || []){const line=node("div",undefined,"created-model-notice"),link=node("a","Open created model in Studio");line.append(node("strong","Draft semantic model created."),node("p","Continue in Studio to validate and publish. You can also add this document as evidence to another model below. Analyze more pages in step 2 to start another extraction."));link.href=item.studio_url || `/demo/context?source=${encodeURIComponent(item.source)}#source`;line.append(link);models.append(line);}
}
$("visual-preview-page").addEventListener("change",previewVisual);
$("visual-acknowledged").addEventListener("change",visualControls);
$("analyze-visual").addEventListener("click",()=>{
 const raw=$("visual-pages").value.trim().split(/[\s,]+/),pages=raw.map(Number);
 if(!raw.length||pages.length>6||pages.some(page=>!Number.isInteger(page)||page<1||page>detail.visual_source.page_count)||new Set(pages).size!==pages.length){message("Enter one to six distinct page numbers within this document.",true);return;}
 mutate("visual",{pages},"Page analysis ready. Review the results, then use either model action or both.");
});
$("approve-visual").addEventListener("click",async()=>{
 if(busy||!latest()||visualFrozen())return;
 const rows=[];
 for(const card of $("visual-rows").querySelectorAll(".visual-row")){
  if(!card.querySelector("input[data-select]").checked)continue;
  const original=detail.visual_extraction.observations.find(item=>String(item.id)===card.dataset.observationId),row=Object.fromEntries(["id","entity","metric","value","unit","period","population","denominator","source_quote","extraction_kind","uncertainty","page"].map(key=>[key,original[key]]));
  for(const input of card.querySelectorAll("[data-field]")){const field=input.dataset.field;row[field]=field==="value"||field==="denominator"?(input.value.trim()?Number(input.value):null):input.value.trim();}
  rows.push(row);
 }
 const reviewer=$("visual-reviewer").value.trim(),note=$("visual-review-note").value.trim(),title=$("visual-model-title").value.trim();
 if(!rows.length||!reviewer||!note||!title||!$("visual-acknowledged").checked){message("Select rows, enter a model title, reviewer and note, then acknowledge the original page review.",true);return;}
 busy=true;controls();message("Creating a draft model from reviewed rows…");
 try{const result=await api(`/${encodeURIComponent(detail.document_id)}/facts`,{revision:detail.revision,extraction_id:detail.visual_extraction.extraction_id,title,rows,reviewer,note,acknowledged:true});detail=result.document;await loadLibrary();renderDetail();const notice=$("materials-notice");notice.replaceChildren(node("span","Reviewed rows created a draft model. "));const link=node("a","Open Studio");link.href=result.studio_url;notice.append(link);}
 catch(error){try{detail=await api(`/${encodeURIComponent(detail.document_id)}`);renderDetail();}catch{}message(error.message,true);}finally{busy=false;controls();}
});

$("finish-visual-model").addEventListener("click",async()=>{
 if(busy||!latest()||!detail.fact_review_pending)return;
 busy=true;controls();message("Finishing reviewed model creation…");
 try{const result=await api(`/${encodeURIComponent(detail.document_id)}/facts`,detail.fact_review_pending);detail=result.document;await loadLibrary();renderDetail();const notice=$("materials-notice");notice.replaceChildren(node("span","Reviewed rows created a draft model. "));const link=node("a","Open Studio");link.href=result.studio_url;notice.append(link);}
 catch(error){try{detail=await api(`/${encodeURIComponent(detail.document_id)}`);renderDetail();}catch{}message(error.message,true);}finally{busy=false;controls();}
});

$("link-search").addEventListener("input",()=>{linkLimit=20;renderLinks();controls();});

// Dropzone: picking or dropping a file uploads it immediately through the form handler above.
const dropzone=$("material-dropzone");
$("material-file").addEventListener("change",()=>{if($("material-file").files.length&&!busy)$("material-upload").requestSubmit();});
for(const type of ["dragenter","dragover"])dropzone.addEventListener(type,event=>{event.preventDefault();if(!busy)dropzone.classList.add("dragging");});
for(const type of ["dragleave","drop"])dropzone.addEventListener(type,()=>dropzone.classList.remove("dragging"));
dropzone.addEventListener("drop",event=>{event.preventDefault();if(busy||!event.dataTransfer.files.length)return;$("material-file").files=event.dataTransfer.files;$("material-upload").requestSubmit();});
