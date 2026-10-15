"""Deterministic evidence summaries: raw logs are not sent to the LLM."""
def summarize(tool,data):
    rows=data.get('rows',[])
    if not rows:
        return 'No matching results returned. Check scope and data availability before concluding that the platform is healthy.'
    if tool=='nifi_processors':
        stopped=sum(r.get('state')=='STOPPED' for r in rows)
        invalid=sum(r.get('validationStatus')=='INVALID' for r in rows)
        return f'Among {len(rows)} returned processors, {stopped} are stopped and {invalid} are invalid. A stopped processor is not necessarily a failure; review its intended operating state.'
    if tool=='nifi_status':
        row=rows[0]
        return f"The process group {row.get('name','')} reports {row.get('queuedCount','unknown')} queued FlowFiles and {row.get('activeThreadCount','unknown')} active threads. This is a current snapshot, not a historical trend."
    if tool=='nifi_bulletins':
        return f'{len(rows)} recent bulletins were returned. Inspect the source processor and message below; bulletins alone do not establish root cause.'
    if tool=='logs':
        errors=sum('error' in str(r.get('message','')).lower() for r in rows)
        return f'{len(rows)} log events are displayed for the selected window; {errors} contain “error”. These are observations from the returned events, not a complete incident or root-cause assessment.'
    if tool=='metrics':
        vals=[]
        for r in rows:
            try:vals.append(float(r['latest']))
            except (ValueError,TypeError,KeyError):pass
        if data.get('query')=='up':
            return f'{len(rows)} target series are displayed. At their latest returned samples, {sum(v==0 for v in vals)} report down and {sum(v==1 for v in vals)} report up. Scrape availability does not establish application health.'
        return f'{len(rows)} metric series are displayed for the selected window. Review labels and the latest values below; the chart shows the first returned series.'
    if tool=='semantic_describe':
        counts={kind:sum(r.get('type')==kind for r in rows) for kind in ['dataset','metric','relationship']}
        return f"Retrieved definitions include {counts['dataset']} datasets, {counts['metric']} metrics and {counts['relationship']} relationships. These definitions describe the data; no business-data query has been executed."
    if data.get('synthetic') and tool=='semantic_query' and len(rows)==1:
        values=', '.join(str(name)+': '+str(value) for name,value in rows[0].items())
        return 'Synthetic financial result — '+values+'. The executed SQL and reviewed sample release are shown below.'
    return f'{len(rows)} rows were returned by the compiled semantic query. The executed SQL and pinned model version are available below.'
