const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("static/login-sync.js", "utf8");

async function setup(result, pathname = "/account") {
  const timers = [];
  let now = 0;
  let reloads = 0;
  const message = { textContent: "loading" };
  const classes = new Set();
  const banner = {
    hidden: false,
    dataset: { statusUrl: "/jobs/login-sync", dashboardUrl: "/", metricsUrl: "/dashboard" },
    querySelector: () => message,
    classList: {
      add: (name) => classes.add(name),
      remove: (name) => classes.delete(name),
    },
  };
  const context = {
    document: { getElementById: () => banner },
    Date: { now: () => now },
    AbortSignal,
    fetch: async () => {
      if (result instanceof Error) throw result;
      return { ok: true, status: 200, json: async () => result };
    },
    window: {
      setTimeout: (callback) => timers.push(callback),
      location: { pathname, reload: () => reloads++ },
    },
  };
  vm.runInNewContext(source, context);
  const flush = () => new Promise((resolve) => setImmediate(resolve));
  await flush();
  return {
    banner, message, classes, timers,
    reloads: () => reloads,
    tick: async (time) => {
      now = time;
      const callback = timers.shift();
      if (callback) await callback();
      await flush();
    },
  };
}

test("success hides loading and refreshes the dashboard once", async () => {
  const ui = await setup({ pending: false, failed: false }, "/");
  assert.equal(ui.banner.hidden, true);
  assert.equal(ui.reloads(), 1);
  assert.equal(ui.timers.length, 0);
});

test("success does not reload a form or account page", async () => {
  const ui = await setup({ pending: false, failed: false });
  assert.equal(ui.banner.hidden, true);
  assert.equal(ui.reloads(), 0);
});

test("success also refreshes the numeric dashboard once", async () => {
  const ui = await setup({ pending: false, failed: false }, "/dashboard");
  assert.equal(ui.banner.hidden, true);
  assert.equal(ui.reloads(), 1);
  assert.equal(ui.timers.length, 0);
});

test("failed jobs stop loading with a useful notice", async () => {
  const ui = await setup({ pending: false, failed: true });
  assert.equal(ui.banner.hidden, false);
  assert.equal(ui.classes.has("login-sync-idle"), true);
  assert.match(ui.message.textContent, /incomplète/);
  assert.equal(ui.timers.length, 0);
});

test("a stopped worker never leaves an infinite spinner", async () => {
  const ui = await setup({ pending: true, queued: true });
  await ui.tick(31000);
  assert.equal(ui.classes.has("login-sync-idle"), true);
  assert.match(ui.message.textContent, /en attente/);
  await ui.tick(121000);
  assert.equal(ui.timers.length, 0);
});

test("a slow running scan stops loading after the UI deadline", async () => {
  const ui = await setup({ pending: true, queued: false });
  await ui.tick(121000);
  assert.equal(ui.classes.has("login-sync-idle"), true);
  assert.equal(ui.timers.length, 0);
  assert.equal(ui.reloads(), 0);
});

test("waiting notice resumes progress when the worker starts", async () => {
  const status = { pending: true, queued: true };
  const ui = await setup(status);
  await ui.tick(31000);
  assert.equal(ui.classes.has("login-sync-idle"), true);
  status.queued = false;
  await ui.tick(33000);
  assert.equal(ui.classes.has("login-sync-idle"), false);
  assert.match(ui.message.textContent, /en cours/);
});

test("lost HTTP connectivity stops loading after three bounded attempts", async () => {
  const ui = await setup(new Error("offline"));
  await ui.tick(2000);
  await ui.tick(4000);
  assert.equal(ui.classes.has("login-sync-idle"), true);
  assert.equal(ui.timers.length, 0);
  assert.match(ui.message.textContent, /indisponible/);
});
