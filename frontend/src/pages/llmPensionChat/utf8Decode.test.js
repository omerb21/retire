import test from "node:test";
import assert from "node:assert/strict";

test("utf-8 decoding keeps Hebrew approval reason (no gibberish)", () => {
  const payload = {
    type: "ui_actions",
    actions: [
      {
        type: "approval_request",
        tool_name: "TRANSFORM_FUNDS_TO_ASSETS",
        reason: "נדרש אישור לפני הפעלת כלי: פעולה מסוכנת",
        arguments: { some: "value" },
      },
    ],
  };

  const json = JSON.stringify(payload);
  const bytes = new TextEncoder().encode(json);
  const decoded = new TextDecoder("utf-8").decode(bytes);

  const parsed = JSON.parse(decoded);
  const reason = parsed?.actions?.[0]?.reason;

  assert.equal(reason, "נדרש אישור לפני הפעלת כלי: פעולה מסוכנת");
  assert.ok(!String(reason).includes("×"));
});
