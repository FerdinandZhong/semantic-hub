/* Native semantic canvas. Layout state never mutates the semantic draft. */
(() => {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  function el(tag, text, cls) {
    const e=document.createElement(tag);
    if(text!==undefined)e.textContent=text;
    if(cls)e.className=cls;
    return e;
  }   function svg(tag, attrs= {
  }) {
    const e=document.createElementNS(NS,tag);
    Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,String(v)));
    return e;
  }   function mount(root, options= {
  }) {
    const readOnly=Boolean(options.readOnly);
    root.classList.add('semantic-canvas');
    let graph= {
      nodes:[],edges:[]
    }, selected='', mode='Lineage', lens='semantic', expanded=new Set(), positions= {
    }, transform= {
      x:25,y:35,k:0.8
    }, scope='', connection=null, changeIndex=0, neighborhood=null, focusKind='all';
    const bar=el('div',undefined,'canvas-toolbar'), stage=el('div',undefined,'canvas-stage'), surface=svg('svg', {
      'aria-label':'Semantic graph',role:'img',tabindex:0
    }), world=svg('g'), mini=svg('svg', {
      viewBox:'0 0 1000 650','aria-label':'Graph minimap'
    }), status=el('div','Loading source graph…','canvas-status');
    const modes=el('div',undefined,'canvas-modes');
    const button=(label,fn)=> {
      const b=el('button',label);
      b.type='button';
      b.addEventListener('click',fn);
      return b;
    };
    const modeButtons= {
    };
    (readOnly?['Lineage']:['Lineage','Edit','Changes']).forEach(m=> {
      modeButtons[m]=button(m,()=>setMode(m));
      modes.append(modeButtons[m]);
    });
    const optionsPanel=el('div',undefined,'canvas-view-options');
    optionsPanel.id=(root.id||'semantic-canvas')+'-view-options';
    optionsPanel.hidden=true;
    const optionsToggle=button('View options',()=>{
      optionsPanel.hidden=!optionsPanel.hidden;
      optionsToggle.setAttribute('aria-expanded',String(!optionsPanel.hidden));
    });
    optionsToggle.setAttribute('aria-expanded','false');
    optionsToggle.setAttribute('aria-controls',optionsPanel.id);
    bar.append(modes);
    const view=el('select');
    view.setAttribute('aria-label','Graph view');
    [['semantic','Semantic'],['metadata','Metadata']].forEach(([v,t])=> {
      const o=el('option',t);
      o.value=v;
      view.append(o);
    });
    view.onchange=()=> {
      lens=view.value;
      neighborhood=null;focusKind='all';expanded.clear();
      render();
      fit();
    };
    const viewLabel=el('label','Graph view');
    viewLabel.append(view);
    optionsPanel.append(viewLabel);
    const search=el('input');
    search.type='search';
    search.placeholder='Find data, metric or document';
    search.setAttribute('aria-label','Find graph object');
    const results=el('select');
    results.setAttribute('aria-label','Search results');
    results.hidden=true;
    search.oninput=()=> {
      results.replaceChildren();
      const matches=graph.nodes.filter(n=>label(n).toLowerCase().includes(search.value.toLowerCase()));
      matches.forEach(n=> {
        const o=el('option',label(n));
        o.value=n.id;
        results.append(o);
      });
      results.hidden=!search.value;
      if(matches.length)focus(matches[0].id);
    };
    results.onchange=()=>focus(results.value);
    bar.append(search,results);
    const zoomControls=el('div',undefined,'canvas-zoom');
    const zoomOut=button('−',()=>zoom(.8)),zoomIn=button('+',()=>zoom(1.25));
    zoomOut.setAttribute('aria-label','Zoom out');zoomIn.setAttribute('aria-label','Zoom in');
    zoomControls.append(zoomOut,zoomIn);
    if(!readOnly)bar.append(button('Connect fields',()=>openRelationship()));
    bar.append(button('Fit',fit),optionsToggle);
    const displayActions=el('div',undefined,'canvas-display-actions');
    function selectedObject() {
      const node=graph.nodes.find(n=>n.id===selected);
      return isColumn(node||{})?graph.nodes.find(n=>n.id===parentId(node)):node;
    }
    const neighborsButton=button('Neighbors',()=> {
      const anchor=selectedObject();
      if(!anchor)return;
      selected=anchor.id;
      neighborhood=new Set([anchor.id]);
      // Match dataset relationships and field-level dependencies in the full graph.
      // Column containment is not a relationship to another dataset.
      const owner=id=>{
        const node=graph.nodes.find(n=>n.id===id);
        return node&&isColumn(node)?parentId(node):id;
      };
      graph.edges.filter(e=>(e.kind||e.type)!=='contains').forEach(e=>{
        const source=owner(e.source),target=owner(e.target);
        if(source===anchor.id)neighborhood.add(target);
        if(target===anchor.id)neighborhood.add(source);
      });
      lens='semantic';view.value=lens;expanded.clear();focusKind='neighbors';
      render();fit();
    });
    const allButton=button('Show all',()=> {
      neighborhood=null;expanded.clear();lens='semantic';view.value=lens;focusKind='all';
      const anchor=selectedObject();if(anchor)selected=kind(anchor)==='document'?'evidence:documents':anchor.id;
      render();fit();
    });
    const columnsButton=button('Columns',()=> {
      const anchor=selectedObject();
      if(!anchor||kind(anchor)!=='dataset')return;
      selected=anchor.id;
      neighborhood=new Set([anchor.id]);
      expanded.clear();lens='metadata';view.value=lens;focusKind='columns';
      render();fit();
    });
    columnsButton.title='Inspect columns in the selected dataset';
    neighborsButton.title='Show relationships around the selected dataset or metric';
    const fullscreenButton=button('Fullscreen',async()=> {
      try {
        if(document.fullscreenElement===root)await document.exitFullscreen();
        else if(root.requestFullscreen)await root.requestFullscreen();
      }catch {status.textContent='Fullscreen is unavailable in this browser.';}
    });
    function fullscreenChanged() {
      const active=document.fullscreenElement===root;
      fullscreenButton.textContent=active?'Exit fullscreen':'Fullscreen';
      fullscreenButton.setAttribute('aria-pressed',String(active));
      requestAnimationFrame(fit);
    }
    document.addEventListener('fullscreenchange',fullscreenChanged);
    fullscreenButton.setAttribute('aria-pressed','false');
    displayActions.append(neighborsButton,allButton,columnsButton,fullscreenButton);
    optionsPanel.append(displayActions);
    const changes=el('div',undefined,'canvas-change-navigation');
    changes.hidden=true;
    const changeLabel=el('span');
    changes.append(button('Previous change',()=>navigateChange(-1)),changeLabel,button('Next change',()=>navigateChange(1)));
    bar.append(changes);
    const legend=el('div',undefined,'canvas-legend');
    legend.append(el('span','━━ Declared relationships'),el('span','┄┄ SQL-derived dependencies'),el('span','··· Document evidence'),el('span',readOnly?'Read-only version':'Added · Modified · Removed · Affected'));
    const dependencyWarnings=el('details',undefined,'canvas-dependency-warnings');
    const warningSummary=el('summary'),warningList=el('ul');
    dependencyWarnings.append(warningSummary,warningList);
    dependencyWarnings.hidden=true;
    const defs=svg('defs'),marker=svg('marker',{id:'canvas-arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:7,markerHeight:7,orient:'auto-start-reverse'});marker.append(svg('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#64748b'}));defs.append(marker);surface.append(defs,world);
    stage.append(surface,mini,zoomControls,status);
    root.replaceChildren(bar,optionsPanel,legend,dependencyWarnings,stage);
    function label(n) {
      return n.label||n.name||n.id;
    }

    function kind(n) {
      return n.kind||n.type||n.category||'dataset';
    }

    function isColumn(n) {
      return ['column','attribute','field'].includes(kind(n));
    }

    function parentId(n) {
      return n.dataset_id||n.parent_id||n.metadata?.dataset_id;
    }

    function visibleNodes() {
      return graph.nodes.filter(n=>(kind(n)!=='document'||selected===n.id)&&(!neighborhood||neighborhood.has(n.id)||neighborhood.has(parentId(n)))&&(!isColumn(n)||lens==='metadata'||expanded.has(parentId(n))||expanded.has(n.id)||selected===n.id));
    }

    function position(n,i) {
      if(!positions[n.id]) {
        const column=isColumn(n), metric=kind(n)==='metric', document=kind(n).startsWith('document');
        const group=document?3:metric?2:column?1:0;
        const peers=visibleNodes().filter(x=> (kind(x).startsWith('document')?3:kind(x)==='metric'?2:isColumn(x)?1:0)===group);
        positions[n.id]= {
          x:(document?740:metric?(lens==='metadata'||expanded.size?740:350):column?370:25),automatic:true,y:peers.findIndex(x=>x.id===n.id)*110+30
        };
      }if(positions[n.id].automatic&&kind(n)==='metric')positions[n.id].x=lens==='metadata'||expanded.size?740:350;return positions[n.id];
    }

    function applyTransform() {
      world.setAttribute('transform',`translate(${transform.x} ${transform.y}) scale(${transform.k})`);
    }

    function changeStatus(n) {
      return n.change_status||n.change||n.status==='removed'&&'removed'||'';
    }

    function select(n) {
      selected=n.id;
      options.onSelect?.(n);
      if(!readOnly)document.dispatchEvent(new CustomEvent('studio:select', {
        detail: {
          type:kind(n),id:n.id,node:n
        }
      }));
      if(readOnly && kind(n)==='document')focus(n.id);
      else render();
    }

    function render() {
      world.replaceChildren();
      mini.replaceChildren();
      const nodes=visibleNodes(),ids=new Set(nodes.map(n=>n.id));
      nodes.forEach(position);
      graph.edges.map(edge=> {
        const e= {
          ...edge
        };
        for(const key of ['source','target']) {
          if(!ids.has(e[key])) {
            const n=graph.nodes.find(n=>n.id===e[key]);
            if(n&&parentId(n))e[key]=parentId(n);
          }
        }return e;
      }).filter(e=>ids.has(e.source)&&ids.has(e.target)&&e.source!==e.target).forEach(e=> {
        const a=positions[e.source],b=positions[e.target],derived=(e.kind||e.type||'').includes('depend'),evidence=e.kind==='document_evidence';
        const p=svg('path', {
          d:a.x>b.x?`M ${a.x} ${a.y+35} C ${a.x-70} ${a.y+35}, ${b.x+300} ${b.y+35}, ${b.x+230} ${b.y+35}`:`M ${a.x+230} ${a.y+35} C ${a.x+300} ${a.y+35}, ${b.x-70} ${b.y+35}, ${b.x} ${b.y+35}`,'data-edge-id':e.id,'marker-end':'url(#canvas-arrow)',class:`canvas-edge ${evidence?'evidence':derived?'derived':'declared'} ${mode==='Changes'?changeStatus(e):''}`
        });
        p.onclick=()=> {
          if(evidence){const doc=graph.nodes.find(n=>n.id===e.document_id);if(doc)select(doc);return;}
          if(!readOnly)document.dispatchEvent(new CustomEvent('studio:select', {
            detail: {
              type:'join',id:e.id,edge:e
            }
          }));
          options.onSelect?.(e);
        };
        world.append(p);
        const t=svg('text', {
          x:(a.x+b.x+230)/2,y:(a.y+b.y)/2+25,class:'canvas-edge-label'
        });
        t.textContent=String(e.label||e.name||(derived?'SQL dependency':'many-to-one')).slice(0,38);
        world.append(t);
      });
      nodes.forEach((n,i)=> {
        const p=position(n,i),g=svg('g', {
          transform:`translate(${p.x} ${p.y})`,class:`canvas-node ${kind(n)} ${selected===n.id?'selected':''} ${mode==='Changes'?changeStatus(n):''}`,'data-node-id':n.id,tabindex:0,role:'button','aria-label':`${kind(n)}: ${label(n)}`
        });
        g.append(svg('rect', {
          width:230,height:76,rx:9
        }));
        const t=svg('text', {
          x:12,y:22
        });
        t.textContent=label(n).slice(0,32);
        const sub=svg('text', {
          x:12,y:43,class:'canvas-node-type'
        });
        sub.textContent=[kind(n)==='document_group'?'document collection':kind(n),n.data_type||n.metadata?.data_type,mode==='Changes'?changeStatus(n):''].filter(Boolean).join(' · ');
        const detail=svg('text', {
          x:12,y:63,class:'canvas-node-detail'
        });
        detail.textContent=String(n.expression||n.metadata?.expression||n.description||'').slice(0,34);
        g.append(t,sub,detail);
        if(mode==='Edit'&&isColumn(n)) {
          const handle=svg('circle', {
            cx:221,cy:38,r:7,class:'canvas-connect-handle','data-connect-field':n.id,'aria-label':'Drag relationship from '+label(n)
          });
          handle.addEventListener('pointerdown',event=> {
            event.stopPropagation();
            event.preventDefault();
            connection=n.id;
            status.textContent='Release on a target field to declare a relationship.';
            const release=up=> {
              const target=document.elementFromPoint(up.clientX,up.clientY)?.closest('[data-node-id]');
              document.removeEventListener('pointerup',release);
              const targetNode=graph.nodes.find(x=>x.id===target?.getAttribute('data-node-id'));
              if(targetNode&&isColumn(targetNode)&&targetNode.id!==n.id)openRelationship(n.id,targetNode.id);
              connection=null;
            };
            document.addEventListener('pointerup',release, {
              once:true
            });
          });
          g.append(handle);
        }g.onkeydown=e=> {
          if(e.key==='Enter'||e.key===' ') {
            e.preventDefault();
            select(n);
          }if(mode==='Edit'&&e.key==='c'&&isColumn(n)) {
            connection=n.id;
            status.textContent='Select the target field, or use Connect fields.';
          }
        };
        g.addEventListener('pointerdown',e=> {
          if(e.button!==0)return;
          e.stopPropagation();
          if(readOnly){select(n);return;}
          const start= {
            x:e.clientX,y:e.clientY,px:p.x,py:p.y
          };
          g.setPointerCapture(e.pointerId);
          g.onpointermove=ev=> {
            p.automatic=false;p.x=start.px+(ev.clientX-start.x)/transform.k;
            p.y=start.py+(ev.clientY-start.y)/transform.k;
            g.setAttribute('transform',`translate(${p.x} ${p.y})`);
          };
          g.onpointerup=event=> {
            g.onpointermove=null;
            const moved=Math.hypot(event.clientX-start.x,event.clientY-start.y)>4;
            if(!moved) {
              p.x=start.px;
              p.y=start.py;
              if(connection&&isColumn(n)&&connection!==n.id) {
                openRelationship(connection,n.id);
                connection=null;
              }else select(n);
            }else render();
          };
        });
        world.append(g);
        const r=svg('rect', {
          x:p.x,y:p.y,width:230,height:76,rx:8,class:`mini-node ${selected===n.id?'selected':''}`
        });
        r.onclick=()=>focus(n.id);
        mini.append(r);
      });
      if(nodes.length) {
        const ps=nodes.map(n=>positions[n.id]);
        mini.setAttribute('viewBox',`0 0 ${Math.max(...ps.map(p=>p.x))+260} ${Math.max(...ps.map(p=>p.y))+106}`);
      }applyTransform();
      const warnings = !graph.dirty && graph.draft_revision === graph.saved_revision
        ? Object.entries(graph.metric_dependencies || {}).flatMap(([id, entry]) =>
          (entry.warnings || []).map(message => `${label(graph.nodes.find(n => n.id === id) || {id})}: ${message}`))
        : [];
      dependencyWarnings.hidden = warnings.length === 0;
      warningSummary.textContent = `${warnings.length} SQL dependency warnings`;
      warningList.replaceChildren(...warnings.map(message => el('li', message)));
      status.textContent=nodes.length?`${nodes.length} objects · ${mode==='Edit'?'Drag changes layout only. Press C on a field to connect.':mode==='Changes'?`Changes against ${graph.baseline_version || 'starter'}.`:graph.dirty?'Save to refresh SQL dependencies. Layout changes do not edit the draft.':'SQL-derived dependencies describe saved definitions; they are not observed execution.'}`:'No graph objects available.';
      Object.entries(modeButtons).forEach(([m,b])=>b.setAttribute('aria-pressed',String(m===mode)));
      changes.hidden=mode!=='Changes';
      const anchor=selectedObject();
      neighborsButton.disabled=!anchor;
      columnsButton.disabled=!anchor||kind(anchor)!=='dataset';
      neighborsButton.setAttribute('aria-pressed',String(focusKind==='neighbors'));
      columnsButton.setAttribute('aria-pressed',String(focusKind==='columns'));
      allButton.setAttribute('aria-pressed',String(focusKind==='all'));
      if(anchor&&focusKind==='neighbors')status.textContent=`Neighbors · ${nodes.length} objects${neighborhood?.size===1?' · No related datasets or metrics.':''}`;
      if(anchor&&focusKind==='columns')status.textContent='Dataset columns · Use Neighbors for relationships or Show all for the overview.';
    }

    function focus(id) {
      const n=graph.nodes.find(n=>n.id===id);
      if(!n)return;
      selected=id;
      if(neighborhood&&!neighborhood.has(n.id)&&!neighborhood.has(parentId(n))){neighborhood=null;focusKind='all';}
      if(isColumn(n))expanded.add(parentId(n));
      if(kind(n)==='document'){
        neighborhood=new Set([id]);
        graph.edges.filter(e=>e.kind==='document_evidence'&&e.source===id).forEach(e=>neighborhood.add(e.target));
        lens='semantic';view.value=lens;expanded.clear();focusKind='neighbors';
        render();fit();return;
      }
      render();
      const p=positions[id];
      transform.x=stage.clientWidth/2-(p.x+115)*transform.k;
      transform.y=stage.clientHeight/2-(p.y+38)*transform.k;
      applyTransform();
    }

    function fit() {
      const nodes=visibleNodes();
      if(!nodes.length)return;
      nodes.forEach(position);
      const ps=nodes.map(n=>positions[n.id]),left=Math.min(...ps.map(p=>p.x)),top=Math.min(...ps.map(p=>p.y)),w=Math.max(...ps.map(p=>p.x))+260-left,h=Math.max(...ps.map(p=>p.y))+106-top;
      transform.k=Math.max(.15,Math.min(1.2,(stage.clientWidth-60)/w,(stage.clientHeight-60)/h));
      transform.x=30-left*transform.k;
      transform.y=30-top*transform.k;
      applyTransform();
    }

    function zoom(factor) {
      const old=transform.k,next=Math.max(.15,Math.min(2.5,old*factor)),cx=stage.clientWidth/2,cy=stage.clientHeight/2;
      transform.x=cx-(cx-transform.x)*next/old;
      transform.y=cy-(cy-transform.y)*next/old;
      transform.k=next;
      applyTransform();
    }     surface.addEventListener('wheel',e=> {
      e.preventDefault();
      zoom(e.deltaY>0?.9:1.1);
    }, {
      passive:false
    });
    surface.addEventListener('pointerdown',e=> {
      if(e.target!==surface)return;
      const start= {
        x:e.clientX,y:e.clientY,tx:transform.x,ty:transform.y
      };
      surface.setPointerCapture(e.pointerId);
      surface.onpointermove=v=> {
        transform.x=start.tx+v.clientX-start.x;
        transform.y=start.ty+v.clientY-start.y;
        applyTransform();
      };
      surface.onpointerup=()=> {
        surface.onpointermove=null;
      };
    });
    surface.onkeydown=e=> {
      if(e.key==='+'||e.key==='=')zoom(1.2);
      if(e.key==='-')zoom(.8);
      if(e.key==='0')fit();
    };
    function setMode(m) {
      if(readOnly && m!=='Lineage')return;
      mode=m;
      render();
      if(m==='Changes')navigateChange(0);
    }

    function navigateChange(delta) {
      const items=(graph.review_items||graph.changes?.items||graph.nodes.filter(n=>changeStatus(n))).filter(item=>(item.change||changeStatus(item))!=='unchanged');
      if(!items.length) {
        changeLabel.textContent='No baseline changes';
        return;
      }changeIndex=(changeIndex+delta+items.length)%items.length;
      const item=items[changeIndex];
      changeLabel.textContent=`${changeIndex+1}/${items.length} · ${item.label||item.name||item.id}`;
      focus(item.node_id||item.id);
      options.onReviewItem?.(item);
    }

    function openRelationship(from='',to='') {
      if(readOnly)return;
      if(mode!=='Edit') {
        setMode('Edit');
      }const fields=graph.nodes.filter(isColumn);
      const dialog=el('dialog',undefined,'canvas-relationship-dialog'),form=el('form');
      form.method='dialog';
      const title=el('h2','Declare a relationship');
      title.id=(root.id||'semantic-canvas')+'-relationship-title';
      const help=el('p','The server validates SQL and join cardinality before review.');
      help.id=(root.id||'semantic-canvas')+'-relationship-help';
      dialog.setAttribute('aria-labelledby',title.id);
      dialog.setAttribute('aria-describedby',help.id);
      form.append(title,help);
      const inputs= {
      };
      [['from_field','From field'],['to_field','To field'],['name','Name'],['meaning','Meaning']].forEach(([key,title])=> {
        const l=el('label',title),input=key.includes('field')?el('select'):el(key==='meaning'?'textarea':'input');
        input.name=key;
        input.required=true;
        if(key==='name') {
          input.pattern='[A-Za-z][A-Za-z0-9_]*';
          input.maxLength=80;
        }if(key==='meaning'){input.maxLength=1000;input.rows=2;}
        if(key.includes('field')){const placeholder=el('option','Choose a field');placeholder.value='';input.append(placeholder);}
        if(key.includes('field'))fields.forEach(n=> {
          const o=el('option',n.qualified||n.metadata?.qualified||label(n));
          o.value=n.qualified||n.metadata?.qualified||label(n);
          o.dataset.nodeId=n.id;
          input.append(o);
        });
        l.append(input);
        form.append(l);
        inputs[key]=input;
      });
      for(const [key,id]of [['from_field',from],['to_field',to]]) {
        const o=[...inputs[key].options].find(o=>o.dataset.nodeId===id);
        if(o)inputs[key].value=o.value;
      }inputs.name.value='relationship_'+Date.now().toString(36);
      form.append(el('p','Cardinality: many-to-one'));
      const error=el('p',undefined,'canvas-form-error');
      error.setAttribute('role','alert');
      form.append(error);
      const actions=el('div',undefined,'canvas-dialog-actions');
      const cancel=button('Cancel',()=>dialog.close());cancel.className='secondary';
      actions.append(cancel);
      const submit=el('button','Add relationship');
      submit.type='submit';
      actions.append(submit);
      form.append(actions);
      form.onsubmit=e=> {
        e.preventDefault();
        const relationship= {
          cardinality:'many_to_one'
        };
        Object.entries(inputs).forEach(([key,input])=>relationship[key]=input.value.trim());
        if(relationship.from_field===relationship.to_field) {
          error.textContent='Choose two different fields.';
          return;
        }const host=options.host||window.contextStudio,definition=host?.getState?.().definition;
        const joins=definition?.joins||[];
        const sourceField=fields.find(n=>n.qualified===relationship.from_field),targetField=fields.find(n=>n.qualified===relationship.to_field);
        if(joins.length>=20) {
          error.textContent='The draft supports at most 20 relationships.';
          return;
        }if(sourceField&&targetField&&parentId(sourceField)===parentId(targetField)) {
          error.textContent='Choose fields from two different datasets.';
          return;
        }const sourceType=sourceField?.data_type,targetType=targetField?.data_type;
        if(sourceType&&targetType&&sourceType!==targetType) {
          error.textContent='Choose fields with matching data types.';
          return;
        }if(joins.some(j=>j.name===relationship.name||(j.from_field===relationship.from_field&&j.to_field===relationship.to_field))) {
          error.textContent='This name or field relationship already exists.';
          return;
        }if(host?.getState?.().busy) {
          error.textContent='Wait for the current operation to finish.';
          return;
        }if(options.onCreateRelationship)options.onCreateRelationship(relationship);
        else if(host?.updateDefinition)host.updateDefinition(d=> {
          d.joins.push(relationship);
        });
        else {
          error.textContent='Relationship editing is unavailable.';
          return;
        }dialog.close();
      };
      dialog.append(form);
      root.append(dialog);
      dialog.addEventListener('close',()=>{dialog.remove();connection=null;render();});
      dialog.showModal();
    }

    function update(data) {
      const raw=data.graph||data;
      graph= {
        ...raw,nodes:[...(raw.nodes||[])],edges:[...(raw.edges||[])]
      };
      const known=new Set(graph.nodes.map(n=>n.id));
      graph.nodes.filter(n=>Array.isArray(n.columns)).forEach(dataset=>dataset.columns.forEach(column=> {
        if(known.has(column.id))return;
        known.add(column.id);
        graph.nodes.push( {
          ...column,data_type:column.type,type:'column',kind:'column',label:column.qualified||column.name,dataset_id:dataset.id
        });
        graph.edges.push( {
          id:'contains:'+column.id,source:dataset.id,target:column.id,kind:'contains',label:'Contains field'
        });
      }));
      const definition=(options.host||(readOnly?null:window.contextStudio))?.getState?.().definition;
      if(definition) {
        definition.metrics.forEach((metric,index)=> {
          const id=metric.id||'metric:'+metric.name;
          if(!known.has(id)) {
            graph.nodes.push( {
              ...metric,id,type:'metric',kind:'metric',label:metric.name
            });
            known.add(id);
          }
          // SQL dependencies are authoritative only for the current saved revision.
          const dependencies = !data.dirty && raw.draft_revision === data.saved_revision
            ? raw.metric_dependencies?.[id] : null;
          const refs = new Set(dependencies?.fields || []);
          refs.forEach(ref=> {
            const field=graph.nodes.find(n=>isColumn(n)&&(n.qualified===ref||n.label===ref));
            if(field)graph.edges.push( {
              id:'dependency:'+id+':'+field.id,source:field.id,target:id,kind:'sql_dependency',label:(dependencies?.dimension_fields||[]).includes(ref)?'Dimension dependency':'SQL expression dependency'
            });
          });
        });
        graph.edges=graph.edges.filter(e=>e.kind!=='join');
        definition.joins.forEach(join=> {
          const from=graph.nodes.find(n=>isColumn(n)&&n.qualified===join.from_field),to=graph.nodes.find(n=>isColumn(n)&&n.qualified===join.to_field);
          graph.edges.push( {
            ...join,id:join.id||'join:'+join.name,source:from?.dataset_id||join.from_field.split('.')[0],target:to?.dataset_id||join.to_field.split('.')[0],kind:'join',label:join.name+' · many-to-one'
          });
        });
      }
      graph.nodes.filter(n=>kind(n)==='document').forEach(doc=>{
        (doc.semantic_links||[]).forEach((link,index)=>{
          const separator=link.target.indexOf(':'),type=link.target.slice(0,separator),name=link.target.slice(separator+1);
          const target=graph.nodes.find(n=>type==='table'?kind(n)==='dataset'&&n.id===name:
            type==='field'?isColumn(n)&&n.qualified===name:
            type==='metric'?kind(n)==='metric'&&(n.name===name||n.label===name):
            type==='concept'?(kind(n)==='concept'&&n.name===name)||n.id===link.target:false);
          if(target)graph.edges.push({id:'semantic-evidence:'+doc.id+':'+index,source:doc.id,target:target.id,
            kind:'document_evidence',label:'Reviewer-linked passage · document assertion',document_id:doc.id,
            supporting_material_link:link});
        });
      });
      const review=raw.review_items||raw.changes?.items||[];
      graph.review_items=review;
      review.forEach(item=> {
        let node=graph.nodes.find(n=>n.id===item.id||n.name===item.name||n.qualified===item.name);
        if(!node&&item.change==='removed'&&item.before) {
          node= {
            ...item.before,id:item.id,kind:item.kind,type:item.kind,label:item.name
          };
          graph.nodes.push(node);
        }if(node)node.change_status=item.change;
        const edge=graph.edges.find(e=>e.id===item.id||e.name===item.name);
        if(edge)edge.change_status=item.change;
      });
      const nextScope=String(data.scope||`${data.pack_id||data.pack||'default'}:${data.snapshot_id||data.snapshot||'default'}`);
      if(nextScope!==scope) {
        scope=nextScope;
        positions= {
        };
        expanded=new Set();
        selected='';neighborhood=null;focusKind='all';lens='semantic';view.value=lens;
      }render();
      if(!selected)fit();
    }

    function selection(event) {
      if(event.detail?.id)focus(event.detail.id);
    }if(!readOnly)document.addEventListener('studio:select',selection);
    const resize=new ResizeObserver(()=> {
      if(!selected)fit();
    });
    resize.observe(stage);
    render();
    return {
      update,focus,setMode,openRelationship,getState:()=>( {
        mode,lens,selected,scope,focusKind,positions:structuredClone(positions),transform: {
          ...transform
        }
      }),destroy() {
        resize.disconnect();
        document.removeEventListener('studio:select',selection);
        document.removeEventListener('fullscreenchange',fullscreenChanged);
        root.replaceChildren();
      }
    };
  }   window.HeliosCanvas= {
    mount
  };
})();
