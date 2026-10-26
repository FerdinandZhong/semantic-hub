"use strict";
// Conversations live only in this document's memory. Reloading clears them.
window.HubChatHistory = (() => {
  const scopes = new Map();
  let sequence = 0;
  function state(key) {
    if (!scopes.has(key)) scopes.set(key, { active: null, items: [] });
    return scopes.get(key);
  }
  return {
    key: (workspace, version, hash) =>
      JSON.stringify([workspace, version, hash]),
    list: (key) => state(key).items.map(({ id, title }) => ({ id, title })),
    current(key) {
      const scope = state(key);
      return scope.items.find((item) => item.id === scope.active) || null;
    },
    open(key, id) {
      const scope = state(key);
      if (scope.items.some((item) => item.id === id)) scope.active = id;
      return this.current(key);
    },
    start(key) {
      state(key).active = null;
    },
    save(key, title, html) {
      const scope = state(key);
      let conversation = this.current(key);
      if (!conversation) {
        conversation = { id: String(++sequence), title, html };
        scope.items.unshift(conversation);
        scope.active = conversation.id;
      } else conversation.html = html;
      return conversation;
    },
  };
})();
