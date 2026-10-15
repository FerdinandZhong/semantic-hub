"use strict";
const $ = id => document.getElementById(id);
let config, workspace, definition, selectedMetric = 0, selectedJoin = 0, selectedTable = null, tablePage = 0;
let dirty = false, busy = false, inspectedVersion, versionCanvas;
let documentsState=null, selectedDocumentId=null, documentLoadId=0, filePreviewId=0;
let currentSource = new URL(location.href).searchParams.get("source");
const viewedVersion = new URL(location.href).searchParams.get("version");
const pageSize = 20;
const stepHashes = {source:"#source",define:"#studio",validate:"#validate",review:"#hub"};
function stepFromHash() {
  return Object.keys(stepHashes).find(name=>stepHashes[name]===location.hash) || "define";
}
function node(tag, text, className) {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text;
  if (className) item.className = className;
  return item;
}
function button(text, action, className = "secondary") {
  const item = node("button", text, className);
  item.type = "button";
  item.addEventListener("click", action);
  return item;
}
async function api(path, body) {
  const url=new URL(path,location.origin);
  if(currentSource)url.searchParams.set("source",currentSource);
  const response = await fetch(url, {
    cache:"no-store", ...(body ? {
      method:"POST",headers:{
        "Content-Type":"application/json"
      },body:JSON.stringify(body)
    } : {
    })
  });
  const data = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map(e => `${e.loc.slice(1).join(".")}: ${e.msg}`).join("; ") : data.detail;
    throw new Error(detail || "The request failed.");
  }
  return data;
}
function binding() {
  return {
    pack_id:config.pack_id,snapshot_sha256:config.snapshot_sha256,session_id:config.session_id
  };
}
function error(err) {
  $("error").textContent = err.message;
  $("error").hidden = false;
  $("error").scrollIntoView({
    block:"nearest"
  });
}
async function work(action, message) {
  if (busy) return;
  busy = true;
  $("error").hidden = true;
  $("notice").textContent = message || "Working…";
  controls();
  // Freeze editors while a request captures the current draft.
  for (const section of document.querySelectorAll('[role="tabpanel"]')) section.inert = true;
  try {
    await action();
  }
  catch (err) {
    error(err);
    $("notice").textContent = "";
  }
  finally {
    busy = false;
    for (const section of document.querySelectorAll('[role="tabpanel"]')) section.inert = false;
    controls();
  }
}
function workspaceStatus() {
  const ready=Boolean(workspace), hub=document.body.dataset.section === "hub";
  $("save").hidden=hub;
  $("edit-draft").hidden=!hub;
  $("edit-draft").disabled=busy;
  $("draft-status").textContent = !ready ? "Loading workspace…" : hub
    ? (workspace.versions.length ? `${workspace.versions.length} reviewed version${workspace.versions.length === 1 ? "" : "s"}` : "No reviewed versions yet")
    : `Draft revision ${workspace.draft.revision} · ${dirty ? "Unsaved changes" : (workspace.draft.revision ? "Saved locally" : "Starter definitions")}`;
  $("active-status").textContent = ready ? (workspace.active_version ? `Queries use reviewed version ${workspace.active_version}` : "Original sample context · no Studio version activated") : "";
}
function controls() {
  if(viewedVersion)return;
  const ready = Boolean(workspace), validated = ready && !dirty && workspace.draft.validation?.passed;
  const currentEvidence=ready && !dirty && workspace.draft.validation?.validation_sha256 && workspace.draft.validation.revision===workspace.draft.revision;
  $("save").disabled = busy || !ready || (!dirty && workspace.draft.revision > 0);
  $("reload").disabled = busy;
  for(const checkbox of $("review-items").querySelectorAll("input[type=checkbox]")) checkbox.disabled=busy || dirty;
  for (const id of ["select-page","select-all","baseline"]) $(id).disabled=busy || dirty || !ready;
  for(const control of document.querySelectorAll(".version-comparison select,.version-comparison button"))control.disabled=busy || dirty;
  $("validate").disabled = busy || !ready || dirty || workspace.draft.revision === 0;
  $("review-fields").disabled = busy || !validated || (workspace.review?.items || []).some(item => item.status !== "approved");
  for (const id of ["approve-selected","request-selected"]) {
    $(id).hidden=!selectedReview.size;
    $(id).disabled = busy || dirty || !currentEvidence || !selectedReview.size;
  }
  $("review-batch-actions").hidden=!selectedReview.size;
  $("review-batch-count").textContent=`${selectedReview.size} selected across all pages`;
  workspaceStatus();
  $("validation-status").textContent = dirty ? "Save your changes before validation. Previous evidence no longer applies to this draft." : !ready || workspace.draft.revision === 0 ? "Save your first draft to enable validation." : workspace.draft.validation ? (validated ? "All checks passed for this saved draft." : "Validation needs attention. Inspect the results below.") : "This saved draft is ready to validate.";
  proposalControls();
  renderReviewReadiness();
}
function renderReviewReadiness(){
  const box=$("review-blockers");box.replaceChildren();
  if(!workspace){box.hidden=true;return;}
  const report=workspace.draft.validation,items=workspace.review?.items||[],pending=items.filter(item=>item.status!=="approved").length;
  const validated=!dirty && report?.passed && report.revision===workspace.draft.revision;
  const blockers=[];
  if(dirty)blockers.push("Save your changes, then validate the new revision. Previous evidence no longer applies.");
  else if(!report || report.revision!==workspace.draft.revision)blockers.push(workspace.draft.revision===0?"Save the first draft, then run validation.":"Run validation for this saved revision.");
  else if(!report.passed){
    blockers.push(...(report.errors||[]));
    for(const item of [...(report.metrics||[]),...(report.joins||[])]){
      if(!item.passed)blockers.push(`${item.name}: ${item.error||"Validation failed. Inspect the validation results."}`);
    }
    if(!blockers.length)blockers.push("Validation failed. Inspect the validation results.");
  }
  if(pending)blockers.push(`${pending} of ${items.length} objects still need approval. Review their evidence, then use Approve selected.`);
  box.hidden=!blockers.length;
  $("review-status").textContent=validated&&!pending?`Revision ${workspace.draft.revision} is ready. Enter the version details and confirm your review.`:"Version approval is locked until validation passes and every object is approved.";
  const list=node("ul");for(const message of blockers)list.append(node("li",message));box.append(list);
  const actions=node("div",undefined,"actions");
  const openChecks=button("Open validation & review",()=>{step("validate",true);$("validation-status").scrollIntoView({block:"nearest"});},"secondary");
  openChecks.disabled=busy;actions.append(openChecks);
  if(!dirty)for(const failed of report?.metrics||[]){
    const metric=definition.metrics.find(metric=>metric.name===failed.name);
    if(failed.passed || !metric || metric.reference_sql?.trim())continue;
    const edit=button(`Add reference SQL: ${failed.name}`,()=>{
      step("define");window.contextStudio.selectMetric(metric.id||metric.name);inspector("metric");
      $("metric-reference_sql").focus();$("metric-reference_sql").scrollIntoView({block:"center"});
    },"secondary");edit.disabled=busy;actions.append(edit);
  }
  box.append(actions);
}
function markDirty() {
  dirty = true;
  selectedReview.clear();
  renderReview();
  studioChanged();
  $("notice").textContent = "";
  $("validation-results").replaceChildren();
  controls();
}
function step(name, focus = false) {
  if(viewedVersion)return;
  if(location.hash!==stepHashes[name])history.replaceState(null,"",stepHashes[name]);
  const hub=name==="review", title=hub ? "Versions & releases" : "Semantic Studio";
  document.body.dataset.section=hub ? "hub" : "studio";
  $("workspace-breadcrumb").textContent=`Workspace / ${title}`;
  $("workspace-heading").textContent=title;
  $("workspace-description").textContent=hub
    ? "Review versions, compare changes, publish approved context, and choose the version used for queries."
    : "Build and refine semantic definitions, inspect relationships, and validate changes before review.";
  workspaceStatus();
  $("version-evidence").hidden=!["validate","review"].includes(name);
  if(name==="source" && workspace)loadDocuments();
  document.title=`${config?.title || "Cloudera"} · ${title}`;
  for(const [id,active] of [["nav-studio",!hub],["nav-versions",hub]]) {
    $(id).classList.toggle("active",active);
    if(active) $(id).setAttribute("aria-current","page");
    else $(id).removeAttribute("aria-current");
  }

  for (const tab of document.querySelectorAll("[data-step]")) {
    const active = tab.dataset.step === name;
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
    $("step-" + tab.dataset.step).hidden = !active;
    if (active && focus) tab.focus();
  }
}
for (const tab of document.querySelectorAll("[data-step]")) {
  tab.addEventListener("click", () => step(tab.dataset.step));
  tab.addEventListener("keydown", event => {
    const names = ["source","define","validate","review"], index = names.indexOf(tab.dataset.step);
    let target;
    if (event.key === "ArrowRight") target = names[(index+1)%4];
    if (event.key === "ArrowLeft") target = names[(index+3)%4];
    if (event.key === "Home") target = names[0];
    if (event.key === "End") target = names[3];
    if (target) {
      event.preventDefault();
      step(target, true);
    }
  });
}
for (const item of document.querySelectorAll("[data-next]")) item.addEventListener("click", () => step(item.dataset.next, true));
function dataTable(result) {
  const table = node("table"), head = node("thead"), tr = node("tr"), body = node("tbody");
  for (const column of result.columns) tr.append(node("th", column));
  head.append(tr);
  for (const row of result.rows) {
    const r = node("tr");
    for (const cell of row) r.append(node("td", cell === null ? "NULL" : String(cell)));
    body.append(r);
  }
  table.append(head,body);
  return table;
}
function renderTable(data) {
  selectedTable = data;
  $("table-detail").hidden = false;
  $("table-name").textContent = data.name;
  $("table-rows").textContent = `${data.row_count.toLocaleString()} rows · first ${data.rows.length} shown`;
  $("columns").replaceChildren();
  for (const column of data.columns) {
    const tr = node("tr"), meaning = node("td"), input = node("input");
    input.value = definition.field_meanings[column.qualified] || "";
    input.maxLength = 1000;
    input.setAttribute("aria-label", `Meaning of ${column.qualified}`);
    input.placeholder = "Add a business meaning";
    input.addEventListener("input", () => {
      if (input.value) definition.field_meanings[column.qualified] = input.value;
      else delete definition.field_meanings[column.qualified];
      markDirty();
    });
    meaning.append(input);
    tr.append(node("td",column.name),node("td",column.type),meaning);
    $("columns").append(tr);
  }
  $("preview").replaceChildren(dataTable({
    columns:data.columns.map(c=>c.name),rows:data.rows.map(r=>data.columns.map(c=>r[c.name]))
  }));
  for (const b of $("table-list").children) b.setAttribute("aria-pressed",String(b.dataset.table === data.name));
}
async function tables() {
  const data = await api(`/demo/api/context/tables?offset=${tablePage*pageSize}&limit=${pageSize}`);
  $("table-count").textContent = `${data.total} tables`;
  $("table-list").replaceChildren();
  for (const table of data.items) {
    const b = button(table.name, () => work(async () => {
      renderTable(await api(`/demo/api/context/table?name=${encodeURIComponent(table.name)}`));
      $("notice").textContent = "";
    }));
    b.className = "";
    b.dataset.table = table.name;
    b.setAttribute("aria-pressed",String(selectedTable?.name === table.name));
    b.append(node("small",`${table.row_count.toLocaleString()} rows · ${table.field_count} columns`));
    $("table-list").append(b);
  }
  $("previous-tables").disabled = tablePage === 0;
  $("next-tables").disabled = (tablePage+1)*pageSize >= data.total;
  if (!selectedTable && data.items.length) renderTable(await api(`/demo/api/context/table?name=${encodeURIComponent(data.items[0].name)}`));
}
$("previous-tables").addEventListener("click",()=>work(async()=>{
  tablePage--;
  await tables();
  $("notice").textContent="";
}));
$("next-tables").addEventListener("click",()=>work(async()=>{
  tablePage++;
  await tables();
  $("notice").textContent="";
}));
const metricArrayFields = ["synonyms","example_questions","inclusion_rules","exclusion_rules","ontology_concepts","evidence_refs","assumptions"];
const metricFields = ["name","description","unit","grain","time_rule","expression","dimensions","reference_sql",...metricArrayFields,"owner","rationale","confidence"];
function referenceHelp() {
  const m = definition.metrics[selectedMetric];
  $("reference-help").textContent = `Return columns in this order: ${[...m.dimensions.map(d=>d.split(".").pop()),m.name].join(", ")}. Use these exact aliases. Validation compares all rows without relying on their order.`;
}
function metricList() {
  $("metric-list").replaceChildren();
  definition.metrics.forEach((metric,index) => {
    const b = button(metric.name || "Unnamed metric",()=>{
      selectedMetric=index;
      renderMetric();
    });
    b.setAttribute("aria-pressed",String(index===selectedMetric));
    $("metric-list").append(b);
  });
  $("add-metric").disabled = definition.metrics.length >= 20;
}
function renderMetric() {
  selectedMetric = Math.min(selectedMetric,definition.metrics.length-1);
  metricList();
  const metric = definition.metrics[selectedMetric];
  for (const field of metricFields) $("metric-"+field).value = field === "dimensions" ? (metric[field] || []).join(", ") : metricArrayFields.includes(field) ? (metric[field] || []).map(v=>typeof v === "string" ? v : JSON.stringify(v)).join("\n") : (metric[field] ?? "");
  $("remove-metric").disabled = definition.metrics.length === 1;
  referenceHelp();
  renderMetricFilters();
}
for (const field of metricFields) $("metric-"+field).addEventListener("input",event=>{
  definition.metrics[selectedMetric][field] = field === "dimensions" ? event.target.value.split(",").map(v=>v.trim()).filter(Boolean) : metricArrayFields.includes(field) ? event.target.value.split("\n").map(v=>v.trim()).filter(Boolean) : field === "confidence" ? (event.target.value === "" ? null : Number(event.target.value)) : event.target.value;
  if (field === "name") metricList();
  if (["name","dimensions"].includes(field)) referenceHelp();
  markDirty();
});
$("add-metric").addEventListener("click",()=>{
  let index=definition.metrics.length+1;
  while(definition.metrics.some(m=>m.name===`metric_${index}`)) index++;
  definition.metrics.push({
    id:`metric-${crypto.randomUUID()}`,name:`metric_${index}`,description:"",unit:"count",grain:"One aggregate over the selected source records",time_rule:`Reporting timezone: ${config.timezone}; no date filter`,expression:"",dimensions:[],reference_sql:""
  });
  selectedMetric=definition.metrics.length-1;
  renderMetric();
  markDirty();
  $("metric-name").focus();
});
$("remove-metric").addEventListener("click",()=>{
  definition.metrics.splice(selectedMetric,1);
  selectedMetric=0;
  renderMetric();
  markDirty();
});
for (const key of ["title","description"]) $("context-"+key).addEventListener("input",event=>{
  definition[key]=event.target.value;
  markDirty();
});
function renderJoins() {
  selectedJoin=Math.max(0,Math.min(selectedJoin,definition.joins.length-1));
  $("joins").replaceChildren();
  definition.joins.forEach((join,index)=>{
    const row=node("div",undefined,"join-row"), grid=node("div",undefined,"form-grid two");
    for (const [key,label] of [["name","Relationship name"],["meaning","Business meaning"],["from_field","Source field (many)"],["to_field","Target field (one)"]]) {
      const l=node("label",label), input=node("input");
      input.value=join[key];
      input.maxLength=key==="meaning"?500:key==="name"?128:260;
      input.addEventListener("input",()=>{
        join[key]=input.value;
        markDirty();
      });
      l.append(input);
      grid.append(l);
    }
    row.append(grid,button("Remove relationship",()=>{
      definition.joins.splice(index,1);
      renderJoins();
      markDirty();
    },"secondary danger"));
    row.hidden=index!==selectedJoin;
    $("joins").append(row);
  });
  if (!definition.joins.length) $("joins").append(node("p","No relationships. Metrics can group by fields in their own table.","muted"));
  $("add-join").disabled=definition.joins.length>=20;
}
$("add-join").addEventListener("click",()=>{
  definition.joins.push({
    id:`join-${crypto.randomUUID()}`,name:"relationship_"+(definition.joins.length+1),from_field:"",to_field:"",meaning:"",cardinality:"many_to_one"
  });
  selectedJoin=definition.joins.length-1;
  renderJoins();
  markDirty();
});
function renderValidation() {
  const container=$("validation-results");
  container.replaceChildren();
  const report=workspace.draft.validation;
  if (!report || dirty) return;
  for (const message of report.errors) container.append(node("p",message,"panel fail"));
  for (const metric of report.metrics) {
    const card=node("div",undefined,"panel"), header=node("div",undefined,"panel-heading");
    header.append(node("h2",metric.name),node("span",metric.passed?"Reconciled":"Needs attention",metric.passed?"pass":"fail"));
    card.append(header);
    if (metric.error) card.append(node("p",metric.error,"fail"));
    const grid=node("div",undefined,"evidence-grid");
    for (const [label,sql,result] of [["Compiled SQL",metric.sql,metric.result],["Independent reference SQL",metric.reference_sql,metric.reference_result]]) {
      const side=node("div");
      side.append(node("h3",label));
      if(sql)side.append(node("pre",sql));
      if(result){
        const scroll=node("div",undefined,"scroll");
        scroll.append(dataTable(result));
        side.append(scroll);
      } grid.append(side);
    }
    card.append(grid);
    container.append(card);
  }
  if(report.joins.length){
    const card=node("div",undefined,"panel");
    card.append(node("h2","Relationship checks"));
    const scroll=node("div",undefined,"scroll");
    scroll.append(dataTable({
      columns:["Relationship","Result","Duplicate keys","Null target keys","Unmatched source rows"],rows:report.joins.map(j=>[j.name,j.passed?"Passed":"Failed",j.duplicate_keys,j.null_target_keys,j.unmatched_source_rows])
    }));
    card.append(scroll);
    container.append(card);
  }
  const audit=node("details"), dl=node("dl");
  audit.append(node("summary","Validation binding"));
  for(const [label,value] of [["Draft revision",report.revision],["Checked at",report.checked_at],["Validation hash",report.validation_sha256]])dl.append(node("dt",label),node("dd",value));
  audit.append(dl);
  container.append(audit);
}
function versionUrl(version) {
  const url=new URL("/demo/context",location.origin);
  if(currentSource)url.searchParams.set("source",currentSource);
  if(version)url.searchParams.set("version",version);
  url.hash="hub";
  return url.href;
}
function prepareVersionView(){
  document.body.dataset.view="version";
  $("workspace-heading").textContent=`Version ${viewedVersion}`;
  $("workspace-description").textContent="Read-only · Saved definitions and evidence from this reviewed version.";
  $("workspace-breadcrumb").textContent="Workspace / Versions & releases / View version";
  $("version-back").href=versionUrl();
  $("nav-versions").href=versionUrl();
  $("nav-studio").classList.remove("active");
  $("nav-studio").removeAttribute("aria-current");
  $("nav-versions").classList.add("active");
  $("nav-versions").setAttribute("aria-current","page");
  $("version-navigation").hidden=false;
}
function versionProperties(parent,entries){
  const list=node("dl",undefined,"version-properties");
  for(const [label,value] of entries){
    if(value===undefined || value===null || value==="")continue;
    const content=node("dd");
    content.append(typeof value==="object"?node("pre",JSON.stringify(value,null,2)):node("span",String(value)));
    list.append(node("dt",label),content);
  }
  parent.append(list);
}
function versionSection(title){
  const section=node("section",undefined,"version-section");section.append(node("h3",title));
  $("version-content").append(section);return section;
}
function versionObjects(title,items,name){
  const section=versionSection(`${title} (${items.length})`);
  if(!items.length)section.append(node("p","None recorded in this version.","muted"));
  for(const item of items){
    const detail=node("details");detail.append(node("summary",name(item)));
    versionProperties(detail,Object.entries(item).map(([key,value])=>[key.replaceAll("_"," "),value]));section.append(detail);
  }
}
async function loadVersionCanvas(release){
  const status=$("version-graph-status");
  try{
    const graph=await api(`/demo/api/context/source-graph?version=${encodeURIComponent(release.version)}`);
    if(graph.version!==release.version || graph.context_sha256!==release.context_sha256)throw new Error("The graph does not match this saved version.");
    const documents=release.artifacts?.documents||[];
    const documentId=doc=>(doc.origin==="serving_document"?"source-document:":"document:")+doc.id;
    if(documents.length){
      graph.nodes.push({id:"evidence:documents",type:"document_group",label:`Documents (${documents.length})`});
      const tables=new Set(graph.nodes.filter(n=>n.type==="dataset").map(n=>n.id)),linked=new Set();
      for(const doc of documents){
        const id=documentId(doc);
        graph.nodes.push({...doc,id,type:"document",label:doc.filename||doc.id});
        for(const link of doc.semantic_links||[]){
          const table=link.target.startsWith("table:")?link.target.slice(6):link.target.startsWith("field:")?link.target.slice(6).split(".")[0]:null;
          if(table && tables.has(table))linked.add(table);
        }
        for(const [index,link] of (doc.entity_links||[]).entries()){
          if(!tables.has(link.table))continue;
          linked.add(link.table);
          graph.edges.push({id:`evidence:${id}:${index}`,source:id,target:link.table,kind:"document_evidence",label:`${link.column} = ${link.value}`,document_id:id});
        }
      }
      for(const table of linked)graph.edges.push({id:`evidence:group:${table}`,source:"evidence:documents",target:table,kind:"document_evidence",label:"Supporting documents",document_id:"evidence:documents"});
    }
    const inspect=object=>{
      const detail=$("version-object-detail");detail.replaceChildren(node("h3",object.label||object.name||object.id));
      if(object.type==="document_group"){
        detail.append(node("p","Choose a saved document to inspect its content and record links."));
        const list=node("div",undefined,"version-document-links");
        for(const doc of documents)list.append(button(doc.filename||doc.id,()=>{
          const saved=graph.nodes.find(n=>n.id===documentId(doc));versionCanvas.focus(saved.id);inspect(saved);
        },"secondary"));
        detail.append(list);return;
      }
      versionProperties(detail,Object.entries(object).filter(([key])=>!["change_status","type","kind","label"].includes(key)).map(([key,value])=>[key.replaceAll("_"," "),value]));
    };
    versionCanvas?.destroy();
    versionCanvas=window.HeliosCanvas.mount($("version-canvas"),{
      readOnly:true,host:{getState:()=>({definition:release.definition})},onSelect:inspect
    });
    versionCanvas.update({...graph,saved_revision:release.revision,scope:release.context_sha256,dirty:false});
    status.textContent=`${release.version} · Read-only · Select objects to inspect; use search, zoom, and View options to explore.`;
  }catch(err){
    status.textContent=`Version canvas unavailable: ${err.message}`;
  }
}
async function loadVersionView(){
  prepareVersionView();
  const release=await api(`/demo/api/context/version?version=${encodeURIComponent(viewedVersion)}`);
  inspectedVersion=release;
  const def=release.definition,artifacts=release.artifacts;
  $("pack-title").textContent=def.title;
  document.title=`${def.title} · ${release.version} · Read-only`;
  $("version-heading").textContent=`${release.version} · Read-only`;
  $("version-summary").replaceChildren(node("p",def.description));
  versionProperties($("version-summary"),[
    ["Reviewed by",release.reviewer],["Reviewed at",new Date(release.reviewed_at).toLocaleString()],
    ["Review note",release.note],["Saved revision",release.revision],
    ["Validation",release.validation?.passed ? "Passed at review" : "See saved validation evidence"],
    ["Source snapshot",release.snapshot_sha256],["Context hash",release.context_sha256]
  ]);
  $("version-content").replaceChildren();
  versionObjects("Metrics",def.metrics||[],item=>item.name);
  versionObjects("Relationships",def.joins||[],item=>item.name);
  const metadata=versionSection("Business metadata");
  versionProperties(metadata,[["Dataset meanings",def.dataset_meanings],["Field meanings",def.field_meanings],["Field roles",def.field_roles],["Glossary terms",def.glossary_terms]]);
  if(artifacts){
    versionObjects("Supporting documents",artifacts.documents||[],item=>item.filename||item.id);
    const ontology=versionSection("Ontology");
    ontology.append(node("p","Saved entity mappings and relationships for this version. Document statements retain their recorded evidence status.","help"));
    versionProperties(ontology,[["Ontology",artifacts.ontology],["Artifact quality",artifacts.quality]]);
  }else versionSection("Context artifacts").append(node("p","This older version has no archived context artifacts. Its saved definitions and evidence are available below."));
  const evidence=versionSection("Validation & review evidence");
  for(const [title,value] of [["Saved validation results",release.validation],["Object review decisions",release.item_review]]){
    const detail=node("details");detail.append(node("summary",title),node("pre",JSON.stringify(value,null,2)));evidence.append(detail);
  }
  $("version-json").textContent=JSON.stringify(release,null,2);
  $("version-detail").hidden=false;
  await loadVersionCanvas(release);
  $("notice").textContent="";
}
function renderVersions() {
  $("versions").replaceChildren();
  if(!workspace.versions.length)$("versions").append(node("p","No reviewed versions yet. Your saved draft remains editable.","muted"));
  syncVersionSelectors();
  for(const version of workspace.versions){
    const row=node("div",undefined,"version-row"), description=node("div"), actions=node("div",undefined,"actions");
    const title=node("a",version.version,"version-link");title.href=versionUrl(version.version);
    description.append(title,node("p",`Revision ${version.revision} · ${version.reviewer} · ${new Date(version.reviewed_at).toLocaleString()}`),node("p",version.note));
    const view=node("a","View version","secondary version-view-link");view.href=versionUrl(version.version);actions.append(view);
    const published=Boolean(version.published);
    if (!published) actions.append(button("Publish",()=>work(async()=>{
      if (!window.confirm(`Publish reviewed version ${version.version} to this local workspace?`)) return;
      const data=await api("/demo/api/context/publish",{
        ...binding(),version:version.version,context_sha256:version.context_sha256,confirmed:true
      });
      accept(data,false);
      $("notice").textContent=`Version ${version.version} published locally. Activate it to change queries.`;
    }),"secondary publish-version"));
    actions.append(button("Create draft",()=>work(async()=>{
      if (dirty && !window.confirm("Replace unsaved edits with a draft from this version?")) return;
      await acceptWithGraph(await api("/demo/api/context/restore",{
        ...binding(),revision:workspace.draft.revision,version:version.version
      }));
      step("define");
      $("notice").textContent=`Draft restored from ${version.version}. Save, validate and review its new revision.`;
    }),"secondary restore-version"));
    description.append(node("span",published?"Published":"Reviewed · unpublished","badge subtle"));
    const active=workspace.active_version===version.version;
    const activate=button(active?"Active for queries":"Use for queries",()=>work(async()=>{
      const data=await api("/demo/api/context/activate",{
        ...binding(),version:version.version,context_sha256:version.context_sha256
      });
      // Activation must not discard unsaved edits in the current tab.
      workspace.active_version=data.active_version;
      workspace.versions=data.versions;
      renderVersions();
      $("notice").textContent=`Version ${version.version} is active. Reload any open query page to use it.`;
    }),active?"secondary":"");
    activate.classList.add("activate-version");
    activate.disabled=active || !published;
    actions.append(activate);
    const comparison=node("details",undefined,"version-comparison");
    comparison.append(node("summary",`Compare ${version.version}`));
    const compareControls=node("div",undefined,"version-compare-controls");
    const label=node("label","Compare with"),baseline=node("select");
    baseline.setAttribute("aria-label",`Compare ${version.version} with`);
    baseline.append(new Option("Starter definitions","starter"));
    for(const other of workspace.versions){
      if(other.version!==version.version)baseline.append(new Option(other.version,other.version));
    }
    baseline.append(new Option("Current saved draft","draft"));
    const previous=workspace.versions.filter(other=>other.revision<version.revision).sort((a,b)=>b.revision-a.revision)[0];
    baseline.value=previous?.version || "starter";
    label.append(baseline);
    const result=node("div",undefined,"version-comparison-result");
    result.setAttribute("aria-live","polite");
    baseline.addEventListener("change",()=>result.replaceChildren());
    compareControls.append(label,button("Compare",()=>work(async()=>{
      // The comparison API accepts the draft only as the target, never as a baseline.
      const draft=baseline.value==="draft";
      await compareVersions(draft?"draft":version.version,draft?version.version:baseline.value,result);
      $("notice").textContent="Comparison loaded for the selected version.";
    }),"secondary"));
    comparison.append(compareControls,node("p","Changes show the baseline before and the selected version after. For draft comparisons, the saved draft is after.","help"),result);
    row.append(description,actions,comparison);
    $("versions").append(row);
  }
}
async function acceptWithGraph(data) {
  const graph=await api("/demo/api/context/source-graph");
  if(graph.draft_revision !== data.draft.revision) {
    throw new Error("The source graph revision changed. Reload the saved workspace before editing.");
  }
  sourceGraph=graph;
  accept(data);
}
function accept(data, resetEditors=true) {
  workspace=data;
  documentsState=null;
  loadDocuments();
  if(resetEditors) selectedReview.clear();
  if(resetEditors){
    definition=structuredClone(data.draft.definition);
    dirty=false;
    $("context-title").value=definition.title;
    $("context-description").value=definition.description;
    renderMetric();
    renderJoins();
    if(selectedTable)renderTable(selectedTable);
  }
  renderValidation();
  renderVersions();
  renderArtifactVersions();
  renderReview();
  controls();
  studioChanged();
}
$("save").addEventListener("click",()=>work(async()=>{
  const invalid=$("metric-filters").querySelector("input:invalid");
  if(invalid){invalid.reportValidity();throw new Error("Correct the structured filter value before saving.");}
  await acceptWithGraph(await api("/demo/api/context/draft",{
    ...binding(),revision:workspace.draft.revision,definition
  }));
  $("confirmed").checked=false;
  $("notice").textContent=`Draft revision ${workspace.draft.revision} saved. Validate this revision before review.`;
},"Saving draft…"));
$("validate").addEventListener("click",()=>work(async()=>{
  accept(await api("/demo/api/context/validate",{
    ...binding(),revision:workspace.draft.revision
  }));
  $("confirmed").checked=false;
  $("notice").textContent=workspace.draft.validation.passed?"Validation passed. Continue to review when you have checked the evidence.":"Validation completed. Resolve the reported issues before review.";
},"Executing compiled and reference SQL…"));
$("review-form").addEventListener("submit",event=>{
  event.preventDefault();
  work(async()=>{
    accept(await api("/demo/api/context/review",{
      ...binding(),revision:workspace.draft.revision,validation_sha256:workspace.draft.validation.validation_sha256,version:$("version").value,reviewer:$("reviewer").value,note:$("review-note").value,confirmed:$("confirmed").checked
    }));
    $("confirmed").checked=false;
    $("notice").textContent="Reviewed version saved. Publish it, then activate it when you want queries to use it.";
  },"Saving reviewed version…");
});
$("download-version").addEventListener("click",()=>{
  if(!inspectedVersion)return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(inspectedVersion,null,2)+"\n"],{
    type:"application/json"
  }));
  const link=node("a");
  link.href=url;
  link.download=`${config.pack_id}-context-${inspectedVersion.version}.json`;
  link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
});
async function load() {
  config=await api("/demo/api/config");
  currentSource=config.connection_id;
  const materialsUrl=new URL("/demo/materials",location.origin);
  materialsUrl.searchParams.set("source",currentSource);
  $("add-supporting-material").href=materialsUrl.pathname+materialsUrl.search;
  $("source-nav-title").textContent=config.connection_name;
  for(const link of document.querySelectorAll("[data-source-link]")){
    const url=new URL(link.href);url.searchParams.set("source",currentSource);link.href=url;
  }
  if(viewedVersion){await loadVersionView();return;}
  accept(await api("/demo/api/context"));
  $("pack-title").textContent=config.title;
  document.title=`${config.title} · ${$("step-review").hidden ? "Semantic Studio" : "Versions & releases"}`;
  $("source-binding").replaceChildren();
  for(const [label,value] of [["Pack",config.pack_id],["Snapshot",config.snapshot_sha256],["Reporting timezone",config.timezone],["Storage","Local workspace; scoped to this source snapshot"]])$("source-binding").append(node("dt",label),node("dd",value));
  await tables();
  await loadProposals();
  await loadDocuments();
  renderArtifactVersions();
  sourceGraph=await api("/demo/api/context/source-graph");
  if (!canvasHandle && window.HeliosCanvas) {
    canvasHandle = window.HeliosCanvas.mount($("studio-canvas"), {
      host:window.contextStudio,
      onReviewItem:showChangeInspector
    });
  } studioChanged();
  $("notice").textContent="";
  if(new URL(location.href).searchParams.get("draft")==="ai"){
    step("source");$("evidence-draft").scrollIntoView({block:"start"});
  }
}
$("reload").addEventListener("click",()=>{
  if(dirty&&!window.confirm("Discard unsaved changes and reload the saved draft?"))return;
  work(load,"Loading saved workspace…");
});
window.addEventListener("beforeunload",event=>{
  if(dirty){
    event.preventDefault();
    event.returnValue="";
  }
});
const selectedReview = new Set();
let reviewPage = 0, batchDecision = "approve", canvasHandle, sourceGraph;
let reviewPageSize = 10;
function studioChanged() {
  if (!definition) return;
  $("definition-code").textContent = JSON.stringify(definition,null,2);
  window.dispatchEvent(new CustomEvent("studio:change", {
    detail:window.contextStudio.getState()
  }));
  renderTree();
  if(canvasHandle && sourceGraph) {
    let note=$("canvas-evidence-note");
    if(!note) { note=node("p",undefined,"canvas-evidence-note");note.id="canvas-evidence-note";$("studio-canvas").prepend(note); }
    note.textContent=dirty ? `Unsaved edits · change highlights are paused. Save revision ${workspace.draft.revision+1} to refresh evidence.` : `Saved revision ${workspace.draft.revision} · changes against ${workspace.review?.baseline_version || "starter"}`;
    canvasHandle.update({
    ...sourceGraph,
    ...documentGraph(),
    scope:`${config.pack_id}:${config.snapshot_sha256}`,
    baseline_version:workspace.review?.baseline_version || "starter",
    saved_revision:workspace.draft.revision,
    dirty,
    review_items:dirty ? [] : workspace.review?.items||[]
    });
  }
  const inspectedDocument=$("source-inspector").dataset.documentId;
  if(inspectedDocument && documentsState?.revision===workspace.draft.revision)showDocumentInspector(inspectedDocument);
}
window.contextStudio = {
  getState:()=>({
    config,workspace,definition,dirty,busy
  }),
  selectMetric:id=>{
    const name=String(id).replace(/^metric:/, "");
    const index=definition.metrics.findIndex((m,i)=>m.id===id || m.name===name || String(i)===String(id));
    if(index>=0){
      selectedMetric=index;
      renderMetric();
      $("metric-editor").scrollIntoView({
        block:"nearest"
      });
    }
  },
  editJoin:id=>{
    const name=String(id).replace(/^join:/, "");
    const index=definition.joins.findIndex((j,i)=>j.id===id || j.name===name || String(i)===String(id));
    if(index>=0){
      selectedJoin=index;
      [...$("joins").children].forEach((row,i)=>row.hidden=i!==index);
      $("joins").children[index]?.scrollIntoView({
        block:"nearest"
      });
      $("joins").children[index]?.querySelector("input")?.focus();
    }
  },
  updateDefinition:mutator=>{
    if(busy) return;
    mutator(definition);
    renderMetric();
    renderJoins();
    markDirty();
  }
};
document.addEventListener("studio:select",event=>{
  const {
    type,id,node:object
  }=event.detail||{
  };
  if(type==="document")showDocumentInspector(id);
  if(type==="document_group")showDocumentGroup();
  if(type==="metric"){
    window.contextStudio.selectMetric(id);
    inspector("metric");
  }if(type==="join" || type==="relationship"){
    window.contextStudio.editJoin(id);
    inspector("join");
  }if(type==="dataset" || type==="column" || type==="table")work(async()=>{
    const name=object?.table || (type==="column" ? object?.qualified?.split(".")[0] : object?.name) || id.replace(/^dataset:/,"");
    const data=await api(`/demo/api/context/table?name=${encodeURIComponent(name)}`);
    renderTable(data);
    const box=$("source-inspector");
    delete box.dataset.documentId;
    box.replaceChildren(node("h2",type==="column"?object.qualified:data.name),node("p",`${data.row_count.toLocaleString()} source rows · ${data.columns.length} typed fields`));
    for(const column of data.columns){
      if(type==="column" && column.qualified!==object.qualified)continue;
      const label=node("label",`${column.name} · ${column.type}`),input=node("input");
      input.value=definition.field_meanings[column.qualified]||"";
      input.placeholder="Business meaning";
      input.maxLength=1000;
      input.addEventListener("input",()=>{
        if(input.value) definition.field_meanings[column.qualified]=input.value;
        else delete definition.field_meanings[column.qualified];
        markDirty();
      });
      label.append(input);
      box.append(label);
    }box.append(button("Open full source sample",()=>step("source")));
    inspector("source");
  });
});
function inspector(type){
  if(type!=="source")delete $("source-inspector").dataset.documentId;
  const editable=[...document.querySelectorAll(".studio-inspector > .panel")].filter(panel=>!["source-inspector","changes-inspector"].includes(panel.id));
  editable.forEach((panel,index)=>panel.hidden=["context","metric","join"][index]!==type);
  $("source-inspector").hidden=type!=="source";
  $("changes-inspector").hidden=type!=="changes";
  document.querySelectorAll("[data-inspector]").forEach(button=>button.setAttribute("aria-pressed",String(button.dataset.inspector===type)));
}
function showChangeInspector(item){
  const box=$("changes-inspector");
  box.replaceChildren(node("h2",`${item.name} · ${item.change}`),node("p",`Saved revision ${workspace.draft.revision} · baseline ${workspace.review?.baseline_version||"starter"}`,"help"));
  if(dirty) box.append(node("p","Save unsaved edits to refresh change evidence.","pending"));
  else box.append(changeDiff(item));
  inspector("changes");
}

