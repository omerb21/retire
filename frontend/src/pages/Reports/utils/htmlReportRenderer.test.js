import test from "node:test";
import assert from "node:assert/strict";

import { renderHtmlReport } from "./htmlReportRenderer.js";

test("renderHtmlReport does not call window.open in auto mode", () => {
  const calls = [];
  const openWindow = (...args) => {
    calls.push(args);
    return {};
  };

  const result = renderHtmlReport({ mode: "auto", htmlContent: "<html></html>", openWindow });
  assert.equal(result.opened, false);
  assert.equal(result.htmlContent, "<html></html>");
  assert.equal(calls.length, 0);
});
