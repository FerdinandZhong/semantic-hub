/* Structured evidence stays in the existing conversation/result panel. */
function timeControls(){const kind=$('obs-time-mode').value;$('obs-range-fields').hidden=kind!=='range';$('obs-exact-fields').hidden=kind!=='exact';$('obs-timezone-wrap').hidden=kind==='relative';if(state.tab==='observability')$('minutes').disabled=kind!=='relative';}
$('obs-time-mode').onchange=()=>{if($('obs-time-mode').value==='exact')$('obs-path').value='exact';else if($('obs-path').value==='exact')$('obs-path').value='auto';timeControls();};
$('obs-path').onchange=()=>{if($('obs-path').value==='exact')$('obs-time-mode').value='exact';else if($('obs-time-mode').value==='exact')$('obs-time-mode').value='relative';timeControls();};
function svgNode(tag,attrs={},text){const element=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [key,value] of Object.entries(attrs))element.setAttribute(key,value);if(text!==undefined)element.textContent=text;return element;}
const evidenceColors=['#3769dd','#7196ea','#a5bdef','#c4d3f5','#547ebc','#8aa8bc','#5e9e91','#a8c4bc','#b5986b','#d3bf9a','#bcb4d7','#d7d3e5'];
function evidenceChart(spec){
 const points=spec.points||[];if(!points.length)return;
 const box=node('section',undefined,'evidence-chart');box.append(node('h3',spec.title),node('p',spec.y_label+' · '+spec.unit,'helper'));
 const svg=svgNode('svg',{viewBox:'0 0 620 235',role:'img','aria-label':spec.title});
 const values=points.map(point=>Number(point.y));if(values.some(value=>!Number.isFinite(value)))return;
 const maximum=Math.max(...values,1),minimum=spec.type==='line'?Math.min(0,...values):0;
 const format=value=>Number.isInteger(value)?String(value):value.toFixed(2);
 if(spec.type==='pie'){
  const total=values.reduce((a,b)=>a+b,0);if(total<=0){box.append(node('p','No non-zero categories to display.'));return box;}
  let angle=-Math.PI/2;
  points.forEach((point,index)=>{const next=angle+2*Math.PI*point.y/total;const sx=150+80*Math.cos(angle),sy=110+80*Math.sin(angle),ex=150+80*Math.cos(next),ey=110+80*Math.sin(next);const color=evidenceColors[index%evidenceColors.length];let shape;
   if(point.y===total)shape=svgNode('circle',{cx:150,cy:110,r:80,fill:color});
   else shape=svgNode('path',{d:`M150,110 L${sx},${sy} A80,80 0 ${next-angle>Math.PI?1:0} 1 ${ex},${ey} Z`,fill:color,class:'pie-slice'});
   shape.append(svgNode('title',{},`${point.x}: ${point.y} (${(point.y/total*100).toFixed(1)}%)`));svg.append(shape);angle=next;
  });
 }else if(spec.type==='bar'){
  const height=Math.max(235,points.length*30+30);svg.setAttribute('viewBox',`0 0 620 ${height}`);
  points.forEach((point,index)=>{const y=15+index*30;svg.append(svgNode('text',{x:8,y:y+13,class:'axis-text'},String(point.x).slice(0,23)),svgNode('rect',{x:190,y,width:point.y/maximum*340,height:16,rx:3,fill:evidenceColors[0]}),svgNode('text',{x:540,y:y+13,class:'axis-text'},format(point.y)));});
 }else{
  const xs=points.map(point=>Date.parse(point.x)),first=Math.min(...xs),span=Math.max(...xs)-first||1;
  if(xs.some(value=>!Number.isFinite(value)))return;
  for(let i=0;i<5;i++){const y=190-i*38,value=minimum+(maximum-minimum)*i/4;svg.append(svgNode('line',{x1:52,x2:592,y1:y,y2:y,stroke:'#e9edf5'}),svgNode('text',{x:43,y:y+3,'text-anchor':'end',class:'axis-text'},format(value)));}
  const coordinates=points.map((point,index)=>[52+(xs[index]-first)/span*540,190-(point.y-minimum)/(maximum-minimum||1)*152]);
  svg.append(svgNode('polyline',{points:coordinates.map(pair=>pair.join(',')).join(' '),fill:'none',stroke:evidenceColors[0],'stroke-width':2.5}));
  for(const index of [...new Set([0,Math.floor(points.length/2),points.length-1])]){const x=coordinates[index][0],label=new Date(xs[index]).toISOString().slice(11,19);svg.append(svgNode('text',{x,y:215,'text-anchor':'middle',class:'axis-text'},label));}
  points.forEach((point,index)=>{const marker=svgNode('circle',{cx:coordinates[index][0],cy:coordinates[index][1],r:3,fill:'white',stroke:evidenceColors[0]});marker.append(svgNode('title',{},`${point.x}: ${format(point.y)} ${spec.unit}`));svg.append(marker);});
 }
 box.append(svg,node('p',spec.x_label+' · evidence '+spec.citation,'helper'));
 if(spec.type!=='line'){
  const legend=node('div',undefined,'chart-evidence-legend');points.forEach((point,index)=>{const item=node('div');item.append(node('strong',point.x),node('span',format(point.y)+(spec.type==='pie'?' · '+(point.y/values.reduce((a,b)=>a+b,0)*100).toFixed(1)+'%':'')));legend.append(item);});box.append(legend);
 }
 return box;
}
function renderObservabilityDefinitions(context){
 const box=node('details',undefined,'observability-definitions');box.open=true;
 box.append(node('summary','Metric definitions and log fields · '+context.version),node('p',context.scope,'helper'));
 const definitions=[...(context.metrics||[]),...(context.items||[]),...(context.log_fields||[])];
 if(!definitions.length)box.append(node('p','No matching reviewed definitions. Native tool validation still applies.','helper'));
 for(const item of definitions.slice(0,14)){
  const card=node('section',undefined,'definition-card');card.append(node('h3',item.technical_name||item.id),node('p',item.description));
  if(item.unit||item.metric_type)card.append(node('p','Unit: '+(item.unit||'Not supplied')+' · Type: '+(item.metric_type||'Not supplied'),'helper'));
  if(item.labels)card.append(node('p','Labels: '+(item.labels.length?item.labels.join(', '):'Not supplied'),'helper'));
  if(item.aggregation)card.append(node('p',item.aggregation));
  if(item.limits?.length){const list=node('ul');for(const limit of item.limits)list.append(node('li',limit));card.append(list);}
  card.append(node('small',item.origin||'reviewed release'));box.append(card);
 }
 if(definitions.length>14)box.append(node('p',`${definitions.length-14} additional definitions remain in the response; this panel displays the first 14.`,'helper'));
 $('result').append(box);
}
function renderEvidence(data,answer){
 if(data.status==='needs_clarification'){answer.append(node('p',state.tab==='data'?'No query was executed. Specify an approved metric, field or business meaning.':'No source was queried. Use the time controls or specify the timestamp and timezone.','scope'));return;}
 if(data.findings?.length>1){const list=node('ul',undefined,'evidence-findings');for(const finding of data.findings.slice(1)){const item=node('li',finding.text);item.append(node('small',' ['+finding.citation+']'));list.append(item);}answer.append(list);}
 if(data.window)answer.append(node('p',`${data.window.start} ≤ time < ${data.window.end} · ${data.window.timezone} · ${data.window.precision}`,'scope'));
 if(data.operational_context)renderObservabilityDefinitions(data.operational_context);
 if(data.semantic_retrieval){const context=data.semantic_retrieval;const box=node('details',undefined,'semantic-retrieval');box.open=true;box.append(node('summary','Retrieved semantic definitions'),node('p',`${context.method} · ${context.dataset_count} datasets · ${context.field_count} fields · ${context.context_chars} context characters`,'helper'),node('p',`Release ${context.release_sha256} · Policy ${context.policy_revision}`,'helper'));const list=node('ul');for(const match of context.matches||[])list.append(node('li',`${match.kind}: ${match.name} · lexical score ${match.score}`));box.append(list);$('result').append(box);}
 if(data.charts?.length){const grid=node('div',undefined,'evidence-charts');for(const spec of data.charts){const box=evidenceChart(spec);if(box)grid.append(box);}$('result').append(grid);}
 if(data.limitations?.length){const box=node('details');box.open=true;box.append(node('summary','Coverage and limitations'));const list=node('ul');for(const text of data.limitations)list.append(node('li',text));box.append(list);$('result').append(box);}
 if(data.citations?.length){const box=node('details');box.append(node('summary','Source evidence references'),node('pre',JSON.stringify(data.citations,null,2)));$('result').append(box);}
}

timeControls();
