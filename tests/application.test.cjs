const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("static/application.js", "utf8");

test("a title suggestion changes the field only after an explicit click", () => {
  let click;
  let focused = false;
  const events = [];
  const input = {
    value: "Choix manuel",
    focus: () => { focused = true; },
    dispatchEvent: (event) => events.push(event.type),
  };
  const button = {
    dataset: { jobTitle: 'Analyste GRC "H/F"' },
    addEventListener: (name, callback) => { assert.equal(name, "click"); click = callback; },
  };
  vm.runInNewContext(source, {
    Event,
    document: {
      querySelectorAll: () => [button],
      getElementById: () => input,
    },
  });
  assert.equal(input.value, "Choix manuel");
  click();
  assert.equal(input.value, 'Analyste GRC "H/F"');
  assert.equal(focused, true);
  assert.deepEqual(events, ["input"]);
});
