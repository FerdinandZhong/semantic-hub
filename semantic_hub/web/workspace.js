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
  view = "home",
  generation = 0;
const titles = {
  home: "Semantic workspaces",
  overview: "Workspace overview",
  chat: "Talk to your data",
  providers: "Builders & connections",
};
const statusName = (s) =>
  ({
    starter: "Starter",
    draft: "Draft",
    reviewed: "Reviewed",
    published: "Published",
    configured: "Configured",
    linked: "Linked",
  })[s] || s;
const editorUrl = (id, step = "define") =>
  `/v2/editor?source=${encodeURIComponent(id)}#${step}`;
const workspaceUrl = (id, next = "overview") =>
  `/v2?${new URLSearchParams({ view: next, workspace: id })}`;
const icon = (kind) => {
  const source = document.querySelector(`[data-nav="${kind}"] svg`);
  return source ? source.outerHTML : "";
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
  $("content").innerHTML =
    heading(
      current.name,
      "This workspace is managed by " + current.provider_name,
      tag("Linked provider"),
    ) +
    `<div class="split"><section class="panel"><div class="panel-head"><h2>Native semantic workspace</h2></div><div class="panel-body"><p>Continue in ${esc(current.provider_name)} to build this model or use its native conversation.</p><p class="muted">The provider checks model access. External definitions and queries have not been imported into this Hub.</p><div class="toolbar">${anchor("Open Studio", current.links.studio, true)}${anchor("Talk to your data", current.links.chat)}</div></div></section><section class="panel"><div class="panel-head"><h2>Workspace identity</h2></div><div class="panel-body">${details(
      [
        ["Builder", current.provider_name],
        ["Organization", current.organization_id],
        ["Native model", current.model_id],
        ["Integration", "Navigation only"],
      ],
    )}</div></section></div>`;
}
async function load() {
  const selected =
    $("workspace").value ||
    new URL(location.href).searchParams.get("workspace");
  [workspaces, providers] = await Promise.all([
    api("/api/semantic-hub/v2/workspaces").then((d) => d.items),
    api("/api/semantic-hub/v2/providers").then((d) => d.items),
  ]);
  $("workspace").innerHTML = workspaces
    .map((w) => `<option value="${esc(w.id)}">${esc(w.name)}</option>`)
    .join("");
  $("workspace").value = selected
    ? workspaces.some((w) => w.id === selected)
      ? selected
      : ""
    : workspaces[0]?.id || "";
  await render();
}
function navigate(next, id) {
  view = next;
  if (id !== undefined) $("workspace").value = id;
  const url = new URL(location.href);
  url.searchParams.set("view", view);
  if ($("workspace").value)
    url.searchParams.set("workspace", $("workspace").value);
  history.pushState(null, "", url);
  render();
}
function syncShell() {
  const scoped = view !== "home" && view !== "providers";
  $("workspace-bar").hidden = !scoped;
  $("workspace-tabs").hidden = !(
    view === "overview" &&
    current?.native &&
    current.kind === "local"
  );
  $("provider-label").textContent = current?.provider_name || "No workspace";
  $("breadcrumb").textContent = titles[view] || "Semantic workspace";
  const active = view === "overview" ? "workspace" : view;
  document.querySelectorAll("[data-nav]").forEach((a) => {
    const key = a.dataset.nav;
    a.classList.toggle("active", key === active);
    if (key === active) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
    if (key === "workspace" || key === "chat")
      a.href = workspaceUrl(
        current?.id || "",
        key === "workspace" ? "overview" : "chat",
      );
    if (key === "settings")
      a.href =
        "/v2/settings?" +
        new URLSearchParams({ source: current?.native ? current.id : "" });
  });
  $("workspace-tabs").innerHTML = current?.native
    ? `<a href="${esc(workspaceUrl(current.id))}" class="active" aria-current="page">Overview</a>` +
      [
        ["source", "Source data"],
        ["define", "Studio"],
        ["validate", "Validation & review"],
        ["hub", "Versions & releases"],
      ]
        .map(
          ([step, title]) =>
            `<a href="${esc(editorUrl(current.id, step))}">${title}</a>`,
        )
        .join("")
    : "";
}
async function render() {
  const ticket = ++generation;
  notice("");
  current = workspaces.find((w) => w.id === $("workspace").value);
  if (["studio", "tables", "sources", "review", "releases"].includes(view)) {
    const step = {
      studio: "define",
      tables: "source",
      sources: "source",
      review: "validate",
      releases: "hub",
    }[view];
    if (current?.native) {
      location.assign(editorUrl(current.id, step));
      return;
    }
    view = "overview";
  }
  syncShell();
  $("content").innerHTML = '<p class="muted">Loading workspace…</p>';
  try {
    if (view === "home") {
      renderHome();
      return;
    }
    if (view === "providers") {
      renderProviders();
      return;
    }
    if (!current) {
      $("content").innerHTML = empty(
        "Workspace unavailable",
        "Select an available workspace or return to the catalog.",
        anchor("All workspaces", "/v2", true),
      );
      return;
    }
    if (!current.native) {
      providerHandoff();
      return;
    }
    if (view === "overview") {
      renderOverview();
      return;
    }
    if (current.kind !== "local") {
      $("content").innerHTML = empty(
        "Source import required",
        "This connection stores a profile. Source import and query execution are not available for this connector yet.",
        anchor("Inspect source setup", editorUrl(current.id, "source"), true),
      );
      return;
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
function renderHome() {
  $("content").innerHTML =
    heading(
      "Semantic workspaces",
      "Find a workspace. Define meaning, review changes, and ask your data.",
      '<button id="new-workspace" class="primary">New workspace</button>',
    ) +
    `<div class="catalog-summary">${tag(workspaces.length + " workspaces")}${tag(providers.length + " builders")}${tag(workspaces.filter((w) => w.status === "published").length + " published models", true)}</div><div class="toolbar catalog-toolbar"><input id="workspace-search" type="search" placeholder="Search workspaces…" aria-label="Search workspaces"><select id="builder-filter" aria-label="Filter by builder"><option value="">All builders</option>${providers.map((p) => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("")}</select><select id="status-filter" aria-label="Filter by status"><option value="">All statuses</option>${[...new Set(workspaces.map((w) => w.status))].map((s) => `<option value="${esc(s)}">${esc(statusName(s))}</option>`).join("")}</select></div><div class="section-heading"><h2>Your workspaces</h2><span id="card-count" class="muted"></span></div><div id="workspace-cards" class="workspace-cards"></div>`;
  function draw() {
    const q = $("workspace-search").value.trim().toLowerCase(),
      provider = $("builder-filter").value,
      status = $("status-filter").value;
    const items = workspaces.filter(
      (w) =>
        (w.name + " " + w.description + " " + w.provider_name)
          .toLowerCase()
          .includes(q) &&
        (!provider || w.provider_id === provider) &&
        (!status || w.status === status),
    );
    $("card-count").textContent = items.length + " shown";
    $("workspace-cards").innerHTML =
      items
        .map(
          (w) =>
            `<article class="workspace-card"><div class="card-top"><span class="card-icon">${icon(w.native ? "workspace" : "providers")}</span>${tag(statusName(w.status), w.status === "published")}</div><h2>${esc(w.name)}</h2><p>${esc(w.model?.description || w.description)}</p><div class="card-meta"><span><b>${esc(w.model?.table_count ?? "—")}</b> tables</span><span><b>${esc(w.model?.metric_count ?? "—")}</b> metrics</span></div><div class="card-footer">${tag(w.provider_name)}<a data-open-workspace="${esc(w.id)}" href="${esc(workspaceUrl(w.id))}">Open workspace →</a></div></article>`,
        )
        .join("") ||
      empty("No matching workspaces", "Change the search or filters.");
    document.querySelectorAll("[data-open-workspace]").forEach(
      (a) =>
        (a.onclick = (e) => {
          if (e.ctrlKey || e.metaKey || e.shiftKey) return;
          e.preventDefault();
          navigate("overview", a.dataset.openWorkspace);
        }),
    );
  }
  for (const id of ["workspace-search", "builder-filter", "status-filter"])
    $(id).oninput = draw;
  $("new-workspace").onclick = () => newWorkspace();
  draw();
}
function renderOverview() {
  const m = current.model;
  if (!m) {
    $("content").innerHTML =
      heading(current.name, current.description) +
      empty(
        "Source profile configured",
        "This connector requires source import before semantic authoring or queries are available.",
        anchor("Inspect source setup", editorUrl(current.id, "source"), true),
      );
    return;
  }
  const published = (m.versions || []).filter((v) => v.published),
    latest = published[0];
  $("content").innerHTML =
    heading(
      current.name,
      "Inspect the current model, then continue building or use a published version.",
      anchor("Continue in Studio", editorUrl(current.id), true),
    ) +
    `<div class="metrics overview-metrics">${[
      [m.table_count, "SOURCE TABLES"],
      [m.metric_count, "BUSINESS METRICS"],
      [m.draft_revision, "DRAFT REVISION"],
      [latest?.version || "None", "PUBLISHED VERSION"],
    ]
      .map(
        ([v, label]) =>
          `<div class="metric"><span>${label}</span><strong>${esc(v)}</strong></div>`,
      )
      .join(
        "",
      )}</div><div class="split"><section class="panel"><div class="panel-head"><h2>Build and publish</h2>${tag(statusName(current.status), current.status === "published")}</div><div class="panel-body">${[
      ["source", "Source data", "Inspect tables and supporting documents."],
      [
        "define",
        "Studio",
        "Edit definitions, field meanings, and relationships.",
      ],
      [
        "validate",
        "Validation & review",
        "Check technical results and review each change.",
      ],
      [
        "hub",
        "Versions & releases",
        "Publish a reviewed version for consumers.",
      ],
    ]
      .map(
        ([step, title, description], i) =>
          `<div class="workflow-row"><div><strong>${i + 1}. ${title}</strong><p class="muted">${description}</p></div>${anchor("Open", editorUrl(current.id, step))}</div>`,
      )
      .join(
        "",
      )}</div></section><section class="panel"><div class="panel-head"><h2>Published model</h2>${tag(latest ? "Available" : "Not published", !!latest)}</div><div class="panel-body"><p>${latest ? `Version <strong>${esc(latest.version)}</strong> is published. Draft changes do not alter that release.` : "Validate and review the draft before publishing it for questions."}</p>${anchor(latest ? "Talk to your data" : "Review draft", latest ? workspaceUrl(current.id, "chat") : editorUrl(current.id, "validate"), true)}${details(
      [
        ["Builder", current.provider_name],
        ["Source", m.source_name],
        ["Data origin", m.generation_mode],
        ["Active version", m.active_version || "No active version"],
      ],
    )}</div></section></div>`;
}
async function newWorkspace() {
  $("setup-title").textContent = "New workspace";
  $("setup-error").textContent = "";
  $("setup-fields").innerHTML =
    '<p>Build a local workspace or link an existing provider workspace.</p><div class="toolbar"><button type="button" id="create-builtin" class="primary">Built-in workspace</button><button type="button" id="link-external">Link provider workspace</button></div>';
  $("setup-form").querySelector('[type="submit"]').hidden = true;
  $("setup").showModal();
  $("create-builtin").onclick = () =>
    configureSource().catch((e) => {
      $("setup-error").textContent = e.message;
    });
  $("link-external").onclick = () => {
    $("setup").close();
    navigate("providers");
  };
}
async function configureSource() {
  const catalog = await api("/demo/api/hub");
  const schemas = await api("/demo/api/connections/schema");
  $("setup-title").textContent = "New built-in workspace";
  $("setup-fields").innerHTML =
    `<label>Workspace name<input name="name" maxlength="120" required></label><label>Description<textarea name="description" maxlength="1500"></textarea></label><label>Source type<select id="source-kind" name="kind">${Object.keys(
      schemas,
    )
      .map(
        (k) =>
          `<option value="${esc(k)}">${esc(k === "local" ? "Local dataset" : k)}</option>`,
      )
      .join(
        "",
      )}</select></label><div id="source-config"></div><p id="source-capability" class="muted"></p>`;
  function fields() {
    const kind = $("source-kind").value;
    $("source-capability").textContent =
      kind === "local"
        ? "This creates an independent draft over a registered local dataset."
        : "Profile only. Source import is not available for this connector yet. Credential references name environment variables; do not enter credentials.";
    $("source-config").innerHTML =
      kind === "local"
        ? `<label>Dataset<select name="config.pack_id" required>${catalog.local_datasets.map((p) => `<option value="${esc(p.id)}">${esc(p.title)}</option>`).join("")}</select></label>`
        : Object.entries(schemas[kind].properties)
            .map(
              ([key, schema]) =>
                `<label>${esc(key.replaceAll("_", " "))}<input name="config.${esc(key)}" maxlength="${schema.maxLength || 1000}" ${(schemas[kind].required || []).includes(key) ? "required" : ""}></label>`,
            )
            .join("");
  }
  fields();
  $("source-kind").onchange = fields;
  const submit = $("setup-form").querySelector('[type="submit"]');
  submit.hidden = false;
  $("setup-form").onsubmit = async (e) => {
    e.preventDefault();
    submit.disabled = true;
    try {
      const values = Object.fromEntries(new FormData(e.target));
      const config = {};
      for (const [k, v] of Object.entries(values))
        if (k.startsWith("config.") && v.trim()) config[k.slice(7)] = v.trim();
      const record = await api("/demo/api/connections", {
        name: values.name.trim(),
        description: values.description.trim(),
        kind: values.kind,
        config,
      });
      $("setup").close();
      await load();
      navigate("overview", record.id);
    } catch (error) {
      $("setup-error").textContent = error.message;
    } finally {
      submit.disabled = false;
    }
  };
}
function renderProviders() {
  $("content").innerHTML =
    heading(
      "Builders & connections",
      "Choose where semantic models are authored. Each builder keeps its own workspace and permissions.",
      '<button id="add-provider" class="primary">Connect Helios</button>',
    ) +
    `<div class="provider-grid">${providers.map((p) => `<section class="panel"><div class="panel-head"><h2>${esc(p.name)}</h2>${tag(p.kind === "builtin" ? "Available" : "Links only", p.kind === "builtin")}</div><div class="panel-body"><p class="muted">${p.kind === "builtin" ? "Build, review, and query the local sample models." : "Open native Helios Studio and Talk. Release import and delegated queries are not enabled."}</p>${p.kind === "builtin" ? '<button class="primary" id="provider-builtin-create">New workspace</button>' : `<div class="detail-row"><span>Application origin</span><strong>${esc(p.ui_origin)}</strong></div>${anchor("Open builder", p.ui_origin)}<button class="primary" style="margin-top:16px;margin-left:12px" data-link-project="${esc(p.id)}">Link a workspace</button>`}</div></section>`).join("")}</div>`;
  $("add-provider").onclick = () => setup("provider");
  $("provider-builtin-create").onclick = () => newWorkspace();
  document
    .querySelectorAll("[data-link-project]")
    .forEach(
      (b) => (b.onclick = () => setup("project", b.dataset.linkProject)),
    );
}
function setup(kind, provider) {
  $("setup-form").querySelector('[type="submit"]').hidden = false;
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
    heading("Talk to your data", `${current.name} · Built-in workspace`) +
    (!versions.length
      ? empty(
          "Publish a model to start a conversation",
          "Questions use reviewed, published definitions. Open Studio to validate and publish a version.",
          anchor("Open Studio", editorUrl(current.id), true),
        )
      : `<div class="chat-shell chat-with-history"><section class="conversation-history" aria-label="Conversation history"><h2>Conversations</h2><p>This page session · Results stay in memory until you reload.</p><button id="clear-chat" class="quiet" type="button">New conversation</button><div id="conversation-list" class="conversation-history-list"></div></section><div class="chat-conversation"><div class="toolbar"><label for="chat-version">Published version</label><select id="chat-version">${versions.map((v) => `<option>${esc(v.version)}</option>`).join("")}</select></div><div id="chat-thread" class="chat-thread"></div><form id="chat-form" class="composer"><textarea id="question" placeholder="Ask a question about this published model…" aria-label="Question" maxlength="2000" required></textarea><div class="composer-foot"><span>Inspect the interpretation before running.</span><button id="ask" class="primary">Prepare answer →</button></div></form></div></div>`);
  if (!versions.length) return;
  if (
    versions.some((v) => String(v.version) === String(catalog.active_version))
  )
    $("chat-version").value = String(catalog.active_version);
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
  const history = window.HubChatHistory;
  const workspaceId = current.id;
  const historyKey = () =>
    history.key(workspaceId, selected().version, selected().context_sha256);
  function historyList() {
    const key = historyKey(),
      active = history.current(key);
    $("conversation-list").innerHTML =
      history
        .list(key)
        .map(
          (item) =>
            `<button type="button" data-conversation="${esc(item.id)}" aria-current="${item.id === active?.id}">${esc(item.title)}</button>`,
        )
        .join("") || "<p>No conversations for this published version yet.</p>";
    document.querySelectorAll("[data-conversation]").forEach((button) => {
      button.disabled = busy;
      button.onclick = () => {
        if (busy) return;
        history.open(key, button.dataset.conversation);
        reset();
      };
    });
  }
  function saveConversation(title) {
    // Archive rendered results and provenance, never an executable interpretation.
    const snapshot = $("chat-thread").cloneNode(true);
    snapshot
      .querySelectorAll("button,.chat-intro")
      .forEach((item) => item.remove());
    history.save(historyKey(), title, snapshot.innerHTML);
    historyList();
  }
  function invalidate() {
    plan = null;
    document.querySelectorAll("[data-run]").forEach((b) => b.remove());
  }
  function reset() {
    turn++;
    invalidate();
    $("question").value = "";
    const v = selected();
    const conversation = history.current(historyKey());
    historyList();
    if (conversation) {
      $("chat-thread").innerHTML = conversation.html;
      return;
    }
    $("chat-thread").innerHTML =
      `<div class="chat-intro"><h2>What would you like to explore?</h2><p class="muted">Use a saved metric or ask about your published data and evidence.</p><div class="suggestions">${v.metrics.map((m, i) => `<button type="button" data-suggest="${i}">${esc(m.name.replaceAll("_", " "))}</button>`).join("")}</div>${anchor("Configure the query model", "/v2/settings?source=" + encodeURIComponent(workspaceId))}</div>`;
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
      .querySelectorAll("[data-conversation]")
      .forEach((button) => (button.disabled = busy));
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
        saveConversation(original);
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
      saveConversation(original);
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
          saveConversation(original);
        } catch (e) {
          if (ticket === generation && n === turn) {
            answer.textContent = e.message;
            saveConversation(original);
          }
        } finally {
          if (ticket === generation) {
            busy = false;
            controls();
          }
        }
      };
    } catch (e) {
      if (ticket === generation && n === turn) {
        output.textContent = e.message;
        saveConversation(original);
      }
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
  $("clear-chat").onclick = () => {
    if (busy) return;
    history.start(historyKey());
    reset();
  };
  reset();
}
$("close-dialog").onclick = () => $("setup").close();
$("refresh").onclick = () => load().catch((e) => notice(e.message));
$("workspace").onchange = () => navigate(view);
document.querySelectorAll("[data-nav]").forEach(
  (a) =>
    (a.onclick = (e) => {
      const dest = {
        home: "home",
        workspace: "overview",
        chat: "chat",
        providers: "providers",
      }[a.dataset.nav];
      if (dest && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
        e.preventDefault();
        navigate(dest);
      }
    }),
);
window.addEventListener("popstate", () => {
  const params = new URL(location.href).searchParams;
  view = params.get("view") || "home";
  $("workspace").value = params.get("workspace") || workspaces[0]?.id || "";
  render();
});
const initial = new URL(location.href).searchParams.get("view");
if (
  titles[initial] ||
  ["studio", "tables", "sources", "review", "releases"].includes(initial)
)
  view = initial;
load().catch((e) => {
  notice(e.message);
  $("content").innerHTML = empty("Workspace catalog unavailable", e.message);
});
