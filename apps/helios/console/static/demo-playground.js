/* Published model playground. Definitions and execution remain bound to one release. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  let versions=[],selected=null,plan=null,canvas=null,generation=0,busy=false;
  const node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
  const post=(url,data)=>request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const binding=()=>({pack_id:config.pack_id,snapshot_sha256:config.snapshot_sha256,session_id:config.session_id});
  function controls(){
    $('playground-ask').disabled=busy||!selected;$('playground-new-chat').disabled=busy;$('playground-mode').disabled=busy||!selected;
    $('playground-run').disabled=busy||!plan;
    for(const button of document.querySelectorAll('#playground-examples button,#playground-choices button'))button.disabled=busy;
  }
  function reset(){
    generation++;plan=null;busy=false;canvas?.destroy();canvas=null;
    for(const id of ['playground-interpretation','playground-answer','playground-graph-panel','playground-clarification','playground-error','playground-agent-panel'])$(id).hidden=true;
    $('playground-status').textContent='';controls();
  }
  // Chat transcript: each new question archives the previous turn as read-only history.
  function archiveTurn(){
    const turn=$('playground-turn');if(turn.hidden)return;
    const copy=turn.cloneNode(true);
    for(const el of [copy,...copy.querySelectorAll('[id]')])if(el.id.startsWith('playground-'))el.removeAttribute('id');
    // Saved turns never restore runnable plans; ask again for a fresh interpretation.
    for(const control of copy.querySelectorAll('button,select,input,textarea'))control.disabled=true;
    copy.classList.add('chat-archived');$('playground-transcript').append(copy);
  }
  function clearChat(){$('playground-transcript').replaceChildren();$('playground-turn').hidden=true;$('playground-suggestions').hidden=false;}
  function metricButton(metric){
    const button=node('button',metric.name.replaceAll('_',' '));button.type='button';button.className='secondary';
    button.title=metric.description;button.onclick=()=>{
      $('playground-question').value=metric.description;interpret(metric.name);
    };return button;
  }
  function selectVersion(){
    reset();clearChat();selected=versions.find(v=>v.version===$('playground-version').value)||null;
    $('playground-ready').hidden=!selected;$('playground-empty').hidden=Boolean(selected);
    $('playground-view').hidden=!selected;
    if(!selected){$('playground-binding').textContent='No published version selected.';controls();return;}
    const url=new URL('/demo/context',location.origin);url.searchParams.set('source',currentSource);url.searchParams.set('version',selected.version);url.hash='hub';$('playground-view').href=url;
    $('playground-heading').textContent=selected.title;
    $('playground-binding').textContent=`${selected.version} · Published · Reviewed by ${selected.reviewer} · ${selected.evidence_passages||0} published document passages. This selection does not change the active version.`;
    $('playground-question').value='';
    $('playground-examples').replaceChildren(...selected.metrics.map(metricButton));
    const current=new URL(location.href);current.searchParams.set('version',selected.version);history.replaceState(null,'',current);
    controls();
  }
  function agentChecks(data){
    const agent=data.agent,scope=data.scope_check;
    $('playground-agent-panel').hidden=!(agent||scope);
    if(!agent&&!scope)return;
    $('playground-agent-engine').textContent=agent?`AI query assistant · ${agent.model}`:'Server scope check';
    $('playground-agent-summary').textContent=agent?'The agent inspects this published version through bounded tools. Previous answers are not reused as facts.':'The server checks the original question against source rows before preparing SQL.';
    const labels={inspect_model:'Read published definitions',inspect_coverage:'Check actual data coverage',read_document_evidence:'Read published document evidence',prepare_query:'Validate scope and compile query',prepare_document:'Prepare citation-checked answer',request_clarification:'Identify unsupported or ambiguous scope'};
    $('playground-agent-steps').replaceChildren(...(agent?.trace||[]).map(step=>{
      const li=node('li');li.append(node('strong',labels[step.tool]||step.tool),node('span',` · ${step.status.replaceAll('_',' ')}`));
      if(step.metric)li.append(node('p',step.metric));if(step.message)li.append(node('p',step.message));return li;
    }));
    $('playground-scope-details').hidden=!scope;
    $('playground-scope-evidence').textContent=scope?JSON.stringify({question:scope.requirements.original_question,checks:scope.checks,requested_ranges:scope.requirements.year_ranges,coverage:scope.coverage},null,2):'';
  }
  async function interpret(metric=null){
    if(!selected||busy)return;
    const originalQuestion=$('playground-question').value.trim();
    archiveTurn();reset();const ticket=generation;const release=selected;busy=true;controls();
    $('playground-turn-question').textContent=originalQuestion||metric;$('playground-turn').hidden=false;$('playground-suggestions').hidden=true;
    $('playground-question').value='';$('playground-thread').scrollTop=$('playground-thread').scrollHeight;
    $('playground-status').textContent=metric?'Preparing the saved metric…':'AI is inspecting definitions, data coverage, and published evidence…';
    try{
      const data=await post('/demo/api/playground/interpret',{...binding(),version:release.version,context_sha256:release.context_sha256,question:originalQuestion,metric,mode:metric?'metric':$('playground-mode').value});
      if(ticket!==generation)return;
      $('playground-status').textContent='';
      agentChecks(data);
      if(data.status!=='ready'){
        $('playground-outcome-heading').textContent=data.status==='no_data'?'No matching data':data.status==='unsupported_scope'?'Requested scope is not supported':data.status==='unavailable'?'Agent unavailable':'Clarify the question';
        $('playground-clarification').hidden=false;$('playground-clarification-text').textContent=data.message;
        $('playground-choices').replaceChildren(...(data.choices||[]).map(metricButton));return;
      }
      plan={...data,originalQuestion};$('playground-interpretation').hidden=false;
      $('playground-meaning').textContent=data.interpretation;
      const isDocument=data.kind==='document',isHybrid=data.kind==='hybrid';
      $('playground-sql-panel').hidden=isDocument;$('playground-plan-passages').hidden=!(isDocument||isHybrid);
      $('playground-run').textContent=isDocument?'Answer from these documents':isHybrid?'Run AI query and answer':'Run this interpretation';
      $('playground-run-help').textContent=isDocument?'Reads this version’s published evidence. It does not execute SQL or change the model.':isHybrid?'AI runs the proposed SQL, reads the published passages, and checks a cited answer.':'Runs against the selected local sample. Your published model stays unchanged.';
      if(isDocument||isHybrid){
        const container=$('playground-plan-passages');container.replaceChildren();
        const fold=node('details');fold.append(node('summary','Inspect retrieved passages'));
        for(const p of data.passages){const item=node('details');item.append(node('summary',`${p.title} · ${p.location}`),node('p',p.text));fold.append(item);}container.append(fold);
      }
      if(isDocument){
        definitions($('playground-definition'),[['Answer type','Document evidence'],['Version',data.version],['Evidence scope',`${data.passages.length} linked passages from this published version`],['Query model',`${data.provenance.provider} · ${data.provenance.model}`]]);
        $('playground-rules').textContent=data.notice;
        return;
      }
      const m=data.metric,q=data.request;
      definitions($('playground-definition'),[['AI tools',isHybrid?'Execute SQL + read documents + verify cited answer':'Execute SQL'],['Version',data.version],['Metric',m.name],['Definition',m.description],['Expression',m.expression],['Unit',m.unit],['Grain',m.grain],['Time rule',m.time_rule],['Group by',q.dimensions.join(', ')||'No grouping'],['Additional filters',q.filters.length?JSON.stringify(q.filters):'None'],['Interpretation',data.provenance.method==='saved_metric'?'Saved metric definition':`${data.provenance.provider} · ${data.provenance.model} · proposed interpretation`]]);
      $('playground-rules').textContent=`Fixed metric scope: ${m.description||m.name}. ${m.filters?.length?`Fixed filters: ${JSON.stringify(m.filters)}.`:'The expression defines any fixed period and population.'} Additional question filters do not replace this scope. Review the definition before running.`;
      $('playground-sql').textContent=data.sql;
      $('playground-graph-panel').hidden=false;
      canvas=window.HeliosCanvas.mount($('playground-canvas'),{readOnly:true,host:{getState:()=>({definition:data.graph_definition})},onSelect:object=>{$('playground-object').textContent=JSON.stringify(object,null,2);}});
      canvas.update({...data.graph,saved_revision:data.graph.draft_revision,scope:data.context_sha256,dirty:false});
      $('playground-documents').replaceChildren();
      if(!data.documents.length)$('playground-documents').append(node('p','No supporting documents recorded for this scope.'));
      for(const doc of data.documents)$('playground-documents').append(node('p',`${doc.filename} · ${doc.citation||doc.id}`));
      $('playground-retrieval').textContent=JSON.stringify({manifest:data.manifest,retrieval:data.retrieval},null,2);
    }catch(error){if(ticket===generation){$('playground-error').textContent=error.message;$('playground-error').hidden=false;$('playground-status').textContent='';}}
    finally{if(ticket===generation){busy=false;controls();}}
  }
  async function run(){
    if(!plan||busy)return;
    const ticket=generation,saved=plan;busy=true;controls();$('playground-error').hidden=true;$('playground-answer').hidden=true;
    $('playground-status').textContent=saved.kind==='document'?'AI is reading published evidence and checking citations…':saved.kind==='hybrid'?'AI is querying data, reading documents, and checking the answer…':'Executing the interpreted query…';
    try{
      const result=await post('/demo/api/playground/run',{...binding(),plan_id:saved.plan_id});
      if(ticket!==generation)return;
      const isDocument=result.kind==='document',isHybrid=result.kind==='hybrid',isAIAnswer=isDocument||isHybrid;
      $('playground-answer-context').hidden=true;
      $('playground-answer-kind').textContent=isHybrid?'AI answer · SQL + documents':isDocument?'AI answer · documents':'Metric query';
      $('playground-cited-claims').hidden=!isAIAnswer;
      $('playground-executed-sql').hidden=isDocument;
      if(isAIAnswer){
        $('playground-executed-sql').textContent=isHybrid?result.sql:'';
        $('playground-answer-text').textContent=result.status==='answered'?'AI answer with source evidence':result.message;
        $('playground-limit').textContent=`${result.context_version} · ${result.notice}`;
        $('playground-results').replaceChildren();$('playground-results').hidden=true;
        const claims=$('playground-cited-claims');claims.replaceChildren();
        for(const claim of result.claims||[]){
          const section=node('article');section.className='playground-document-claim';section.append(node('p',claim.text));
          for(const c of claim.citations){
            const citation=node('details');citation.append(node('summary',c.source_kind==='sql'?c.title:`${c.title} · ${c.location} · Document revision ${c.document_revision}`),node('blockquote',c.quote));
            if(c.source_kind==='sql')citation.append(node('pre',c.sql));
            else citation.append(node('p',`Linked targets: ${c.links.map(l=>l.target).join(', ')}`));
            if(c.preview_url){const link=node('a','Open original page');link.href=c.preview_url;link.target='_blank';link.rel='noopener';citation.append(link);}
            const evidence=node('pre',`Citation: ${c.citation}\nOriginal SHA-256: ${c.original_sha256}\nAttachment SHA-256: ${c.attachment_sha256}`);citation.append(evidence);section.append(citation);
          }claims.append(section);
        }
        definitions($('playground-evidence'),[['Version',result.context_version],['Context hash',result.context_sha256],['Snapshot',result.snapshot_sha256],['Artifact hash',result.artifact_sha256],['Answer hash',result.result_sha256],['Answer model',`${result.planner.provider} · ${result.planner.model}`]]);
        $('playground-answer').hidden=false;$('playground-status').textContent=result.status==='answered'?'AI answer completed. Inspect each claim and its source.':result.message;
        $('playground-answer').scrollIntoView({block:'nearest'});return;
      }
      const rows=Array.isArray(result.rows)?result.rows:[],columns=Array.isArray(result.columns)?result.columns:[];
      const scalar=columns.length===1&&rows.length===1;
      const noData=result.status==='no_data'||!rows.length||rows.every(row=>!row.length||row.every(value=>value===null||value===undefined));
      $('playground-answer-text').textContent=noData?'No matching value':scalar?[formatValue(rows[0][0]),result.unit].filter(Boolean).join(' '):`${rows.length} result rows`;
      $('playground-answer-context').hidden=false;
      $('playground-answer-context').textContent=noData?`${result.message||'The query returned no usable value for this scope.'} Review the question and fixed metric scope below. Missing values do not represent zero.`:`Question: ${saved.originalQuestion}. Fixed metric scope: ${saved.metric.description||saved.metric.name}.`;
      $('playground-limit').textContent=result.truncated?`Showing the first ${result.display_limit} rows. The result is truncated.`:`${saved.metric.name} · ${result.context_version} · Local sample result`;
      const table=node('table'),head=node('thead'),tr=node('tr'),body=node('tbody');
      for(const col of columns)tr.append(node('th',col));head.append(tr);
      for(const row of rows){const tr=node('tr');for(const value of row)tr.append(node('td',value===null||value===undefined?'No value':formatValue(value)));body.append(tr);}
      table.append(head,body);$('playground-results').replaceChildren(table);$('playground-results').hidden=scalar||noData;
      $('playground-executed-sql').textContent=result.sql;
      definitions($('playground-evidence'),[['Original question',saved.originalQuestion],['Metric',saved.metric.name],['Fixed metric scope',saved.metric.description],['Expression',saved.metric.expression],['Fixed filters',JSON.stringify(saved.metric.filters||[])],['Additional filters',JSON.stringify(saved.request?.filters||[])],['Returned rows',rows.length],['Version',result.context_version],['Context hash',result.context_sha256],['Snapshot',result.snapshot_sha256],['SQL hash',result.sql_sha256],['Result hash',result.result_sha256]]);
      $('playground-answer').hidden=false;$('playground-status').textContent=noData?'Query completed. No matching value is available.':'Query completed using the selected published version.';
      $('playground-answer').scrollIntoView({block:'nearest'});
    }catch(error){if(ticket===generation){$('playground-error').textContent=error.message;$('playground-error').hidden=false;$('playground-status').textContent='';}}
    finally{if(ticket===generation){busy=false;controls();}}
  }
  $('playground-form').onsubmit=event=>{event.preventDefault();interpret();};
  $('playground-version').onchange=selectVersion;
  // Editing the next message invalidates the displayed plan without hiding the answer.
  $('playground-question').oninput=()=>{plan=null;controls();};
  $('playground-mode').onchange=()=>{plan=null;controls();};
  $('playground-question').onkeydown=event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();if(!busy&&$('playground-question').value.trim())$('playground-form').requestSubmit();}};
  $('playground-new-chat').onclick=()=>{if(busy)return;reset();clearChat();$('playground-question').focus();};
  $('playground-run').onclick=run;
  document.addEventListener('demo:ready',async()=>{
    try{
      const data=await request('/demo/api/playground');versions=data.versions;
      $('playground-version').replaceChildren(...versions.map(v=>{const option=node('option',v.version);option.value=v.version;return option;}));
      $('playground-version').disabled=!versions.length;
      const requested=new URL(location.href).searchParams.get('version');
      if(requested&&!versions.some(v=>v.version===requested)){
        $('playground-version').append(new Option('Choose a published version',''));$('playground-version').value='';
      }else $('playground-version').value=requested||(versions.some(v=>v.version===data.active_version)?data.active_version:versions[0]?.version)||'';
      $('legacy-query').open=!versions.length;
      $('playground-llm-status').textContent=queryLLMReady?'AI can query data, read published documents, or use both. It must preserve your question’s period and population.':'Configure the query model for questions and document answers, or select a saved metric below.';
      selectVersion();
      if(requested&&!selected){$('playground-error').textContent='The requested version is not published or is unavailable. Select a published version.';$('playground-error').hidden=false;}
    }catch(error){$('playground-error').textContent=error.message;$('playground-error').hidden=false;}
  });
})();
