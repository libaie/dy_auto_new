const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Keep the executor, cancellation state, and all handlers real. Android and
// transport adapters are the only external boundaries; each test gets a VM.
module.exports = function taskRuntime() {
  const root = path.resolve(__dirname, '../..');
  const noOp = () => {};
  const cache = new Map();
  const storage = new Map();
  const calls = { clicks: [], inputs: [], stats: [], releases: [], shells: [] };
  let now = 1000;
  const timers = [];
  const state = { calls, onSleep: noOp, advance(ms) { now += ms; }, tick() { timers.forEach(fn => fn()); } };
  const bounds = { left: 20, top: 100, right: 700, bottom: 1500 };
  const screen = { width: 720, height: 1600, density: 2, contentBounds: bounds, blockedBounds: [], canInteract: true };
  const geometry = {
    read: () => screen,
    rect: b => b && ({ left: b.left, top: b.top, right: b.right, bottom: b.bottom }),
    contains: (b, x, y) => !!b && x >= b.left && x < b.right && y >= b.top && y < b.bottom,
    isUsablePoint: (p, ctx, region) => geometry.contains(region || ctx.contentBounds, p.x, p.y),
    dp: (n, ctx) => n * ctx.density,
  };
  const edit = { value: '', text() { return this.value; }, setText(value) { this.value = value; return true; },
    className: () => 'android.widget.EditText', bounds: () => bounds };
  const ui = {
    isAppActive: () => true, openApp: () => true, isOnPage: () => true,
    findElement: () => null, findElements: () => [], waitForElement: () => true, waitForPage: () => true,
    clickElement(node) { calls.clicks.push(node); return true; },
    clickAction(action) { calls.clicks.push(action); return true; },
    inputText(node, value) { calls.inputs.push(value); edit.value = value; return true; },
    submitViaKeyboard(action) { calls.clicks.push(action); return true; },
    swipeUp: noOp, captureUISnapshot: () => ({}),
  };
  const api = {
    beginTaskSession: () => ({}), isCurrentSession: () => true, endTaskSession: noOp,
    incrementStats(...args) { calls.stats.push(args); }, reportProgress: noOp,
    claimCommentReply: () => ({ claimed: true }),
    releaseCommentReply(...args) { calls.releases.push(args); },
    claimDMRecipient: () => ({ claimed: true, conversation_id: 'conversation' }),
    releaseDMRecipient(data) { calls.releases.push(data); }, reportDMSend: noOp,
    collectReport: () => ({}), saveCommentAIReply: noOp, saveUserProfile: noOp,
    uploadUserAvatar: noOp, get: () => [],
  };
  const analyzer = { useTemplate: noOp, resolveDestination: () => null, _localRelevanceCheck: () => true,
    SCORE_THRESHOLD: 40, analyzeComment: () => ({ score: 90, tier: 'low', reply: 'reply' }),
    generateVideoComment: () => 'comment', checkHealthRelevance: () => true, checkRelevance: () => true };
  const antiDetect = { wrapAction(action, fn) { return fn(); }, maybePause: noOp, humanSwipeUp: noOp };
  const modules = {
    'core/ui-operator.js': ui,
    'core/api-client.js': api,
    'core/ai-analyzer.js': analyzer,
    'core/anti-detect.js': antiDetect,
    'core/selector-loader.js': { get: () => null },
    'core/selector-resolver.js': {},
    'core/screen-context.js': geometry,
    'core/human-input.js': { typeFocusedText(value) { calls.inputs.push(value); edit.value = value; return true; } },
    'core/ocr-locator.js': {},
    'core/image-locator.js': {},
    'core/crash-recovery.js': { setAccountId: noOp, ensureAppRunning: noOp },
    'core/flow-context.js': { enter: noOp, reset: noOp },
    'utils/logger.js': { info: noOp, warn: noOp, error: noOp, debug: noOp },
  };
  const context = vm.createContext({
    console, global: {}, device: { width: 720, height: 1600, wakeUpIfNeeded: noOp },
    Date: class extends Date { static now() { return now; } },
    sleep(ms) { now += Number(ms || 0); state.onSleep(ms); },
    setInterval(fn) { timers.push(fn); return timers.length; }, clearInterval: noOp,
    back: noOp, press: () => true, gestures: () => true,
    input(value) { calls.inputs.push(value); edit.value += value; }, setClip: noOp,
    shell(command) { calls.shells.push(command); return { code: 0 }; },
    className() { return { focused() { return this; }, findOne: () => edit, find: () => [edit] }; },
    text() { return { find: () => [] }; },
    storages: { create() { return { get(key, fallback) { return storage.has(key) ? storage.get(key) : fallback; }, put(key, value) { storage.set(key, value); } }; } },
  });
  function load(relative) {
    const filename = path.resolve(root, relative.endsWith('.js') ? relative : relative + '.js');
    const key = path.relative(root, filename);
    if (Object.hasOwn(modules, key)) return modules[key];
    if (cache.has(filename)) return cache.get(filename).exports;
    const module = { exports: {} };
    cache.set(filename, module);
    const wrapper = vm.runInContext('(function(require, module, exports) {\n' + fs.readFileSync(filename, 'utf8') + '\n})', context, { filename });
    wrapper(name => load(path.relative(root, path.resolve(path.dirname(filename), name))), module, module.exports);
    return module.exports;
  }
  state.load = load;
  state.loadUI = function () { delete modules['core/ui-operator.js']; return load('core/ui-operator'); };
  state.geometry = geometry;
  state.ui = ui;
  state.api = api;
  state.analyzer = analyzer;
  state.antiDetect = antiDetect;
  state.edit = edit;
  state.context = context;
  state.executor = load('core/task-executor');
  state.cancellation = load('core/task-cancellation');
  const search = load('handlers/search-base');
  for (const method of ['_openSearch', '_inputKeyword', '_clickSuggestion', '_clickVideoTab', '_clickSearchResult']) search[method] = () => true;
  return state;
};
