import test from "node:test";
import assert from "node:assert/strict";

import { applyUiNavigateIfPresent, findFirstNavigatePath } from "./uiActions.js";
import { buildOpenUrl, openUrlOnce } from "./openUrl.js";

test("ui_actions navigate uses action.path exactly", () => {
  const payload = {
    type: "ui_actions",
    actions: [{ type: "navigate", path: "/clients/36/reports?auto_html=1", label: "פתח דוח" }],
  };

  assert.equal(findFirstNavigatePath(payload), "/clients/36/reports?auto_html=1");

  let navigatedTo = null;
  const didNavigate = applyUiNavigateIfPresent(payload, (path) => {
    navigatedTo = path;
  });

  assert.equal(didNavigate, true);
  assert.equal(navigatedTo, "/clients/36/reports?auto_html=1");
});

test("buildOpenUrl uses hash routing when window.hash starts with #/", () => {
  const url = "/clients/39/reports?auto_html=1";
  const origin = "https://example.com";
  const hash = "#/clients/1";
  assert.equal(buildOpenUrl(url, origin, hash), "https://example.com/#/clients/39/reports?auto_html=1");
});

test("buildOpenUrl uses browser routing when window.hash is empty", () => {
  const url = "/clients/39/reports?auto_html=1";
  const origin = "https://example.com";
  const hash = "";
  assert.equal(buildOpenUrl(url, origin, hash), "https://example.com/clients/39/reports?auto_html=1");
});

test("openUrlOnce opens only once when invoked twice quickly with same open_url", () => {
  const calls = [];
  const win = {
    open: (...args) => {
      calls.push(args);
    },
  };

  const lastOpenAtRef = { current: 0 };
  const lastOpenUrlRef = { current: null };

  const payload = {
    url: "/clients/39/reports?auto_html=1",
    origin: "https://example.com",
    hash: "#/clients/1",
    win,
    lastOpenAtRef,
    lastOpenUrlRef,
    ttlMs: 2500,
  };

  const r1 = openUrlOnce(payload);
  const r2 = openUrlOnce(payload);

  assert.equal(r1.opened, true);
  assert.equal(r2.opened, false);
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], "https://example.com/#/clients/39/reports?auto_html=1");
});
