"use strict";
// The original editor owns dirty tracking, beforeunload, save, and API calls.
// Normalize older deep links before its asynchronous initial load completes.
window.HubEditorShell = {
  setSource(source) {
    for (const link of document.querySelectorAll(
      ".sidebar [data-nav], .overview-tab",
    )) {
      const url = new URL(link.href, location.href);
      if (
        ["workspace", "chat"].includes(link.dataset.nav) ||
        link.classList.contains("overview-tab")
      ) {
        url.searchParams.set("workspace", source);
      } else if (link.dataset.nav === "settings") {
        url.searchParams.set("source", source);
      }
      link.href = url.href;
    }
  },
};

// Keep generated source links in the same application shell.
document.addEventListener(
  "click",
  (event) => {
    const link = event.target.closest("a[href]");
    if (!link) return;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin) return;
    if (url.pathname === "/demo/context") url.pathname = "/v2/editor";
    if (url.pathname === "/demo/query") {
      url.pathname = "/v2";
      url.searchParams.set("view", "chat");
      url.searchParams.set("workspace", url.searchParams.get("source") || "");
      url.searchParams.delete("source");
    }
    link.href = url.href;
  },
  true,
);
