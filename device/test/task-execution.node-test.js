const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const root = path.resolve(__dirname, '..');

function runtime(t) {
  const actual = new Set([
    'core/task-executor.js', 'core/task-timeout.js', 'core/task-cancellation.js',
    'handlers/nurture.js', 'handlers/search-base.js', 'handlers/search-like.js',
  ].map(file => path.join(root, file)));
  const noOp = () => {};
  const ui = { findElement: () => null, waitForElement: () => true, swipeUp: noOp };
  const adapter = new Proxy({ ensureAppActive: () => true, safeClick: () => true }, {
    get: (object, key) => key in object ? object[key] : noOp,
  });
  const originalLoad = Module._load;
  const originals = Object.fromEntries(['sleep', 'setInterval', 'clearInterval', 'back', 'press', 'device'].map(key => [key, global[key]]));
  const originalNow = Date.now;
  let now = 0;
  let tick = noOp;
  function clearModules() {
    for (const filename of Object.keys(require.cache)) {
      if (filename.startsWith(root + path.sep)) delete require.cache[filename];
    }
  }
  clearModules();
  Module._load = function (request, parent, isMain) {
    const resolved = Module._resolveFilename(request, parent, isMain);
    if (resolved === path.join(root, 'core/ui-operator.js')) return ui;
    if (resolved.startsWith(root + path.sep) && !actual.has(resolved)) return adapter;
    return originalLoad.apply(this, arguments);
  };
  global.setInterval = callback => { tick = callback; return 1; };
  global.clearInterval = noOp;
  global.sleep = ms => { now += Number(ms || 0); };
  global.back = noOp;
  global.press = noOp;
  global.device = { width: 1080, height: 1920 };
  Date.now = () => now;
  t.after(() => {
    Module._load = originalLoad;
    Date.now = originalNow;
    for (const [key, value] of Object.entries(originals)) {
      if (value === undefined) delete global[key]; else global[key] = value;
    }
    clearModules();
  });
  // Keep real executor/handler modules and load executor first, as main.js does.
  const executor = require('../core/task-executor');
  const nurture = require('../handlers/nurture');
  nurture._ensureOnFeed = noOp;
  nurture._executeSubTask = () => true; // Android interaction boundary.
  const search = require('../handlers/search-base');
  for (const method of ['_openSearch', '_inputKeyword', '_clickSuggestion', '_clickVideoTab', '_clickSearchResult']) {
    search[method] = () => true;
  }
  const like = require('../handlers/search-like');
  like._interactWithVideo = () => true;
  return { executor, like, ui, advance: ms => { now += ms; }, tick: () => tick() };
}

test('main load order executes a nurture handler without partial circular exports', t => {
  const { executor } = runtime(t);
  const result = executor.execute({ id: 'nurture', type: 'nurture', params: {
    duration: 60, sub_tasks: [{ type: 'browse', count: 1 }],
  } });
  assert.equal(result.status, 'completed');
  assert.equal(result.result.browse.done, 1);
});

test('main load order executes a finite search handler', t => {
  const { executor } = runtime(t);
  const result = executor.execute({ id: 'search', type: 'search_like', params: { keyword: 'test', video_count: 1 } });
  assert.equal(result.status, 'completed');
  assert.equal(result.result.success_count, 1);
});

test('a 60-minute nurture can finish successfully after minute 31', t => {
  const { executor, advance, tick } = runtime(t);
  executor.registerHandler('nurture', { execute() {
    advance(31 * 60 * 1000);
    tick();
    return { success: true, result: { success_count: 1 } };
  } });
  assert.equal(executor.execute({ id: 'long', type: 'nurture', params: { duration: 60 } }).status, 'completed');
});

test('executor still rejects a task that exceeds its requested duration and grace', t => {
  const { executor, advance, tick } = runtime(t);
  executor.registerHandler('nurture', { execute() {
    advance(33 * 60 * 1000);
    tick();
    return { success: true, result: {} };
  } });
  assert.equal(executor.execute({ id: 'expired', type: 'nurture', params: { duration: 30 } }).status, 'failed');
});

test('full search processes videos until cancellation instead of completing with zero work', t => {
  const { executor, like } = runtime(t);
  let interactions = 0;
  like._interactWithVideo = () => {
    interactions++;
    if (interactions === 2) executor.cancel('full');
    return true;
  };
  const result = executor.execute({ id: 'full', type: 'search_like', params: { keyword: 'test', video_count: -1 } });
  assert.equal(interactions, 2);
  assert.equal(result.status, 'cancelled');
});

test('full search ends when the next video detail cannot be loaded', t => {
  const { executor, like, ui } = runtime(t);
  let interactions = 0;
  like._interactWithVideo = () => { interactions++; return true; };
  ui.waitForElement = () => interactions === 0;
  const result = executor.execute({ id: 'exhausted', type: 'search_like', params: { keyword: 'test', video_count: -1 } });
  assert.equal(result.status, 'completed');
  assert.equal(interactions, 1);
});

test('full search remains bounded when video navigation never reaches an end', t => {
  const { executor, like, advance } = runtime(t);
  let interactions = 0;
  like._interactWithVideo = () => { interactions++; advance(6 * 60 * 1000); return true; };
  const result = executor.execute({ id: 'bounded', type: 'search_like', params: { keyword: 'test', video_count: -1 } });
  assert.equal(interactions, 2);
  assert.equal(result.status, 'failed');
});
