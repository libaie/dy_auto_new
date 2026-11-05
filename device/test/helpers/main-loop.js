const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Run main's actual startup/queue/config code; only Android, transport, and task
// execution boundaries are simulated. Callbacks can run during initialization.
module.exports = function mainLoop(options = {}) {
  const noOp = () => {};
  const threads = [];
  const executed = [];
  const reports = [];
  const cancelled = [];
  const intervals = new Map();
  const timeouts = new Map();
  const events = [];
  let timerId = 0;
  let now = 1000;
  let polls = 0;
  let closedApps = 0;
  let authFailure;
  let connected;
  let callbacks;
  let pairUI;
  let selectorsReady = false;
  let templatesReady = false;
  const config = { serverUrl: 'https://unit.invalid', deviceSecret: 'unit-secret', deviceId: 'unit-device',
    pollInterval: 30000, heartbeatInterval: 60000, ai: {}, decision: options.previousDecision || { enabled: false } };
  const api = {
    setAuthFailureHandler(fn) { authFailure = fn; },
    captureSession() { return {}; },
    register() {
      events.push('register');
      return options.register ? options.register() : { device_id: 'unit-device', config: {} };
    },
    poll() { polls++; return options.poll ? options.poll(polls) : null; },
    report(id, status, result, snapshot, lease) { reports.push({ id, status, lease }); return { ok: true }; },
    setProxy: noOp, heartbeat: noOp,
  };
  const pairing = {
    getSavedServerUrl() { return 'https://unit.invalid'; },
    getSavedSecret() { return 'unit-secret'; },
    request() { return options.pairResult; },
    waitForApproval() { return options.pairResult; },
    checkStatus() { return options.pairResult; },
    clear: noOp,
  };
  const state = {
    config, api, events, executed, reports, cancelled, intervals, timeouts,
    dispatch(task) { callbacks.onTask(task); },
    update(serverConfig, proxy) { callbacks.onConfigUpdated(serverConfig, proxy); },
    cancel(id) { callbacks.onCancelTask(id); },
    connect() { connected(); },
    authFail() { authFailure(); },
    remove() { callbacks.onDeviceRemoved(); },
    pair() { assert.equal(typeof pairUI, 'function'); pairUI('unit.invalid'); },
    run() { assert.ok(threads.length, 'an execution thread is pending'); threads.shift()(); },
    pending() { return threads.length; },
    polls() { return polls; },
    closedApps() { return closedApps; },
    advance(ms) { now += ms; },
    tick(ms = config.pollInterval) {
      const active = [...intervals.values()].filter(timer => timer.ms === ms);
      assert.ok(active.length, 'requested interval is active');
      active.forEach(timer => timer.fn());
    },
    timeout(ms) {
      const entry = [...timeouts.entries()].find(([, timer]) => timer.ms === ms);
      assert.ok(entry, 'requested timeout is active');
      timeouts.delete(entry[0]);
      entry[1].fn();
    },
  };
  const modules = {
    './config': config,
    './core/task-timeout': require('../../core/task-timeout'),
    './core/task-executor': options.executor || {
      execute(task) {
        executed.push({ ...task, decision: JSON.parse(JSON.stringify(config.decision)), selectorsReady, templatesReady });
        events.push('execute:' + task.id);
        return { status: 'completed', result: {} };
      },
      getCurrentTaskId() { return null; }, cancel(id) { cancelled.push(id); },
    },
    './core/api-client': api,
    './core/device-ws': {
      setAuthFailureHandler: noOp,
      setOnConnectedHandler(fn) { connected = fn; },
      start() { events.push('ws-start'); if (options.wsStart) options.wsStart(state); },
      setCallbacks(value) { callbacks = value; },
      stop: noOp,
    },
    './core/pairing': pairing,
    './core/selector-loader': {
      init() {
        if (options.duringSelectorInit) options.duringSelectorInit(state);
        selectorsReady = true;
      },
      checkAndUpdate: noOp,
    },
    './core/prompt-template-loader': {
      init() { templatesReady = true; }, checkAndUpdate: noOp,
    },
    './core/ui-operator': { closeApp() { closedApps++; } },
    './core/floating-window': { showPairingUI(fn) { pairUI = fn; }, showMainUI: noOp, showWaitingUI: noOp,
      updatePairStatus: noOp, setStatus: noOp },
  };
  const adapter = new Proxy({}, { get() { return noOp; } });
  const context = {
    require(name) { return modules[name] || adapter; },
    events: { on: noOp }, device: { model: 'unit', brand: 'unit' },
    Date: class extends Date { static now() { return now; } },
    threads: { start(fn) {
      if (options.immediateThreads) fn(); else threads.push(fn);
      return { interrupt: noOp };
    } },
    setInterval(fn, ms) { const id = ++timerId; intervals.set(id, { fn, ms }); return id; },
    clearInterval(id) { intervals.delete(id); },
    setTimeout(fn, ms) { const id = ++timerId; timeouts.set(id, { fn, ms }); return id; },
    clearTimeout(id) { timeouts.delete(id); },
    console,
  };
  context.global = context;
  const source = fs.readFileSync(path.join(__dirname, '../../main.js'), 'utf8');
  const end = source.indexOf('\n// 启动\n');
  assert.ok(end > 0, 'startup functions have a boundary before Android UI bootstrap');
  vm.runInNewContext(source.slice(0, end), context);
  state.context = context;
  state.start = initialConfig => context.startMainLoop('https://unit.invalid', 'unit-secret', initialConfig);
  if (options.autoStart !== false) state.start(options.initialConfig);
  return state;
};
