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
  // Match the workflow pages: "Workspace / <workspace> / Overview".
  $("breadcrumb").textContent =
    view === "overview" && current ? `${current.name} / Overview` : titles[view] || "Semantic workspace";
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
  submit.disabled = false;
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
let pickerGeneration = 0;
function linkWorkspace(providerId) {
  const dialog = $("setup"), form = $("setup-form");
  if (dialog.open) return;
  const token = ++pickerGeneration;
  let request = 0, saving = false;
  const provider = providers.find((item) => item.id === providerId);
  $("setup-title").textContent = "Link a Helios workspace";
  $("setup-error").textContent = "";
  $("setup-fields").innerHTML = `<label>Workspace name<input name="name" required maxlength="120" placeholder="Finance analytics"></label><label>CAI API key (optional)<input id="helios-key" type="password" autocomplete="off"></label><p class="muted">The Hub sends this key to ${esc(provider?.api_origin || "the configured Helios API")}. The key stays in this dialog until it closes.</p><button type="button" id="helios-retry">Load organizations</button><label>Organization<select name="organization_id" id="helios-org" required disabled></select></label><label>Model<select name="model_id" id="helios-model" required disabled></select></label><p id="helios-status" role="status"></p>${anchor("Open Helios", provider?.ui_origin)}`;
  const submit = form.querySelector('[type="submit"]');
  submit.hidden = false;
  submit.disabled = true;
  const org = $("helios-org"), model = $("helios-model"), key = $("helios-key");
  const active = () => token === pickerGeneration && dialog.open;
  const clearModels = () => { model.innerHTML = ""; model.disabled = true; submit.disabled = true; };
  const options = (select, items, placeholder) => {
    select.innerHTML = `<option value="">${placeholder}</option>` + items.map((item) => `<option value="${esc(item.id)}">${esc(item.name || item.id)}</option>`).join("");
    select.disabled = !items.length;
  };
  const call = async (path, body) => {
    const response = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json", ...(key.value ? {"X-Helios-API-Key": key.value} : {})}, body: JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) throw Error(response.status === 401 ? "Access requires a valid CAI API key. Enter the key and retry." : typeof data.detail === "string" ? data.detail : "Helios is unavailable. Retry the request.");
    return data;
  };
  const discover = async (organizationId) => {
    const version = ++request;
    clearModels();
    if (!organizationId) { org.innerHTML = ""; org.disabled = true; }
    $("helios-status").textContent = organizationId ? "Loading models…" : "Loading organizations…";
    $("setup-error").textContent = "";
    try {
      const data = await call(`/api/semantic-hub/v2/providers/${encodeURIComponent(providerId)}/discover`, organizationId ? {organization_id: organizationId} : {});
      if (!active() || version !== request) return;
      const items = organizationId ? data.models || [] : data.organizations || [];
      options(organizationId ? model : org, items, organizationId ? "Select a model" : "Select an organization");
      $("helios-status").textContent = items.length ? "" : organizationId ? "No accessible models. Ask your Helios administrator to create a model or grant access, then retry." : "No accessible organizations. Check your Helios access, then retry.";
    } catch (error) {
      if (active() && version === request) { $("setup-error").textContent = error.message; $("helios-status").textContent = "Request failed. Retry when ready."; }
    }
  };
  org.onchange = () => { clearModels(); ++request; if (org.value) discover(org.value); };
  model.onchange = () => { submit.disabled = saving || !org.value || !model.value; };
  key.oninput = () => { ++request; org.innerHTML = ""; org.disabled = true; clearModels(); $("helios-status").textContent = "Load organizations with this credential."; };
  $("helios-retry").onclick = () => discover(org.value);
  form.onsubmit = async (event) => {
    event.preventDefault();
    if (saving || !org.value || !model.value) return;
    saving = true; submit.disabled = true;
    try {
      const linked = await call("/api/semantic-hub/v2/projects", {provider_id: providerId, name: form.elements.name.value, organization_id: org.value, model_id: model.value});
      if (!active()) return;
      dialog.close();
      await load();
      navigate("home", linked.id);
      notice(`Workspace linked as “${linked.name}”. Existing model links keep their original name.`);
      document.querySelector(`[data-open-workspace="${CSS.escape(linked.id)}"]`)?.closest(".workspace-card")?.scrollIntoView({block: "nearest"});
    } catch (error) { if (active()) $("setup-error").textContent = error.message; }
    finally { saving = false; if (active()) submit.disabled = !org.value || !model.value; }
  };
  dialog.addEventListener("close", () => { if (token === pickerGeneration) ++pickerGeneration; ++request; key.value = ""; org.innerHTML = ""; model.innerHTML = ""; }, {once: true});
  dialog.showModal();
  discover();
}
function setup(kind, provider) {
  if (kind === "project") return linkWorkspace(provider);
  $("setup-form").querySelector('[type="submit"]').hidden = false;
  $("setup-form").querySelector('[type="submit"]').disabled = false;
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
      : [];
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
  const workspaceId = current.id;
  const resultScope = current.model?.synthetic ? "Synthetic sample" : "Local source snapshot";
  $("content").innerHTML = heading("Talk to your data", "Ask a question. Follow the checks. Explore the answer and its sources.") +
    (!versions.length ? empty("Publish a model to start a conversation", "Publish reviewed definitions and document evidence in Studio first.", anchor("Open Studio", editorUrl(current.id), true)) :
    `<div class="chat-shell chat-with-history"><section class="conversation-history" aria-label="Conversation history"><h2>Conversations</h2><button id="clear-chat" class="quiet" type="button">＋ New conversation</button><div id="conversation-list" class="conversation-history-list"></div><p class="history-note">This page session · Cleared when you reload.</p></section><div class="chat-conversation"><div class="chat-toolbar"><span class="chat-source"><i></i>${esc(current.name)}</span><label>Published version <select id="chat-version">${versions.map(v => `<option>${esc(v.version)}</option>`).join("")}</select></label></div><div id="chat-thread" class="chat-thread" aria-label="Conversation"></div><form id="chat-form" class="composer"><textarea id="question" placeholder="Ask about your data or published documents…" aria-label="Question" maxlength="2000" required rows="2"></textarea><div class="composer-foot"><span>Read-only queries · Published definitions and evidence</span><button id="ask" class="primary">Ask &amp; run ↑</button></div></form></div></div>`);
  if (!versions.length) return;
  if (versions.some(v => String(v.version) === String(catalog.active_version))) $("chat-version").value = String(catalog.active_version);
  const binding = {pack_id: config.pack_id, snapshot_sha256: config.snapshot_sha256, session_id: config.session_id};
  const endpoint = built("/demo/api/playground/chat");
  const history = window.HubChatHistory;
  let busy = false, turn = 0, suggestion = null;
  const selected = () => versions.find(v => v.version === $("chat-version").value);
  const historyKey = () => history.key(workspaceId, selected().version, selected().context_sha256);
  const fresh = n => ticket === generation && n === turn;
  const make = (tag, text, cls) => {const e = document.createElement(tag); if (text != null) e.textContent = text; if (cls) e.className = cls; return e;};
  function historyList() {
    const active = history.current(historyKey());
    $("conversation-list").innerHTML = history.list(historyKey()).map(item => `<button type="button" data-conversation="${esc(item.id)}" aria-current="${item.id === active?.id}">${esc(item.title)}</button>`).join("") || '<p>Your questions will appear here.</p>';
    document.querySelectorAll("[data-conversation]").forEach(b => {b.disabled = busy; b.onclick = () => {if (!busy) {history.open(historyKey(), b.dataset.conversation); reset();}};});
  }
  function save(title) {history.save(historyKey(), title, $("chat-thread").innerHTML); historyList();}
  function controls() {
    for (const id of ["ask", "chat-version", "clear-chat", "question"]) $(id).disabled = busy;
    document.querySelectorAll("[data-suggest],[data-conversation]").forEach(b => b.disabled = busy);
    $("ask").textContent = busy ? "Working…" : "Ask & run ↑";
  }
  function starters(v) {
    const items = v.metrics.map(m => ({metric: m.name, text: m.name === 'total_amount_sgd'
      ? 'What is the total settled sender outflow in SGD for the sample?'
      : `What is the value of ${m.name.replaceAll('_', ' ')} for this sample?`, label: 'Published metric'}));
    for (const m of v.metrics) for (const q of m.example_questions || []) {
      if (q && !items.some(i => i.text === q)) items.push({text: q, label: 'Ask a question'});
    }
    if (v.metrics.some(m => m.name === 'total_amount_sgd')) items.push({text: 'Show total settled sender outflow in SGD by sender jurisdiction.', label: 'Explore the data'});
    if (v.evidence_passages) items.push({text: (v.document_titles || []).some(t => /mas.*sg.?qr|sg.?qr.*mas/i.test(t)) ? 'According to the attached MAS announcement, how does SG QR support PayNow transfers?' : 'What do the published documents explain about this dataset?', label: 'Explore document evidence'});
    return items.slice(0, 4);
  }
  function reset() {
    turn++; suggestion = null; $("question").value = ""; historyList();
    const item = history.current(historyKey());
    if (item) {$("chat-thread").innerHTML = item.html; $("chat-thread").querySelectorAll('.answer-canvas:not([hidden] *)').forEach(mountCanvas); return;}
    const examples = starters(selected());
    $("chat-thread").innerHTML = `<div class="chat-intro"><div class="chat-intro-icon">✧</div><h2>What would you like to know?</h2><p>Get answers from your data, with reviewed definitions<br>and citations from published documents.</p><div class="suggestions">${examples.map((s, i) => `<button type="button" data-suggest="${i}"><span>${esc(s.label)}</span>${esc(s.text)}<b aria-hidden="true">↗</b></button>`).join('')}</div><p class="chat-intro-foot">${esc(resultScope)} · ${selected().metrics.length} published metric${selected().metrics.length === 1 ? '' : 's'} · ${selected().evidence_passages || 0} document passages</p></div>`;
    document.querySelectorAll('[data-suggest]').forEach(b => b.onclick = () => {suggestion = examples[Number(b.dataset.suggest)]; $("question").value = suggestion.text; $("question").focus();});
  }
  function retrieval(box, data) {
    box.replaceChildren();
    const title = make('div', null, 'retrieval-heading');
    title.append(make('strong', 'Semantic retrieval'), make('span', data.method, 'tag'));
    box.append(title);
    if (data.matches?.length) {
      const list = make('div', null, 'retrieval-matches');
      for (const match of data.matches.slice(0, 4)) {
        const row = make('div', null, 'retrieval-match');
        const score = typeof match.score === 'number' && Number.isFinite(match.score)
          ? (match.query_terms != null ? `${match.score} / ${match.query_terms} terms` : match.score.toFixed(3)) : 'Not scored';
        row.append(make('span', match.name + (match.location ? ' · ' + match.location : '')), make('strong', score)); list.append(row);
      }
      box.append(list);
    } else box.append(make('p', data.method === 'Saved metric selection' ? 'Exact published metric selected' : 'No lexical match score is available for this question.'));
    box.append(make('p', data.note, 'retrieval-note'));
    box.hidden = false;
  }
  function renderAnswer(box, result, version) {
    box.replaceChildren();
    const blocked = ['needs_clarification', 'unavailable', 'insufficient_evidence', 'conflicting_evidence', 'no_data'].includes(result.status);
    if (blocked) box.append(make('p', result.message || 'No verified answer is available for this question.', 'answer-summary'));
    const tabs = [];
    if (result.columns && !blocked) {
      const single = result.rows?.length === 1 && result.columns.length === 1 && result.rows[0][0] != null;
      const table = make('div');
      if (single) {
        const value = result.rows[0][0], number = Number(value);
        const display = Number.isFinite(number) ? new Intl.NumberFormat('en-SG', {maximumFractionDigits: 8}).format(number) : String(value);
        box.append(make('p', result.metric?.description || 'Query result', 'answer-label'));
        box.append(make('div', `${result.unit || ''} ${display}`.trim(), 'answer-value'));
        box.append(make('p', 'Calculated from the selected source snapshot using the published metric.', 'answer-summary'));
        table.innerHTML = rowsTable(result.columns, [[display]]);
      } else {
        box.append(make('p', `${result.rows?.length || 0} rows returned${result.truncated ? ' (display limit reached)' : ''}.`, 'answer-summary'));
        table.innerHTML = rowsTable(result.columns, result.rows || []);
      }
      if (result.rows?.length) tabs.push(['Table', [table]]);
    }
    for (const claim of result.claims || []) {
      box.append(make('p', claim.text, 'answer-summary'));
      for (const citation of claim.citations || []) {
        const source = make('details', null, 'citation-card');
        source.append(make('summary', `${citation.title || citation.id || 'Published evidence'}${citation.location ? ' · ' + citation.location : ''}`));
        source.append(make('blockquote', citation.quote || ''));
        box.append(source);
      }
    }
    if (!blocked && !result.columns && !result.claims?.length) box.append(make('p', result.message || 'No supported answer was returned. Try a more specific question.'));
    const meta = make('div', null, 'answer-meta');
    meta.append(make('span', `${result.context_version || version.version} · ${resultScope}`));
    if (result.context_sha256) meta.append(make('span', `Context ${result.context_sha256.slice(0, 12)}`));
    box.append(meta);
    if (result.semantic_canvas) {
      const canvas = make('div', null, 'answer-canvas'); canvas.dataset.canvas = JSON.stringify(result.semantic_canvas);
      tabs.push(['Semantic canvas', [canvas]]);
    }
    const checks = [];
    let checkLabel = 'SQL & checks';
    if (result.evaluation?.summary.total) {
      const {passed, total} = result.evaluation.summary;
      checkLabel = `SQL & checks · ${passed}/${total} passed`;
      const evaluation = make('div', null, 'answer-checks');
      for (const [title, items] of [['Retrieval', result.evaluation.retrieval], ['Generation', result.evaluation.generation]]) {
        if (!items.length) continue;
        evaluation.append(make('h4', title)); const list = make('ul', null, 'check-list');
        for (const c of items) {
          const row = make('li'); row.dataset.status = c.status;
          row.append(make('span', {pass: '✓', fail: '✕', warn: '⚠', 'n/a': '–'}[c.status], 'check-mark'), make('strong', c.name), make('span', c.detail, 'check-detail'));
          list.append(row);
        }
        evaluation.append(list);
      }
      evaluation.append(make('p', 'Deterministic checks on this answer. Relevance signals rank matches; they are not calibrated confidence.', 'retrieval-note'));
      checks.push(evaluation);
    }
    if (result.sql) {
      checks.push(make('pre', result.sql));
      if (result.request) checks.push(make('pre', JSON.stringify(result.request, null, 2)));
    }
    if (checks.length) tabs.push([checkLabel, checks]);
    tabs.push(['Provenance', [make('pre', JSON.stringify(result, null, 2))]]);
    const strip = make('div', null, 'answer-tabs'); strip.setAttribute('role', 'tablist'); strip.setAttribute('aria-label', 'Answer details');
    const panels = make('div', null, 'answer-tab-panels');
    const uid = 'at' + (++answerSeq);
    tabs.forEach(([label, nodes], i) => {
      const tab = make('button', label, 'answer-tab'); tab.type = 'button';
      tab.id = `${uid}-t${i}`; tab.setAttribute('role', 'tab'); tab.setAttribute('aria-selected', 'false'); tab.setAttribute('aria-controls', `${uid}-p${i}`); tab.tabIndex = i ? -1 : 0;
      const panel = make('div', null, 'answer-tab-panel'); panel.id = `${uid}-p${i}`; panel.setAttribute('role', 'tabpanel'); panel.setAttribute('aria-labelledby', tab.id); panel.hidden = true;
      panel.append(...nodes); strip.append(tab); panels.append(panel);
    });
    box.append(strip, panels);
  }
  let answerSeq = 0;
  // Delegated, so tabs keep working after a history restore replaces the thread HTML.
  function selectTab(tab, open) {
    const strip = tab.parentElement;
    for (const t of strip.children) {
      const on = open && t === tab;
      t.setAttribute('aria-selected', on); t.tabIndex = on || (!open && t === tab) ? 0 : -1;
      const panel = document.getElementById(t.getAttribute('aria-controls')); panel.hidden = !on;
      if (on) mountCanvas(panel.querySelector('.answer-canvas'));
    }
  }
  $("chat-thread").addEventListener('click', e => {
    const tab = e.target.closest?.('.answer-tab');
    if (tab) selectTab(tab, tab.getAttribute('aria-selected') !== 'true');
  });
  $("chat-thread").addEventListener('keydown', e => {
    const tab = e.target.closest?.('.answer-tab'), step = {ArrowRight: 1, ArrowLeft: -1}[e.key];
    if (!tab || (!step && e.key !== 'Home' && e.key !== 'End')) return;
    const all = [...tab.parentElement.children];
    const next = all[e.key === 'Home' ? 0 : e.key === 'End' ? all.length - 1 : (all.indexOf(tab) + step + all.length) % all.length];
    e.preventDefault(); next.focus();
    selectTab(next, tab.getAttribute('aria-selected') === 'true');
  });
  function agentTrace(box, agent) {
    const stops = {receipt: 'Stopped on a checked plan receipt', single_receipt_fallback: 'Stopped with one checked receipt',
      no_receipt: 'Stopped without a checked plan', budget_exhausted: 'Stopped at the tool budget', sdk_error: 'Agent runtime error'};
    const head = make('p', `Agent tool calls · ${agent.tool_calls ?? agent.trace.length}/${agent.tool_budget} budget · ${stops[agent.stop_reason] || 'Stop reason not recorded'}`, 'trace-heading');
    const list = make('ol', null, 'agent-trace');
    for (const step of agent.trace || []) {
      const row = make('li'); row.dataset.status = step.status === 'rejected' ? 'fail' : 'pass';
      row.append(make('strong', step.tool.replaceAll('_', ' ')), make('span', [step.status, step.metric, step.failure_type === 'duplicate_call' ? 'duplicate call' : step.message].filter(Boolean).join(' · '), 'check-detail'));
      list.append(row);
    }
    box.append(head, list);
  }
  async function ask() {
    const original = $("question").value.trim(); if (busy || !original) return;
    const shortcut = suggestion?.text === original ? suggestion.metric : null;
    suggestion = null; const n = ++turn, v = selected(); busy = true; controls();
    $("chat-thread").querySelector('.chat-intro')?.remove();
    $("chat-thread").append(make('div', original, 'bubble user'));
    $("question").value = '';
    const output = make('article', null, 'chat-answer');
    const progress = make('details', null, 'answer-progress'); progress.open = true;
    const summary = make('summary', 'Working on your question'); progress.append(summary);
    const flow = make('ol', null, 'chat-flow');
    const steps = ['retrieve', 'check', 'execute', 'answer'];
    const labels = ['Find context', 'Check scope', 'Read data', 'Answer'];
    steps.forEach((s, i) => {const row = make('li', labels[i]); row.dataset.stage = s; row.dataset.state = 'waiting'; flow.append(row);});
    const action = make('p', 'Starting…', 'progress-action'); action.setAttribute('role', 'status');
    progress.append(flow, action); const evidence = make('div', null, 'retrieval-panel'); evidence.hidden = true;
    const answer = make('div', null, 'answer-body');
    output.append(progress, evidence, answer); $("chat-thread").append(output); output.scrollIntoView({block: 'nearest'});
    let stage = -1, received = false;
    function update(s, detail) {
      stage = Math.max(stage, steps.indexOf(s));
      flow.querySelectorAll('li').forEach((li, i) => li.dataset.state = i < stage ? 'done' : i === stage ? 'running' : 'waiting');
      action.textContent = detail;
    }
    const controller = new AbortController();
    // Bound network waiting, including a proxy that buffers the response.
    const timeout = setTimeout(() => controller.abort(), 250000);
    let reader;
    try {
      const response = await fetch(endpoint, {method: 'POST', headers: {'Content-Type': 'application/json'}, signal: controller.signal,
        body: JSON.stringify({...binding, version: v.version, context_sha256: v.context_sha256, question: original, metric: shortcut || null, mode: shortcut ? 'metric' : 'auto'})});
      if (!response.ok) {const data = await response.json(); throw Error(typeof data.detail === 'string' ? data.detail : 'The chat request was rejected. Reload and retry.');}
      if (!(response.headers.get('content-type') || '').includes('application/x-ndjson')) throw Error('The service returned an unexpected response. Check application access.');
      reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
      const handle = event => {
        if (event.type === 'error') throw Error(event.message);
        if (event.type === 'progress') update(event.stage, event.detail);
        if (event.type === 'retrieval') retrieval(evidence, event.detail);
        if (event.type === 'result') {
          if (received) throw Error('A duplicate answer was received.'); received = true;
          renderAnswer(answer, event.result, v);
          if (event.result.agent) agentTrace(progress, event.result.agent);
          const success = (!event.result.status || event.result.status === 'answered') && (event.result.columns || event.result.claims?.length);
          flow.querySelectorAll('li').forEach((li, i) => li.dataset.state = success ? 'done' : i < stage ? 'done' : i === stage ? 'attention' : 'waiting');
          summary.textContent = success ? 'Completed · View execution flow' : 'Request needs attention · View checks';
          action.textContent = success ? 'Answer ready. Inspect the result and its sources below.' : 'No complete answer was issued for this request.';
          progress.open = !success;
        }
      };
      while (true) {
        const {value, done} = await reader.read();
        if (!fresh(n)) {controller.abort(); return;}
        buffer += decoder.decode(value || new Uint8Array(), {stream: !done});
        const lines = buffer.split('\n'); buffer = lines.pop();
        for (const line of lines) if (line.trim()) handle(JSON.parse(line));
        if (done) {if (buffer.trim()) handle(JSON.parse(buffer)); break;}
      }
      if (!received) throw Error('The connection ended before an answer arrived. Please retry.');
    } catch (error) {
      controller.abort();
      if (fresh(n)) {
        summary.textContent = 'Request interrupted'; progress.open = true;
        flow.querySelector('[data-state="running"]')?.setAttribute('data-state', 'attention');
        action.textContent = 'No complete answer was returned.';
        answer.replaceChildren(make('p', error.name === 'AbortError' ? 'The request timed out. Please retry.' : error.message, 'chat-error'));
      }
    } finally {
      clearTimeout(timeout); reader?.releaseLock();
      if (fresh(n)) {busy = false; controls(); save(original); output.scrollIntoView({block: 'nearest'});}
    }
  }
  // Mount on first open. Restored history HTML carries only the payload, so stale SVG is replaced.
  const mounted = new WeakSet();
  function mountCanvas(box) {
    if (!box || mounted.has(box) || !window.HeliosCanvas) return;
    mounted.add(box);
    const data = JSON.parse(box.dataset.canvas), host = make('div', null, 'answer-canvas-host'), detail = make('p', 'Select an object to inspect it.', 'answer-canvas-detail');
    box.replaceChildren(host, detail);
    const handle = window.HeliosCanvas.mount(host, {readOnly: true, host: {getState: () => ({definition: data.definition})},
      onSelect: o => {detail.textContent = [o.kind || o.type, o.label || o.name || o.id, o.description || o.expression || o.location || ''].filter(Boolean).join(' · ');}});
    handle.update({...data.graph, saved_revision: data.graph.draft_revision, dirty: false});
  }
  $("chat-form").onsubmit = e => {e.preventDefault(); ask();};
  $("question").oninput = () => {if (suggestion?.text !== $("question").value) suggestion = null;};
  $("question").onkeydown = e => {if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {e.preventDefault(); $("chat-form").requestSubmit();}};
  $("chat-version").onchange = reset;
  $("clear-chat").onclick = () => {if (!busy) {history.start(historyKey()); reset();}};
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