for(const button of document.querySelectorAll("[data-inspector]"))button.addEventListener("click",()=>inspector(button.dataset.inspector));
$("nav-versions").addEventListener("click",()=>step("review"));
$("edit-draft").addEventListener("click",()=>step("define",true));
$("nav-studio").addEventListener("click",event=>{
  event.preventDefault();
  step("define");
});
function renderTree(){
  const tree=$("studio-tree");
  tree.replaceChildren(node("h3","Semantic objects"));
  for(const [label,objects,type] of [["Datasets",(sourceGraph?.nodes||[]).filter(n=>n.kind==="dataset" || n.type==="dataset"),"dataset"],["Metrics",definition.metrics,"metric"],["Relationships",definition.joins,"join"],["Documents",currentDocuments().map(doc=>({id:documentObjectId(doc),label:doc.filename.split("/").pop()})),"document"]]){
    const group=node("details");
    group.open=type!=="document";
    group.append(node("summary",`${label} (${objects.length})`));
    for(const object of objects){
      const id=object.id || object.name;
      const b=button(object.name || object.label,()=>{
        canvasHandle?.focus(id);
        document.dispatchEvent(new CustomEvent("studio:select",{
          detail:{
            type,id,node:object
          }
        }));
      });
      b.dataset.objectId=id;
      b.classList.add("tree-object");
      group.append(b);
    }tree.append(group);
  }
}
function matchingReview(){
  const query=$("review-filter").value.toLowerCase(),change=$("review-change").value;
  return (workspace?.review?.items||[]).filter(item=>(!query || `${item.name} ${item.kind}`.toLowerCase().includes(query)) && (!change || item.change===change));
}
function reviewTechnicalState(item){
  const validation=workspace.draft.validation;
  if(dirty)return {label:"Unsaved changes",style:"pending",reasons:["Save and validate your changes before review."]};
  if(!validation || validation.revision!==workspace.draft.revision){
    return {label:"Not validated",style:"pending",reasons:[workspace.draft.revision===0 ? "Save the draft, then run validation." : "Run validation for this saved draft."]};
  }
  if(!item.eligible)return {label:"Blocked",style:"fail",reasons:item.reasons?.length ? item.reasons : ["Inspect the validation results above."]};
  return {label:"Ready for review",style:"pass",reasons:[]};
}
function renderReview(){
  if(!workspace)return;
  $("review-scope").textContent=`Approval scope: revision ${workspace.draft.revision}, baseline ${workspace.review?.baseline_version||"starter"}. Display comparison does not change this scope.`;
  const items=matchingReview(),pages=Math.max(1,Math.ceil(items.length/reviewPageSize));
  reviewPage=Math.max(0,Math.min(reviewPage,pages-1));
  const page=items.slice(reviewPage*reviewPageSize,(reviewPage+1)*reviewPageSize);
  $("review-items").replaceChildren();
  for(const item of page){
    const tr=node("tr"),cell=node("td"),check=node("input");
    check.type="checkbox";
    check.checked=selectedReview.has(item.id);
    check.disabled=dirty || busy;
    check.setAttribute("aria-label",`Select ${item.kind} ${item.name}`);
    check.addEventListener("change",()=>{
      check.checked?selectedReview.add(item.id):selectedReview.delete(item.id);
      renderReview();
      controls();
    });
    cell.append(check);
    const technical=node("td",undefined,"review-technical"),state=reviewTechnicalState(item);
    technical.append(node("span",state.label,state.style));
    for(const reason of state.reasons)technical.append(node("p",reason,"review-reason"));
    tr.append(cell,node("td",`${item.name} · ${item.kind}`),node("td",item.change,`change-${item.change}`),technical,node("td",item.status.replaceAll("_"," ")));
    const evidence=node("td"),details=node("details");
    details.append(node("summary",item.change==="unchanged"?"View definition":"Before / after"));
    details.append(changeDiff(item));
    evidence.append(details);
    if(item.kind==="document")evidence.append(button("Open in canvas",()=>openDocumentCanvas(item.id),"secondary review-document-link"));
    tr.append(evidence);
    $("review-items").append(tr);
  }
  $("selection-count").textContent=`${selectedReview.size} selected · ${items.length} matching · ${(workspace.review?.items||[]).length} total objects`;
  renderReviewPagination(items.length,pages);
  if(!items.length){
    const tr=node("tr"),td=node("td",dirty?"Save and validate to review current changes.":"No matching review objects.");
    td.colSpan=6;
    tr.append(td);
    $("review-items").append(tr);
  }
}
function renderReviewPagination(total,pages){
  $("review-range").textContent=total?`${reviewPage*reviewPageSize+1}–${Math.min(total,(reviewPage+1)*reviewPageSize)} of ${total} objects`:"0 objects";
  $("review-page").textContent=total?`Page ${reviewPage+1} of ${pages}`:"No matching pages";
  $("review-prev").disabled=!total||reviewPage===0;
  $("review-next").disabled=!total||reviewPage>=pages-1;
  const numbers=$("review-page-numbers");numbers.replaceChildren();
  if(!total)return;
  const visible=new Set([0,pages-1,reviewPage-1,reviewPage,reviewPage+1]);
  if(pages<=5)for(let i=0;i<pages;i++)visible.add(i);
  let previous=-1;
  for(const index of [...visible].filter(i=>i>=0&&i<pages).sort((a,b)=>a-b)){
    if(previous>=0&&index>previous+1){const gap=node("span","…","review-page-gap");gap.setAttribute("aria-hidden","true");numbers.append(gap);}
    const control=button(String(index+1),()=>{reviewPage=index;renderReview();numbers.querySelector('[aria-current="page"]')?.focus();},"secondary");
    control.setAttribute("aria-label",`Page ${index+1}`);
    if(index===reviewPage)control.setAttribute("aria-current","page");
    numbers.append(control);previous=index;
  }
}
$("review-page-size").addEventListener("change",()=>{
  const first=reviewPage*reviewPageSize;
  reviewPageSize=Number($("review-page-size").value);
  reviewPage=Math.floor(first/reviewPageSize);
  renderReview();
});
for(const id of ["review-filter","review-change"])$(id).addEventListener("input",()=>{
  reviewPage=0;
  renderReview();
});
$("review-prev").addEventListener("click",()=>{
  reviewPage--;
  renderReview();
});
$("review-next").addEventListener("click",()=>{
  reviewPage++;
  renderReview();
});
$("select-page").addEventListener("click",()=>{
  matchingReview().slice(reviewPage*reviewPageSize,(reviewPage+1)*reviewPageSize).forEach(item=>selectedReview.add(item.id));
  renderReview();
  controls();
});
$("select-all").addEventListener("click",()=>{
  matchingReview().forEach(item=>selectedReview.add(item.id));
  renderReview();
  controls();
});
$("clear-selection").addEventListener("click",()=>{
  selectedReview.clear();
  renderReview();
  controls();
});
function openBatch(decision){
  batchDecision=decision;
  const items=(workspace.review?.items||[]).filter(item=>selectedReview.has(item.id));
  $("batch-title").textContent=decision==="approve"?"Approve selected definitions":"Request definition changes";
  $("batch-preview").textContent=`${items.filter(item=>item.eligible).length} eligible · ${items.filter(item=>!item.eligible).length} blocked · ${items.length} objects · saved revision ${workspace.draft.revision} · local reviewer attribution`;
  $("batch-objects").replaceChildren(...items.map(item=>node("p",`${item.kind}: ${item.name} (${item.change})`)));
  $("batch-confirmed").checked=false;
  $("batch-dialog").showModal();
}
$("approve-selected").addEventListener("click",()=>openBatch("approve"));
$("request-selected").addEventListener("click",()=>openBatch("request_changes"));
$("batch-cancel").addEventListener("click",()=>$("batch-dialog").close());
$("batch-form").addEventListener("submit",event=>{
  event.preventDefault();
  const ids=[...selectedReview];
  $("batch-dialog").close();
  work(async()=>{
    const result=await api("/demo/api/context/batch-review",{
      ...binding(),revision:workspace.draft.revision,validation_sha256:workspace.draft.validation.validation_sha256,item_ids:ids,decision:batchDecision,reviewer:$("batch-reviewer").value,note:$("batch-note").value,confirmed:$("batch-confirmed").checked
    });
    selectedReview.clear();
    accept(result.workspace || result);
    const accepted=(result.outcomes||[]).filter(item=>item.accepted).length;
    $("notice").textContent=`${accepted} decisions recorded · ${ids.length-accepted} rejected. ${(result.outcomes||[]).filter(item=>!item.accepted).map(item=>`${
      item.id
    }: ${
      (item.reasons||[]).join("; ")
    }`).join(" | ")}`;
  });
});
function changeDiff(item){
  const grid=node("div",undefined,"diff-grid"),before=item.before||{
  },after=item.after||{
  },keys=new Set([...Object.keys(before),...Object.keys(after)]);
  for(const [title,value] of [["Before",before],["After",after]]){
    const panel=node("div");
    panel.append(node("h3",title));
    for(const key of keys){
      const changed=JSON.stringify(before[key])!==JSON.stringify(after[key]);
      const row=node("div",`${key}: ${JSON.stringify(value[key] ?? "—")}`,changed?"diff-changed":"diff-field");
      panel.append(row);
    }grid.append(panel);
  }return grid;
}
function syncVersionSelectors(){
  const select=$("baseline"),value=select.value;
  select.replaceChildren(new Option("Starter definitions","starter"));
  for(const version of workspace.versions)select.append(new Option(version.version,version.version));
  const chosen=workspace.review?.baseline_version||value;
  if([...select.options].some(option=>option.value===chosen))select.value=chosen;
}
async function compareVersions(version,baseline,container=$("review-comparison")){
  const data=await api(`/demo/api/context/compare?version=${encodeURIComponent(version)}&baseline_version=${encodeURIComponent(baseline)}`);
  container.replaceChildren(node("h3",`${version} compared with ${baseline}`));
  for(const item of data.items || data.changes || []){
    const detail=node("details");
    detail.append(node("summary",`${item.name || item.id} · ${item.change || "changed"}`),changeDiff(item));
    container.append(detail);
  }if(!container.querySelector("details"))container.append(node("pre",JSON.stringify(data,null,2)));
}
$("baseline").addEventListener("change",()=>work(async()=>{
  await compareVersions("draft",$("baseline").value);
  $("review-comparison").scrollIntoView({
    block:"nearest"
  });
  $("notice").textContent="Comparison loaded. Decisions remain bound to the current saved draft.";
}));
function renderMetricFilters() {
  const metric=definition.metrics[selectedMetric],box=$("metric-filters");
  box.replaceChildren();
  (metric.filters || []).forEach((filter,index)=>{
    const row=node("div",undefined,"join-row"),grid=node("div",undefined,"form-grid two");
    const fieldLabel=node("label","Source field"),field=node("input");field.value=filter.field;field.placeholder="table.column";
    field.addEventListener("input",()=>{filter.field=field.value;markDirty();});fieldLabel.append(field);
    const opLabel=node("label","Operator"),op=node("select");
    for(const name of ["=","!=",">",">=","<","<=","in","not in","between","like","is null","is not null"]){const option=node("option",name);option.value=name;op.append(option);}op.value=filter.op;
    opLabel.append(op);grid.append(fieldLabel,opLabel);
    const valueLabel=node("label","Value (JSON number, string, or array)"),value=node("input");value.value=JSON.stringify(filter.value ?? null);value.disabled=["is null","is not null"].includes(filter.op);
    value.addEventListener("change",()=>{try{filter.value=JSON.parse(value.value);value.setCustomValidity("");markDirty();}catch{value.setCustomValidity("Enter a valid JSON value, such as 5, \"active\", or [1,2].");value.reportValidity();}});
    op.addEventListener("change",()=>{filter.op=op.value;if(["is null","is not null"].includes(filter.op))filter.value=null;renderMetricFilters();markDirty();});
    valueLabel.append(value);row.append(grid,valueLabel,button("Remove filter",()=>{metric.filters.splice(index,1);renderMetricFilters();markDirty();},"secondary danger"));box.append(row);
  });
  $("add-filter").disabled=(metric.filters || []).length>=20;
}
$("add-filter").addEventListener("click",()=>{
  const metric=definition.metrics[selectedMetric];metric.filters ||= [];metric.filters.push({field:"",op:"=",value:null});renderMetricFilters();markDirty();
});
let proposalState = {items:[], llm_configured:false}, selectedProposal;
function proposalControls() {
  const blocked=busy || !workspace || dirty;
  $("propose-evidence").disabled=blocked;
  $("document-upload").disabled=blocked || Boolean($("document-file").validationMessage);
  $("document-add").disabled=busy || !workspace;
  $("document-cancel").disabled=busy;
  $("documents-review").disabled=busy || !workspace;
  if(dirty)$("documents-status").textContent="Save or reload your metric edits before adding a document.";
  $("artifact-refresh").disabled=busy || !workspace;
  for(const input of $("document-form").querySelectorAll("input"))input.disabled=busy;
  $("propose-llm").disabled=blocked || !(proposalState.llm_available || proposalState.llm_configured);
  const apply=$("proposal-apply");
  if(apply) apply.disabled=blocked || selectedProposal.revision!==workspace.draft.revision;
  $("proposal-status").textContent=dirty ? "Save or reload your unsaved changes before generating or applying a candidate." : (proposalState.llm_available || proposalState.llm_configured) ? "LLM generation is configured. Every candidate requires explicit application and human review." : "Evidence generation is available. Configure an LLM endpoint to enable LLM generation.";
}
function inspectValue(label,value,parent) {
  if(value===undefined || value===null)return;
  const detail=node("details");
  detail.append(node("summary",label),node("pre",typeof value === "string" ? value : JSON.stringify(value,null,2)));
  parent.append(detail);
}
function previewProposal(proposal) {
  selectedProposal=proposal;
  const box=$("proposal-preview");box.hidden=false;box.replaceChildren();
  box.append(node("h3",proposal.label || "Candidate draft"),node("p",`Candidate for saved revision ${proposal.revision}. Application creates a new draft revision; validation and human review follow.`,"help"));
  const candidate=proposal.definition || {};
  const list=node("ul");
  for(const metric of candidate.metrics || [])list.append(node("li",`${metric.name}: ${metric.description || "No description"}`));
  box.append(list);
  inspectValue("Provenance",proposal.provenance,box);
  inspectValue("Source evidence",proposal.evidence,box);
  inspectValue("Assumptions",(candidate.metrics || []).flatMap(metric=>metric.assumptions || []),box);
  inspectValue("Warnings",proposal.warnings || [],box);
  inspectValue("Candidate definition",candidate,box);
  const apply=button("Apply to draft",()=>work(async()=>{
    if(dirty)throw new Error("Save or reload unsaved changes before applying a candidate.");
    const result=await api("/demo/api/context/proposal/apply",{...binding(),revision:workspace.draft.revision,proposal_id:proposal.proposal_id || proposal.id});
    await acceptWithGraph(result);
    $("confirmed").checked=false;
    await loadProposals();
    step("define");
    $("notice").textContent="Candidate applied to the draft. Inspect definitions, validate SQL, and record human review before finalizing.";
  },"Applying candidate to draft…"),"");
  apply.id="proposal-apply";box.append(apply);proposalControls();
}
async function loadProposals() {
  proposalState=await api("/demo/api/context/proposals");
  const box=$("proposal-history");box.replaceChildren();
  const items=proposalState.items || proposalState.candidates || [];
  if(items.length)box.append(node("h3","Candidate history"));
  for(const proposal of items)box.append(button(`${proposal.label || proposal.mode} · revision ${proposal.revision}`,()=>previewProposal(proposal)));
  proposalControls();
}
for(const mode of ["evidence","llm"])$("propose-"+mode).addEventListener("click",()=>work(async()=>{
  if(dirty)throw new Error("Save or reload unsaved changes before generation.");
  const result=await api("/demo/api/context/propose",{...binding(),revision:workspace.draft.revision,mode});
  await loadProposals();previewProposal(result.proposal || result);
  $("notice").textContent="Candidate generated. Inspect its evidence and assumptions before applying it to the draft.";
},mode==="llm" ? "Generating a candidate with the configured LLM…" : "Building a candidate from source evidence…"));
function renderArtifactVersions() {
  const select=$("artifact-version"),value=select.value;select.replaceChildren();
  const draft=node("option","Draft");draft.value="draft";select.append(draft);
  for(const version of workspace.versions || []) {const option=node("option",version.version);option.value=version.version;select.append(option);}
  if([...select.options].some(option=>option.value===value))select.value=value;
}
$("artifact-refresh").addEventListener("click",()=>work(async()=>{
  renderArtifactVersions();
  const data=await api(`/demo/api/context/artifacts?version=${encodeURIComponent($("artifact-version").value)}`);
  const box=$("artifact-content");box.replaceChildren();
  for(const [key,value] of Object.entries(data))inspectValue(key.replaceAll("_"," "),value,box);
  $("notice").textContent="Context artifacts loaded.";
},"Loading context artifacts…"));
function documentReviewLabel(value){return {approved:"Approved",changes_requested:"Changes requested",pending:"Pending review"}[value] || "Pending review";}
function currentDocuments(){return documentsState?.revision===workspace?.draft.revision ? documentsState.items : [];}
function documentObjectId(doc){return (doc.origin==="serving_document"?"source-document:":"document:")+doc.id;}
function documentGraph(){
  const docs=currentDocuments(),nodes=[...(sourceGraph?.nodes||[])],edges=[...(sourceGraph?.edges||[])];
  if(docs.length)nodes.push({id:"evidence:documents",type:"document_group",label:`Documents (${docs.length})`,description:"Open supporting evidence"});
  const tables=new Set();
  for(const doc of docs){
    const id=documentObjectId(doc);
    nodes.push({id,type:"document",label:doc.filename.split("/").pop(),description:documentReviewLabel(doc.review_status),semantic_links:doc.semantic_links||[]});
    for(const link of doc.semantic_links||[]){
      if(link.target.startsWith("table:"))tables.add(link.target.slice(6));
      if(link.target.startsWith("field:"))tables.add(link.target.slice(6).split(".")[0]);
    }
    doc.entity_links.forEach((link,index)=>{
      tables.add(link.table);
      edges.push({id:`evidence:${id}:${index}`,kind:"document_evidence",source:id,target:link.table,label:`${link.column} = ${link.value}`,document_id:id});
    });
  }
  for(const table of tables)edges.push({id:`evidence:group:${table}`,kind:"document_evidence",source:"evidence:documents",target:table,label:"Supporting documents",document_id:"evidence:documents"});
  return {nodes,edges};
}
function reviewDocument(id){
  const item=workspace.review?.items.find(item=>item.id===id);
  step("validate",true);$("review-filter").value=item?.name||"document";$("review-change").value="";reviewPage=0;renderReview();
  $("review-items").scrollIntoView({block:"nearest"});
}
async function openDocumentCanvas(id){
  if(!documentsState)await loadDocuments();
  step("define");canvasHandle?.focus(id);showDocumentInspector(id);
}
function appendSemanticDocumentLinks(box,doc){
  const links=doc.semantic_links||[];
  if(!links.length)return;
  box.append(node("h3","Reviewed semantic links"),node("p","Reviewer links identify relevant definitions. Document claims still require interpretation.","help"));
  for(const link of links){
    const item=node("section",undefined,"document-semantic-link");
    item.append(node("h4",link.target),node("p",`${link.location} · ${link.chunk_id}`),node("blockquote",link.quote),
      node("p",`Reviewer: ${link.reviewer}`),node("p",link.note||"No decision note recorded."));
    box.append(item);
  }
}
function appendMaterialTrace(box,doc){
  const material=doc.supporting_material;
  if(!material)return;
  const detail=node("details"),pairs=node("dl");detail.append(node("summary","Supporting material provenance"));
  for(const [label,value] of [["Library document",material.document_id],["Document revision",material.revision],
    ["Target source",material.source_id],["Original upload checksum",material.sha256],["Attachment checksum",doc.sha256]])
    pairs.append(node("dt",label),node("dd",String(value)));
  detail.append(pairs);box.append(detail);
}
function showDocumentGroup(){
  const box=$("source-inspector");box.replaceChildren(node("h2","Supporting documents"),node("p","Choose a document to inspect its semantic links, record links, and review status.","help"));
  delete box.dataset.documentId;
  for(const doc of currentDocuments())box.append(button(`${doc.filename.split("/").pop()} · ${documentReviewLabel(doc.review_status)}`,()=>openDocumentCanvas(documentObjectId(doc)),"secondary document-inspector-item"));
  inspector("source");
}
function showDocumentInspector(id){
  const doc=currentDocuments().find(doc=>documentObjectId(doc)===id),box=$("source-inspector");
  box.dataset.documentId=id;
  if(!doc){box.replaceChildren(node("p","This document is no longer in the saved draft. Reload to refresh its evidence."));inspector("source");return;}
  const item=workspace.review?.items.find(item=>item.id===id),state=item?reviewTechnicalState(item):null;
  box.replaceChildren(node("h2",doc.filename.split("/").pop()),node("p",documentReviewLabel(doc.review_status),"badge subtle"));
  if(state){box.append(node("p",state.label,state.style));for(const reason of state.reasons)box.append(node("p",reason,"help"));}
  box.append(node("h3","Links to source records"));
  for(const link of doc.entity_links)box.append(node("p",`${link.table}.${link.column} = ${link.value}`));
  box.append(node("p",doc.entity_links.length?"Keys match source records. Human review must confirm the document's claims.":(doc.semantic_links?.length?"Reviewed semantic links are listed below. No record link is declared.":"Model-wide context. No record link is declared."),"help"));
  appendSemanticDocumentLinks(box,doc);appendMaterialTrace(box,doc);
  box.append(node("pre",doc.content,"document-text"),button("Review this document",()=>reviewDocument(id)),button("Open source document",()=>{step("source");showDocument(doc);$("document-detail").scrollIntoView({block:"nearest"});},"secondary"));
  const trace=node("details");trace.append(node("summary","Source and traceability"),node("p",`Saved revision ${workspace.draft.revision}`),node("p",doc.citation),node("p",doc.sha256));box.append(trace);
  inspector("source");
}
function showDocument(doc){
  selectedDocumentId=doc.id;
  const box=$("document-detail");box.hidden=false;box.replaceChildren();
  box.append(node("h3",doc.filename.split("/").pop()),node("p",doc.origin==="serving_document"?"Included with this data source":"Added to the saved draft","help"),node("span",documentReviewLabel(doc.review_status),"badge subtle"));
  box.append(node("h4","Links to source data"));
  if(doc.entity_links.length){
    const links=node("ul");
    for(const link of doc.entity_links)links.append(node("li",`${link.table}.${link.column} = ${link.value}`));
    box.append(links,node("p","These keys match source records. Review the document's business claims separately.","help"));
  }else box.append(node("p",doc.semantic_links?.length?"Reviewed semantic links are listed below. No specific record is linked.":"Model-wide context · no specific record linked.","help"));
  appendSemanticDocumentLinks(box,doc);appendMaterialTrace(box,doc);
  box.append(node("h4","Document content"),node("pre",doc.content,"document-text"));
  const provenance=node("details");provenance.append(node("summary","Source and traceability"));
  const pairs=node("dl");for(const [label,value] of [["Citation",doc.citation],["Content hash",doc.sha256]])pairs.append(node("dt",label),node("dd",value));
  provenance.append(pairs);box.append(provenance);
  const actions=node("div",undefined,"actions");actions.append(button("Show in canvas",()=>openDocumentCanvas(documentObjectId(doc)),"secondary"),button("Review this document",()=>reviewDocument(documentObjectId(doc)),"secondary"));box.append(actions);
  const list=$("document-list");
  for(const item of list.querySelectorAll("button"))item.setAttribute("aria-pressed",String(item.dataset.documentId===doc.id));
  const selected=list.querySelector('[aria-pressed="true"]');
  if(selected){if(selected.offsetTop<list.scrollTop)list.scrollTop=selected.offsetTop;else if(selected.offsetTop+selected.offsetHeight>list.scrollTop+list.clientHeight)list.scrollTop=selected.offsetTop+selected.offsetHeight-list.clientHeight;}
}
function renderDocuments(preferredName){
  if(!documentsState)return;
  const docs=[...documentsState.items].sort((a,b)=>Number(b.origin==="operator_attachment")-Number(a.origin==="operator_attachment")),list=$("document-list");list.replaceChildren();
  const added=docs.filter(doc=>doc.origin==="operator_attachment").length;
  $("documents-status").textContent=`${docs.length} document${docs.length===1?"":"s"} · ${docs.length-added} from source · ${added} added to draft · ${docs.filter(doc=>doc.review_status!=="approved").length} awaiting review`;
  for(const doc of docs){
    const item=button("",()=>showDocument(doc),"document-list-item");item.dataset.documentId=doc.id;
    item.append(node("strong",doc.filename.split("/").pop()),node("span",doc.origin==="serving_document"?"Source document":"Uploaded document"),node("small",documentReviewLabel(doc.review_status)));
    list.append(item);
  }
  if(!docs.length){list.append(node("p","No documents yet. Add business definitions or notes to help explain this data."));$("document-detail").hidden=true;return;}
  showDocument(docs.find(doc=>doc.filename===preferredName)||docs.find(doc=>doc.id===selectedDocumentId)||docs[0]);
}
async function loadDocuments(preferredName){
  const requestId=++documentLoadId;
  try{
    const data=await api("/demo/api/context/documents");
    if(requestId!==documentLoadId)return;
    if(data.revision!==workspace.draft.revision){$("documents-status").textContent="The saved draft changed. Reload the workspace to see its documents.";return;}
    documentsState=data;$("documents-error").hidden=true;renderDocuments(preferredName);studioChanged();
  }catch(err){if(requestId===documentLoadId){$("documents-error").textContent="Could not load documents. Reload the workspace to retry.";$("documents-error").hidden=false;}}
}
function toggleDocumentUpload(open){
  $("document-upload-panel").hidden=!open;
  $("document-add").setAttribute("aria-expanded",String(open));
  if(open)$("document-file").focus();
}
function resetDocumentUpload(){
  filePreviewId++;$("document-form").reset();$("document-file").setCustomValidity("");
  $("document-file-preview").hidden=true;$("document-file-preview").textContent="";$("document-file-status").textContent="";
  $("document-link-options").open=false;toggleDocumentUpload(false);
}
async function readDocumentFile(file){
  if(!file)throw new Error("Choose a text or Markdown document.");
  if(!/\.(txt|md)$/i.test(file.name))throw new Error("Choose a .txt or .md file. PDF and Word are not supported yet.");
  if(!file.size || file.size>262144)throw new Error("Choose a nonempty document no larger than 256 KiB.");
  let content;
  try{content=new TextDecoder("utf-8",{fatal:true}).decode(await file.arrayBuffer());}catch{throw new Error("Save this document as UTF-8 text, then try again.");}
  if(content.includes("\0"))throw new Error("Choose a UTF-8 text document without binary content.");
  return content;
}
$("document-add").addEventListener("click",()=>toggleDocumentUpload($("document-upload-panel").hidden));
$("document-cancel").addEventListener("click",resetDocumentUpload);
$("documents-review").addEventListener("click",()=>{step("validate",true);$("review-filter").value="document";$("review-change").value="";reviewPage=0;renderReview();$("review-items").scrollIntoView({block:"nearest"});});
$("document-file").addEventListener("change",async()=>{
  const id=++filePreviewId;$("document-file").setCustomValidity("");$("document-file-preview").hidden=true;
  try{
    const file=$("document-file").files[0],content=await readDocumentFile(file);
    if(id!==filePreviewId)return;
    $("document-file-preview").textContent=content.slice(0,4000);$("document-file-preview").hidden=false;
    $("document-file-status").textContent=`${file.name} · ${file.size.toLocaleString()} bytes · ${content.length>4000?"Preview shows the first 4,000 characters":"Ready to add"}`;
  }catch(err){if(id===filePreviewId){$("document-file").setCustomValidity(err.message);$("document-file-status").textContent=err.message;}}
  proposalControls();
});
$("artifact-version").addEventListener("change",()=>$("artifact-content").replaceChildren());
$("document-form").addEventListener("submit",event=>{
  event.preventDefault();work(async()=>{
    if(dirty)throw new Error("Save or reload unsaved changes before adding a document.");
    const file=$("document-file").files[0],content=await readDocumentFile(file);
    const table=$("document-table").value.trim(),column=$("document-column").value.trim(),value=$("document-value").value.trim();
    if([table,column,value].some(Boolean) && ![table,column,value].every(Boolean))throw new Error("Provide table, key column, and record value together, or leave all three empty.");
    const result=await api("/demo/api/context/document",{...binding(),revision:workspace.draft.revision,filename:file.name,content,entity_links:table ? [{table,column,value}] : []});
    await acceptWithGraph(result.workspace || result);
    await loadDocuments(file.name);resetDocumentUpload();
    $("notice").textContent="Document added to the draft. Review its content and links before approving the version.";
  },"Adding document…");
});
inspector("metric");
window.addEventListener("hashchange",()=>step(stepFromHash()));
if(viewedVersion)prepareVersionView();
else step(stepFromHash());
work(load,viewedVersion?"Loading saved version…":"Loading workspace…");
