const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

function mainLoop() {
  const noOp = () => {};
  const threads = [];
  const executed = [];
  let callbacks;
  const config = { serverUrl: 'https://unit.invalid', deviceSecret: 'unit-secret', deviceId: 'unit-device' };
  const modules = {
    './config': config,
    './core/task-timeout': require('../core/task-timeout'),
    './core/task-executor': {
      execute(task) { executed.push(task); return { status: 'completed', result: {} }; },
      getCurrentTaskId() { return null; }, cancel: noOp,
    },
    './core/api-client': {
      setAuthFailureHandler: noOp, register() { return null; }, poll() { return null; },
      report() { return { ok: true }; },
    },
    './core/device-ws': {
      setAuthFailureHandler: noOp, setOnConnectedHandler: noOp, start: noOp,
      setCallbacks(value) { callbacks = value; },
    },
    './core/pairing': {
      isConfigured() { return true; },
      getSavedServerUrl() { return config.serverUrl; },
      getSavedSecret() { return config.deviceSecret; },
    },
  };
  const adapter = new Proxy({}, { get() { return noOp; } });
  const context = {
    require(name) { return modules[name] || adapter; },
    events: { on: noOp }, device: { model: 'unit', brand: 'unit' },
    threads: { start(callback) { threads.push(callback); return { interrupt: noOp }; } },
    images: { requestScreenCapture() { return true; } },
    setInterval() { return 1; }, clearInterval: noOp,
    setTimeout() { return 1; }, clearTimeout: noOp,
    sleep() { throw new Error('Stop the Android keep-alive loop in this test'); },
    console: { error: noOp }, toast: noOp,
  };
  context.global = context;
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../main.js'), 'utf8'), context);
  threads.length = 0; // Ignore the Android screen-capture permission helper.
  assert.equal(typeof callbacks.onTask, 'function');
  return { executed, dispatch: task => callbacks.onTask(task), run: () => threads.shift()(), pending: () => threads.length };
}

test('main accepts a new retry lease after completing the same task ID', () => {
  const loop = mainLoop();
  loop.dispatch({ id: 'task', type: 'search_like', lease_id: 'attempt-one' });
  loop.run();
  loop.dispatch({ id: 'task', type: 'search_like', lease_id: 'attempt-two' });
  assert.equal(loop.pending(), 1);
  loop.run();
  assert.deepEqual(loop.executed.map(task => task.lease_id), ['attempt-one', 'attempt-two']);
});

test('main rejects completed-attempt replays and concurrent leases for one task', () => {
  const loop = mainLoop();
  const first = { id: 'task', type: 'search_like', lease_id: 'attempt-one' };
  loop.dispatch(first);
  loop.dispatch({ ...first, lease_id: 'attempt-two' });
  assert.equal(loop.pending(), 1);
  loop.run();
  loop.dispatch(first);
  assert.equal(loop.pending(), 0);
  assert.equal(loop.executed.length, 1);
});

test('main still deduplicates replayed legacy tasks without a lease', () => {
  const loop = mainLoop();
  const task = { id: 'legacy', type: 'search_like' };
  loop.dispatch(task);
  loop.run();
  loop.dispatch(task);
  assert.equal(loop.pending(), 0);
  assert.equal(loop.executed.length, 1);
});
