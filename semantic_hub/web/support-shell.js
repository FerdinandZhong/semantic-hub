"use strict";
(() => {
  const content = document.querySelector(".support-content");
  const edits = new Map();
  const workspaceName = document.getElementById("support-workspace-name");
  if (workspaceName) {
    fetch("/api/semantic-hub/v2/workspaces", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        const workspace = data?.items?.find(
          (item) => item.id === document.body.dataset.source,
        );
        if (workspace) workspaceName.textContent = workspace.name;
      })
      .catch(() => {}); // Keep the actual source ID if workspace metadata is unavailable.
  }
  function studioLinks() {
    for (const link of content.querySelectorAll("a[href]")) {
      const url = new URL(link.href, location.origin);
      if (url.origin === location.origin && url.pathname === "/demo/context") {
        url.pathname = "/v2/editor";
        link.href = url.pathname + url.search + url.hash;
      }
    }
  }
  new MutationObserver(studioLinks).observe(content, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["href"],
  });
  studioLinks();
  const value = (field) =>
    field.type === "checkbox" ? field.checked : field.value;
  // Capture the original value before a user changes a field.
  content.addEventListener("focusin", (event) => {
    const field = event.target;
    if (field.matches("input,textarea,select") && !edits.has(field))
      edits.set(field, value(field));
  });
  content.addEventListener("change", (event) => {
    const field = event.target;
    if (field.type === "file") edits.delete(field); // Upload starts immediately.
  });
  function unsaved() {
    for (const [field, previous] of edits) {
      if (!field.isConnected) {
        edits.delete(field);
        continue;
      }
      // Library filters and document navigation do not create unsaved content.
      const settings = document.body.dataset.supportPage === "llm";
      const review = field.matches(
        "textarea,[data-field],#visual-model-title,#visual-reviewer,#visual-review-note,#material-reviewer,#material-review-note",
      );
      if ((settings || review) && value(field) !== previous) return true;
    }
    return false;
  }
  window.addEventListener("beforeunload", (event) => {
    if (unsaved()) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
})();
