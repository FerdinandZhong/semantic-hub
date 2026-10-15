"use strict";
let config;
let lastResult=null, queryLLMReady=false;
let currentSource=new URL(location.href).searchParams.get("source");
const element = id => document.getElementById(id);
function definitions(target, pairs) {
  target.replaceChildren();
  for (const [label, value] of pairs) {
    const dt = document.createElement("dt"), dd = document.createElement("dd");
    dt.textContent = label; dd.textContent = value;
    target.append(dt, dd);
  }
}
async function request(url, options) {
  const scoped=new URL(url,location.origin);
  if(currentSource)scoped.searchParams.set("source",currentSource);
  const response = await fetch(scoped, {cache:"no-store", ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request was rejected.");
  return data;
}
function showError(error) {
  element("error").textContent = error.message;
  element("error").hidden = false;
}
function formatValue(value) {
  const text = String(value);
  if (!/^-?\d+(\.\d+)?$/.test(text)) return text;
  const [whole, fraction = ""] = text.split(".");
  const trimmed = fraction.replace(/0+$/, "");
  return whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + (trimmed ? `.${trimmed}` : "");
}
async function load() {
  try {
    config = await request("/demo/api/config");
    currentSource=config.connection_id;
    element("source-nav-title").textContent=config.connection_name;
    for(const link of document.querySelectorAll("[data-source-link]")){
      const url=new URL(link.href);url.searchParams.set("source",currentSource);link.href=url;
    }
    element("title").textContent = config.title;
    document.title = `${config.title} · Model playground`;
    for (const example of config.examples) {
      const option = document.createElement("option");
      option.value = example.id; option.textContent = example.question;
      element("example").append(option);
    }
    const reviewed = config.review_state === "LOCAL_SAMPLE_REVIEWED";
    element("data-origin-note").textContent = config.data_origin === "document_evidence"
      ? "These records contain reviewed document assertions. Check source pages, units, scope, and retained uncertainty."
      : config.synthetic === false
      ? "These records contain curated published facts. Check source dates and coverage before interpreting results."
      : "Review covers local sample examples only. These fictional records do not establish operational or regulatory findings.";
    element("query-status").textContent = reviewed ? "Ready to query" : "Review required before querying";
    element("query-context").textContent = config.context_version ? `Active context · ${config.context_version}` : "Original sample context · no Studio version activated";
    element("review-note").textContent = reviewed
      ? (config.context_version ? `Queries use reviewed context ${config.context_version}. Select a metric below.` : "This snapshot has an explicit local sample review. Run a predefined example below.")
      : "This snapshot is awaiting review. Complete the operator review before running sample queries.";
    element("example").disabled = !reviewed;
    element("run").disabled = !reviewed;
    definitions(element("metadata"), [["Dataset",config.pack_id],["Context version",config.context_version || "Original sample"],["Context hash",config.context_sha256 || "Not applicable"],["Source reference",config.source],
      ["Data origin",config.generation_mode],["Reporting timezone",config.timezone],
      ["Review state",config.review_state],["Semantic hash",config.model_sha256],["Snapshot",config.snapshot_sha256]]);
    try {
      const settings=await request('/demo/api/llm');
      const profile=settings.profiles.query;
      queryLLMReady=profile.ready;
      element('explanation-status').textContent=queryLLMReady?`Optional explanation using ${profile.model}. The model receives a bounded sample of this executed result.`:'Configure the data query LLM to explain this result.';
      element('explain-result').disabled=!queryLLMReady || !lastResult;
    } catch (_) { element('explanation-status').textContent='Could not load LLM settings. Open Model configuration to check.'; }
    document.dispatchEvent(new CustomEvent("demo:ready"));
  } catch (error) { showError(error); document.dispatchEvent(new CustomEvent("demo:failed")); }
}
element("query-form").addEventListener("submit", async event => {
  event.preventDefault();
  element("run").disabled = true;
  element("run").textContent = "Running…";
  element("error").hidden = true;
  element("result").hidden = true;
  lastResult=null;
  element('explanation-panel').hidden=true;
  element('explanation-error').hidden=true;
  element('explain-result').disabled=true;
  try {
    const data = await request("/demo/api/example", {method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({pack_id:config.pack_id,snapshot_sha256:config.snapshot_sha256,
        session_id:config.session_id,context_sha256:config.context_sha256,example_id:element("example").value})});
    const grouped = data.columns.length > 1 || data.rows.length > 1;
    element("value").parentElement.hidden = grouped;
    element("result-table").hidden = !grouped;
    element("result-table").replaceChildren();
    if (grouped) {
      const table = document.createElement("table"), head = document.createElement("thead"), header = document.createElement("tr"), body = document.createElement("tbody");
      for (const column of data.columns) { const th = document.createElement("th"); th.textContent = column; header.append(th); }
      head.append(header);
      for (const row of data.rows) { const tr = document.createElement("tr"); for (const value of row) { const td = document.createElement("td"); td.textContent = value === null ? "NULL" : formatValue(value); tr.append(td); } body.append(tr); }
      table.append(head, body); element("result-table").append(table);
    }
    element("value").textContent = formatValue(data.rows[0]?.[0] ?? "No value");
    element("unit").textContent = data.unit;
    element("result-question").textContent = data.question;
    element("sql").textContent = data.sql;
    definitions(element("evidence"), [["Planner",data.planner],["Dataset",data.pack_id],["Context version",data.context_version || "Original sample"],["Context hash",data.context_sha256 || "Not applicable"],
      ["Snapshot",data.snapshot_sha256],["SQL hash",data.sql_sha256],["Result hash",data.result_sha256]]);
    element("result").hidden = false;
    lastResult=data;
    element('explain-result').disabled=!queryLLMReady;
  } catch (error) { showError(error); }
  finally { element("run").disabled = false; element("run").textContent = "Run example"; }
});
element('explain-result').addEventListener('click',async()=>{
  const result=lastResult;
  if(!result)return;
  element('explain-result').disabled=true;
  element('explain-result').textContent='Explaining…';
  element('explanation-error').hidden=true;
  try {
    const response=await request('/demo/api/example/explain',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      pack_id:config.pack_id,snapshot_sha256:config.snapshot_sha256,session_id:config.session_id,
      context_sha256:result.context_sha256,example_id:result.example_id,result_sha256:result.result_sha256
    })});
    if(lastResult!==result)return;
    element('explanation-text').textContent=response.explanation;
    element('explanation-model').textContent=`${response.provider} · ${response.model} · ${response.shown_rows} of ${response.total_rows} result rows. Generated explanation; SQL evidence remains authoritative.`;
    element('explanation-panel').hidden=false;
  }catch(error){if(lastResult===result){element('explanation-error').textContent=error.message;element('explanation-error').hidden=false;}}
  finally{element('explain-result').textContent='Explain result with LLM';element('explain-result').disabled=!lastResult || !queryLLMReady;}
});
load();
