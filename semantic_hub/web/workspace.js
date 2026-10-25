"use strict";
const $ = (id) => document.getElementById(id),
  esc = (v) =>
    String(v ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
let workspaces = [],
  providers = [],
  current = null,
  view = "studio",
  generation = 0;
const titles = {
  studio: "Semantic Studio",
  sources: "Data sources",
  tables: "Tables",
  chat: "Talk to your data",
  providers: "Builders & connections",
};
const tag = (text, green = false) =>
  `<span class="tag ${green ? "green" : ""}">${esc(text)}</span>`;
const anchor = (text, url, primary = false) =>
  url
    ? `<a class="${primary ? "primary" : ""}" href="${esc(url)}" ${url.startsWith("https:") || url.startsWith("http:") ? 'target="_blank" rel="noopener noreferrer"' : ""}>${esc(text)} ↗</a>`
    : "";
async function api(path, body) {
  const r = await fetch(path, {
    headers: body ? { "Content-Type": "application/json" } : {},
    ...(body ? { method: "POST", body: JSON.stringify(body) } : {}),
  });
  let d;
  try {
    d = await r.json();
  } catch {
    throw Error(
      "The service returned an unexpected response. Check application access.",
    );
  }
  if (!r.ok)
    throw Error(
      typeof d.detail === "string"
        ? d.detail
        : JSON.stringify(d.detail || d.error || d),
    );
  return d;
}
const built = (path, suffix = "") =>
  `${path}?source=${encodeURIComponent(current.id)}${suffix}`;
function notice(message) {
  $("notice").textContent = message || "";
  $("notice").hidden = !message;
}
function heading(title, description, action = "") {
  return `<div class="heading"><div><h1>${esc(title)}</h1><p>${esc(description)}</p></div>${action}</div>`;
}
function empty(title, text, action = "") {
  return `<div class="panel empty"><h2>${esc(title)}</h2><p>${esc(text)}</p>${action}</div>`;
}
function rowsTable(columns, rows) {
  return `<div class="table-scroll"><table><thead><tr>${columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${esc(c ?? "—")}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
function details(items) {
  return items
    .map(
      ([k, v]) =>
        `<div class="detail-row"><span>${esc(k)}</span><strong>${esc(v ?? "Not specified")}</strong></div>`,
    )
    .join("");
}
function providerHandoff() {
  const key = view === "tables" ? "sources" : view;
  return (
    heading(titles[view], `${current.name} · ${current.provider_name}`) +
    empty(
      "Continue in " + current.provider_name,
      "This workspace is linked to its native builder. Review model access and publication there. External definitions and queries are not imported into this Hub yet.",
      anchor(
        "Open " +
          (view === "chat"
            ? "Talk to your data"
            : view === "studio"
              ? "Studio"
              : "data sources"),
        current.links[key],
        true,
      ),
    )
  );
}
async function load() {
  const selected = $("workspace").value;
  [workspaces, providers] = await Promise.all([
    api("/api/semantic-hub/v2/workspaces").then((d) => d.items),
    api("/api/semantic-hub/v2/providers").then((d) => d.items),
  ]);
  $("workspace").innerHTML = workspaces
    .map((w) => `<option value="${esc(w.id)}">${esc(w.name)}</option>`)
    .join("");
  const requested = new URL(location.href).searchParams.get("workspace");
  $("workspace").value = workspaces.some(
    (w) => w.id === (selected || requested),
  )
    ? selected || requested
    : workspaces[0]?.id || "";
  current = workspaces.find((w) => w.id === $("workspace").value);
  await render();
}
async function render() {
  const ticket = ++generation;
  notice("");
  current = workspaces.find((w) => w.id === $("workspace").value);
  $("provider-label").textContent = current?.provider_name || "No workspace";
  $("breadcrumb").textContent = titles[view];
  document
    .querySelectorAll("[data-view]")
    .forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  const url = new URL(location.href);
  url.searchParams.set("view", view);
  if (current) url.searchParams.set("workspace", current.id);
  history.replaceState(null, "", url);
  $("content").innerHTML = '<p class="muted">Loading workspace…</p>';
  try {
    if (view === "providers") {
      renderProviders();
      return;
    }
    if (!current) {
      $("content").innerHTML = empty(
        "Create a workspace",
        "Connect a builder to get started.",
      );
      return;
    }
    if (!current.native) {
      $("content").innerHTML = providerHandoff();
      return;
    }
    if (view === "sources") {
      renderSources();
      return;
    }
    if (current.kind !== "local") {
      $("content").innerHTML =
        heading(titles[view], current.name) +
        empty(
          "Source import required",
          "This connection stores a profile. Import and query support are not available for this source yet.",
          anchor("Inspect source setup", current.links.studio, true),
        );
      return;
    }
    if (view === "studio") {
      const data = await api(built("/demo/api/context"));
      if (ticket !== generation) return;
      renderStudio(data);
    }
    if (view === "tables") {
      const data = await api(built("/demo/api/context/tables", "&limit=50"));
      if (ticket !== generation) return;
      renderTables(data, ticket);
    }
    if (view === "chat") {
      const [catalog, config] = await Promise.all([
        api(built("/demo/api/playground")),
        api(built("/demo/api/config")),
      ]);
      if (ticket !== generation) return;
      renderChat(catalog, config, ticket);
    }
  } catch (e) {
    if (ticket === generation) {
      $("content").innerHTML = empty("Workspace could not load", e.message);
      notice(e.message);
    }
  }
}
function renderStudio(data) {
  const d = data.draft?.definition || {},
    metrics = d.metrics || [];
  const model = current.model || {};
  $("content").innerHTML =
    heading(
      "Semantic Studio",
      "Inspect business definitions, then open the editor to validate and publish.",
      anchor("Open editor", current.links.studio, true),
    ) +
    `<div class="metrics"><div class="metric"><span>METRICS</span><strong>${metrics.length}</strong></div><div class="metric"><span>SOURCE TABLES</span><strong>${model.table_count ?? "—"}</strong></div><div class="metric"><span>MODEL STATUS</span><strong style="font-size:19px">${esc(current.status)}</strong></div></div><div class="split"><section class="panel"><div class="panel-head"><h2>Business definitions</h2>${tag("Draft revision " + (data.draft?.revision ?? 0))}</div><div class="list" id="metric-list">${metrics.map((m, i) => `<button data-metric="${i}"><span>${esc(m.name.replaceAll("_", " "))}<small>${esc(m.description || "Review this definition in Studio.")}</small></span>${tag(m.unit || "Metric")}</button>`).join("") || '<div class="panel-body muted">No metrics defined yet.</div>'}</div></section><section class="panel"><div class="panel-head"><h2>Definition details</h2></div><div class="panel-body" id="metric-detail"></div></section></div><div class="toolbar" style="margin-top:20px">${anchor("Review supporting materials", "/demo/materials")}<span class="muted">Draft definitions become queryable after review and publication.</span></div>`;
  function select(i) {
    const m = metrics[i];
    if (!m) return;
    document
      .querySelectorAll("[data-metric]")
      .forEach((b) =>
        b.classList.toggle("selected", Number(b.dataset.metric) === i),
      );
    $("metric-detail").innerHTML =
      details([
        ["Metric", m.name],
        ["Business meaning", m.description],
        ["Unit", m.unit],
        ["Grain", m.grain],
        ["Time rule", m.time_rule],
      ]) + `<pre>${esc(m.expression || "No expression")}</pre>`;
  }
  document
    .querySelectorAll("[data-metric]")
    .forEach((b) => (b.onclick = () => select(Number(b.dataset.metric))));
  select(0);
}
function renderSources() {
  $("content").innerHTML =
    heading(
      "Data sources",
      "Source profiles, preparation status, and the builder responsible for each workspace.",
      anchor("Configure source", "/demo", true),
    ) +
    `<div class="toolbar"><input id="source-filter" aria-label="Filter data sources" placeholder="Search sources or builders…"><span class="muted">${workspaces.length} workspaces</span></div><section class="panel" id="source-table"></section>`;
  function draw() {
    const q = $("source-filter").value.toLowerCase();
    const list = workspaces.filter((w) =>
      `${w.name} ${w.provider_name} ${w.kind}`.toLowerCase().includes(q),
    );
    $("source-table").innerHTML =
      `<div class="table-scroll"><table><thead><tr><th>Source / workspace</th><th>Builder</th><th>Type</th><th>Status</th><th>Tables</th><th></th></tr></thead><tbody>${list.map((w) => `<tr><td><b>${esc(w.name)}</b></td><td>${esc(w.provider_name)}</td><td>${esc(w.kind)}</td><td>${tag(w.status, w.status === "published")}</td><td>${esc(w.model?.table_count ?? "—")}</td><td><button data-open="${esc(w.id)}">Inspect</button></td></tr>`).join("")}</tbody></table></div>`;
    document.querySelectorAll("[data-open]").forEach(
      (b) =>
        (b.onclick = () => {
          $("workspace").value = b.dataset.open;
          view = "studio";
          render();
        }),
    );
  }
  $("source-filter").oninput = draw;
  draw();
}
function renderTables(data, ticket) {
  $("content").innerHTML =
    heading(
      "Tables",
      `${current.name} · ${data.total} source tables. Previews are limited to 10 rows.`,
    ) +
    `<div class="split"><section class="panel"><div class="panel-head"><h2>Source schema</h2>${tag("Read only")}</div><div class="list" id="table-list">${data.items.map((t, i) => `<button data-table="${i}"><span>${esc(t.name)}<small>${t.field_count} columns · ${t.row_count.toLocaleString()} rows</small></span><span>→</span></button>`).join("")}</div></section><section class="panel"><div class="panel-head"><h2 id="table-title">Select a table</h2></div><div id="table-detail" class="panel-body"></div></section></div><section class="panel" style="margin-top:20px"><div class="panel-head"><h2>Sample preview</h2>${tag("Up to 10 rows")}</div><div id="table-preview"></div></section>`;
  let selected = 0;
  async function select(i) {
    selected = i;
    document
      .querySelectorAll("[data-table]")
      .forEach((b) =>
        b.classList.toggle("selected", Number(b.dataset.table) === i),
      );
    try {
      const t = await api(
        built(
          "/demo/api/context/table",
          "&name=" + encodeURIComponent(data.items[i].name),
        ),
      );
      if (ticket !== generation || selected !== i) return;
      $("table-title").textContent = t.name;
      $("table-detail").innerHTML = rowsTable(
        ["Column", "Type"],
        t.columns.map((c) => [c.name, c.type]),
      );
      const rows = t.rows || t.preview || [];
      $("table-preview").innerHTML = rowsTable(
        t.columns.map((c) => c.name),
        rows.map((r) =>
          Array.isArray(r) ? r : t.columns.map((c) => r[c.name]),
        ),
      );
    } catch (e) {
      if (ticket === generation) notice(e.message);
    }
  }
  document
    .querySelectorAll("[data-table]")
    .forEach((b) => (b.onclick = () => select(Number(b.dataset.table))));
  if (data.items.length) select(0);
}
function renderProviders() {
  $("content").innerHTML =
    heading(
      "Builders & connections",
      "Choose where semantic models are authored. Each builder keeps its own workspace and permissions.",
      '<button id="add-provider" class="primary">Connect Helios</button>',
    ) +
    `<div class="provider-grid">${providers.map((p) => `<section class="panel"><div class="panel-head"><h2>${esc(p.name)}</h2>${tag(p.kind === "builtin" ? "Available" : "Links only", p.kind === "builtin")}</div><div class="panel-body"><p class="muted">${p.kind === "builtin" ? "Build, review, and query the local sample models." : "Open native Helios Studio and Talk. Release import and delegated queries are not enabled."}</p>${p.kind === "builtin" ? anchor("Open source setup", "/demo", true) : `<div class="detail-row"><span>Application origin</span><strong>${esc(p.ui_origin)}</strong></div>${anchor("Open builder", p.ui_origin)}<button class="primary" style="margin-top:16px;margin-left:12px" data-link-project="${esc(p.id)}">Link a workspace</button>`}</div></section>`).join("")}</div>`;
  $("add-provider").onclick = () => setup("provider");
  document
    .querySelectorAll("[data-link-project]")
    .forEach(
      (b) => (b.onclick = () => setup("project", b.dataset.linkProject)),
    );
}
function setup(kind, provider) {
  $("setup-title").textContent =
    kind === "provider"
      ? "Connect a Helios builder"
      : "Link a Helios workspace";
  const fields =
    kind === "provider"
      ? [
          ["id", "Provider ID", "helios-team"],
          ["name", "Display name", "Helios team"],
          [
            "ui_origin",
            "UI application origin",
            "https://helios-ui.example.com",
          ],
          [
            "api_origin",
            "API application origin",
            "https://helios-api.example.com",
          ],
        ]
      : [
          ["name", "Workspace name", "Finance analytics"],
          ["organization_id", "Native organization ID", ""],
          ["model_id", "Native model ID", ""],
        ];
  $("setup-fields").innerHTML =
    fields
      .map(
        ([key, label, hint]) =>
          `<label>${label}<input name="${key}" placeholder="${hint}" required maxlength="${key.includes("origin") ? 1000 : 120}"></label>`,
      )
      .join("") +
    '<p class="muted">' +
    (kind === "provider"
      ? "URLs contain no credentials. Access is handled by the provider."
      : "Use identifiers from your Helios workspace. Its permissions are checked when you open it.") +
    "</p>";
  $("setup-error").textContent = "";
  $("setup").showModal();
  $("setup-form").onsubmit = async (e) => {
    e.preventDefault();
    const submit = e.submitter;
    submit.disabled = true;
    try {
      const body = Object.fromEntries(new FormData(e.target));
      if (kind === "project") body.provider_id = provider;
      await api(
        "/api/semantic-hub/v2/" +
          (kind === "provider" ? "providers" : "projects"),
        body,
      );
      $("setup").close();
      await load();
    } catch (err) {
      $("setup-error").textContent = err.message;
    } finally {
      submit.disabled = false;
    }
  };
}
function renderChat(catalog, config, ticket) {
  const versions = catalog.versions || [];
  const resultScope = current.model?.synthetic
    ? "Synthetic sample result"
    : "Local source result";
  $("content").innerHTML =
    heading(
      "Talk to your data",
      `${current.name} · Built-in workspace`,
    ) +
    (!versions.length
      ? empty(
          "Publish a model to start a conversation",
          "Questions use reviewed, published definitions. Open Studio to validate and publish a version.",
          anchor("Open Studio", current.links.studio, true),
        )
      : `<div class="chat-shell"><div class="toolbar"><label for="chat-version">Published version</label><select id="chat-version">${versions.map((v) => `<option>${esc(v.version)}</option>`).join("")}</select><button id="clear-chat" class="quiet">New conversation</button></div><div id="chat-thread" class="chat-thread"></div><form id="chat-form" class="composer"><textarea id="question" placeholder="Ask a question about this published model…" aria-label="Question" maxlength="2000" required></textarea><div class="composer-foot"><span>Inspect the interpretation before running.</span><button id="ask" class="primary">Prepare answer →</button></div></form></div>`);
  if (!versions.length) return;
  const binding = {
    pack_id: config.pack_id,
    snapshot_sha256: config.snapshot_sha256,
    session_id: config.session_id,
  };
  let turn = 0,
    busy = false,
    plan = null;
  const selected = () =>
    versions.find((v) => v.version === $("chat-version").value);
  function invalidate() {
    plan = null;
    document.querySelectorAll("[data-run]").forEach((b) => b.remove());
  }
  function reset() {
    turn++;
    invalidate();
    $("question").value = "";
    const v = selected();
    $("chat-thread").innerHTML =
      `<div class="chat-intro"><h2>What would you like to explore?</h2><p class="muted">Use a saved metric or ask about your published data and evidence.</p><div class="suggestions">${v.metrics.map((m, i) => `<button type="button" data-suggest="${i}">${esc(m.name.replaceAll("_", " "))}</button>`).join("")}</div>${anchor("Configure the query model", "/demo/llm")}</div>`;
    document.querySelectorAll("[data-suggest]").forEach(
      (b) =>
        (b.onclick = () => {
          const m = v.metrics[Number(b.dataset.suggest)];
          $("question").value = m.description || m.name;
          ask(m.name);
        }),
    );
  }
  function message(text, who = "") {
    const div = document.createElement("div");
    div.className = "bubble " + who;
    div.textContent = text;
    $("chat-thread").append(div);
    div.scrollIntoView({ block: "nearest" });
    return div;
  }
  function controls() {
    for (const id of ["ask", "chat-version", "clear-chat"])
      $(id).disabled = busy;
    document
      .querySelectorAll("[data-suggest]")
      .forEach((b) => (b.disabled = busy));
  }
  async function ask(metric = null) {
    if (busy || !$("question").value.trim()) return;
    const original = $("question").value.trim();
    invalidate();
    const n = ++turn;
    busy = true;
    controls();
    const v = selected();
    message(original, "user");
    const output = message("Preparing a checked interpretation…");
    try {
      const prepared = await api(built("/demo/api/playground/interpret"), {
        ...binding,
        version: v.version,
        context_sha256: v.context_sha256,
        question: original,
        metric,
        mode: metric ? "metric" : "auto",
      });
      if (ticket !== generation || n !== turn) return;
      if (prepared.status !== "ready") {
        output.textContent = prepared.message || prepared.status;
        return;
      }
      output.innerHTML = `<b>Review interpretation</b><p>${esc(prepared.interpretation || prepared.metric?.description || "Review the proposed scope.")}</p><details><summary>Scope and execution details</summary><pre>${esc(prepared.sql || JSON.stringify(prepared.request || prepared.scope_check || {}, null, 2))}</pre></details>`;
      if ($("question").value.trim() !== original) {
        output.append(
          document.createTextNode(
            "Question changed. Prepare a new interpretation before running.",
          ),
        );
        return;
      }
      plan = prepared;
      const run = document.createElement("button");
      run.className = "primary";
      run.dataset.run = "true";
      run.textContent = "Run this interpretation";
      output.append(run);
      run.onclick = async () => {
        if (!plan || busy) return;
        const saved = plan;
        invalidate();
        busy = true;
        controls();
        const answer = message("Running the approved interpretation…");
        try {
          const result = await api(built("/demo/api/playground/run"), {
            ...binding,
            plan_id: saved.plan_id,
          });
          if (ticket !== generation || n !== turn) return;
          if (result.columns) {
            answer.innerHTML = `<b>${esc(result.message || "Query result")}</b>${rowsTable(result.columns, result.rows || [])}<p class="muted">${esc(result.context_version || v.version)} · ${esc(resultScope)}</p>`;
          } else {
            answer.textContent =
              result.message ||
              "Response received. Inspect the evidence below.";
          }
          if (result.claims?.length) {
            for (const claim of result.claims) {
              const paragraph = document.createElement("p");
              paragraph.textContent = claim.text;
              answer.append(paragraph);
              for (const citation of claim.citations || []) {
                const quote = document.createElement("blockquote");
                quote.textContent =
                  (citation.title || citation.id || "Published evidence") +
                  ": " +
                  citation.quote;
                answer.append(quote);
              }
            }
          }
          const detail = document.createElement("details");
          detail.innerHTML = "<summary>Result provenance</summary>";
          const pre = document.createElement("pre");
          pre.textContent = JSON.stringify(result, null, 2);
          detail.append(pre);
          answer.append(detail);
          answer.scrollIntoView({ block: "nearest" });
        } catch (e) {
          answer.textContent = e.message;
        } finally {
          if (ticket === generation) {
            busy = false;
            controls();
          }
        }
      };
    } catch (e) {
      if (ticket === generation) output.textContent = e.message;
    } finally {
      if (ticket === generation) {
        busy = false;
        controls();
      }
    }
  }
  $("chat-form").onsubmit = (e) => {
    e.preventDefault();
    ask();
  };
  $("question").oninput = invalidate;
  $("chat-version").onchange = reset;
  $("clear-chat").onclick = reset;
  reset();
}
$("close-dialog").onclick = () => $("setup").close();
$("refresh").onclick = () => load().catch((e) => notice(e.message));
$("workspace").onchange = () => render();
document.querySelectorAll("[data-view]").forEach(
  (b) =>
    (b.onclick = () => {
      view = b.dataset.view;
      render();
    }),
);
const initial = new URL(location.href).searchParams.get("view");
if (titles[initial]) view = initial;
load().catch((e) => notice(e.message));
