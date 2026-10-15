/* Saved lakehouse settings, independent from the offline source fixture. */
const lakehouseKeys=['trino_host','trino_port','trino_scheme','trino_user','trino_password','trino_catalog','trino_schema'];
let lakehouseLoaded=false,lakehouseLoading=false;
function lakehouseState(values){
 const ready=Boolean(values.trino_host&&values.trino_user);
 $('lakehouse-state').textContent=ready?'Saved · not verified':'Not configured';
 $('lakehouse-test').disabled=!ready;$('lakehouse-live').disabled=!ready;
}
async function loadLakehouse(){
 if(lakehouseLoaded||lakehouseLoading)return;
 lakehouseLoading=true;
 try{
  const data=await api('api/settings'),values=data.groups.data;
  const box=$('lakehouse-fields');box.replaceChildren();
  for(const [key,label,type,placeholder] of fields.data.filter(f=>lakehouseKeys.includes(f[0]))){
   const wrap=fieldInput(key,label,type,placeholder||'',values[key]);
   const input=wrap.querySelector('[name]');input.id='lakehouse-'+key;
   const clear=wrap.querySelector('[id^="clear-"]');if(clear)clear.id='lakehouse-clear-'+key;
   if(key==='trino_host'||key==='trino_user')input.required=true;
   if(key==='trino_port'){input.required=true;input.min='1';input.max='65535';}
   box.append(wrap);
  }
  lakehouseState(values);lakehouseLoaded=true;
 }catch(e){$('lakehouse-state').textContent='Settings unavailable';feedback('lakehouse-feedback',e.message,true);}
 finally{lakehouseLoading=false;}
}
$('lakehouse-form').onsubmit=async event=>{
 event.preventDefault();
 if(prep.pending){feedback('lakehouse-feedback','Wait for source discovery to finish before saving.',true);return;}
 const values={};
 for(const key of lakehouseKeys){
  const input=$('lakehouse-'+key);
  values[key]=key==='trino_password'?($('lakehouse-clear-'+key).checked?'':input.value||null):key==='trino_port'?Number(input.value):input.value.trim();
 }
 $('lakehouse-save').disabled=true;
 try{
  await api('api/settings/connections/data',values);
  lakehouseLoaded=false;await loadLakehouse();
  $('prep-mode').onchange();await config();
  feedback('lakehouse-feedback','Lakehouse connection saved. Test it, then choose Use live lakehouse to discover real tables.');
 }catch(e){feedback('lakehouse-feedback',e.message,true);}
 finally{$('lakehouse-save').disabled=false;}
};
$('lakehouse-form').addEventListener('input',()=>{
 $('lakehouse-state').textContent='Unsaved changes';
 $('lakehouse-test').disabled=true;$('lakehouse-live').disabled=true;
});
$('lakehouse-test').onclick=async()=>{
 const button=$('lakehouse-test');button.disabled=true;
 feedback('lakehouse-feedback','Testing the saved Trino connection…');
 try{
  const result=await api('api/settings/connections/data/test',{});
  const trino=result.targets.find(target=>target.name==='Trino');
  if(!trino)throw new Error('The connection test returned no Trino result.');
  const reachable=trino.state==='reachable';
  $('lakehouse-state').textContent=reachable?'Connection verified':'Connection unavailable';
  feedback('lakehouse-feedback',reachable?'Trino connection verified. Choose Use live lakehouse, then load catalogs.':trino.detail||'Trino connection failed.',!reachable);
 }catch(e){$('lakehouse-state').textContent='Connection unavailable';feedback('lakehouse-feedback',e.message,true);}
 finally{button.disabled=false;}
};
$('lakehouse-live').onclick=()=>{
 if(prep.pending)return;
 $('prep-mode').value='live';$('prep-mode').onchange();
 $('sources-view').scrollIntoView({behavior:'smooth',block:'start'});$('source-discover').focus({preventScroll:true});
};
