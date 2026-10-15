"use strict";
(async()=>{
  const id=new URL(location.href).searchParams.get("source");
  try {
    if(!id)throw new Error("Choose a source connection in Semantic Hub.");
    const response=await fetch(`/demo/api/hub/source?source=${encodeURIComponent(id)}`,{cache:"no-store"});
    const source=await response.json();
    if(!response.ok)throw new Error(source.detail || "Could not load this source.");
    document.getElementById("source-name").textContent=source.name;
    document.getElementById("setup-message").textContent=source.message;
    document.getElementById("adapter-status").textContent=source.kind==="atlas"
      ? "Atlas is a metadata source. This builder still needs a catalog import adapter and a paired query connection."
      : "This build saves connection profiles. Live source import and SQL execution adapters for this connection type are not available yet.";
    document.getElementById("configure-connection").href=`/demo?source=${encodeURIComponent(id)}`;
    const details=document.getElementById("source-details");
    for(const [key,value] of Object.entries({type:source.kind,status:source.status,...source.config})){
      const term=document.createElement("dt"),definition=document.createElement("dd");
      term.textContent=key.replaceAll("_"," ");definition.textContent=value || "Not set";details.append(term,definition);
    }
  }catch(error){const notice=document.getElementById("source-error");notice.textContent=error.message;notice.hidden=false;}
})();
