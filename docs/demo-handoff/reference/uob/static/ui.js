/* Local page finder. It never searches or sends dataset contents. */
const pageFinder=document.getElementById('workspace-search');
const pageResults=document.getElementById('workspace-search-results');
const workspacePages=[
 {name:'Sources',group:'Prepare',selector:'[data-workflow="sources"]'},
 {name:'Build semantic context',group:'Prepare',selector:'[data-workflow="builder"]'},
 {name:'NiFi operations',group:'Explore',selector:'[data-tab="nifi"]'},
 {name:'Observability',group:'Explore',selector:'[data-tab="observability"]'},
 {name:'Data understanding',group:'Explore',selector:'[data-tab="data"]'}
];
function closeFinder(){pageResults.hidden=true;pageFinder.setAttribute('aria-expanded','false');}
function updateFinder(){
 const query=pageFinder.value.trim().toLowerCase();
 pageResults.replaceChildren();
 const matches=workspacePages.filter(p=>(p.name+' '+p.group).toLowerCase().includes(query));
 for(const page of matches){
  const button=document.createElement('button');button.type='button';button.className='search-result';
  const label=document.createElement('span');label.textContent=page.name;
  const group=document.createElement('small');group.textContent=page.group;
  button.append(label,group);
  button.onclick=()=>{document.querySelector(page.selector).click();pageFinder.value='';closeFinder();document.querySelector(page.selector).focus();};
  button.onkeydown=e=>{if(e.key==='Escape'){closeFinder();pageFinder.focus();}if(e.key==='ArrowDown'){e.preventDefault();button.nextElementSibling?.focus();}if(e.key==='ArrowUp'){e.preventDefault();(button.previousElementSibling||pageFinder).focus();}};
  pageResults.append(button);
 }
 if(!matches.length){const empty=document.createElement('p');empty.textContent='No matching workspace pages.';pageResults.append(empty);}
 pageResults.hidden=false;pageFinder.setAttribute('aria-expanded','true');
}
pageFinder.oninput=updateFinder;pageFinder.onfocus=updateFinder;
pageFinder.onkeydown=e=>{if(e.key==='Escape')closeFinder();if(e.key==='ArrowDown'){e.preventDefault();pageResults.querySelector('button')?.focus();}if(e.key==='Enter'){e.preventDefault();pageResults.querySelector('button')?.click();}};
document.addEventListener('click',e=>{if(!e.target.closest('.workspace-search'))closeFinder();});
document.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();pageFinder.focus();updateFinder();}});
