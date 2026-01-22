import test from "node:test";
import assert from "node:assert/strict";

import { applyUiNavigateIfPresent, findFirstNavigatePath } from "./uiActions.js";

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
