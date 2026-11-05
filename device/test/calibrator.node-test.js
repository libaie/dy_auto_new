const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const geometry = require('../core/screen-context');

function harness(options = {}) {
  const captures = [], saves = [], recycled = [];
  const cache = {
    search_tab: { id: 'source', version: 3, platform_version: '38.6.0', resolution_profile: 'default', strategies: [{ type: 'text', value: '搜索' }, { type: 'coordinate', x_percent: 0.5, y_percent: 0.2 }] },
    sort_button: { strategies: [{ type: 'coordinate', x_percent: 0.9, y_percent: 0.1 }] },
    follow_button: { strategies: [{ type: 'text', value: '关注' }] },
  };
  const bounds = options.bounds || { left: 800, top: 200, right: 1000, bottom: 300 };
  const node = { bounds: () => bounds };
  let reads = 0;
  const ctx = geometry.create({ width: 1080, height: 2400, density: 3, captureWidth: options.captureWidth || 540, captureHeight: options.captureHeight || 1200 });
  const sandbox = {
    module: { exports: {} }, device: { width: 1080, height: 2400 },
    Date, Math, toast() {}, sleep() {},
    java: { io: { File: function () { return { exists: () => true, isDirectory: () => true }; } } },
    files: { readBytes: () => [1, 2, 3] },
    images: {
      captureScreen: () => ({ getWidth: () => ctx.captureWidth, getHeight: () => ctx.captureHeight, recycle: () => recycled.push('screen') }),
      clip: (img, x, y, width, height) => { captures.push({ x, y, width, height }); if (options.clipThrows) throw Error('clip failed'); return { recycle: () => recycled.push('template') }; },
      save: (img, filename) => saves.push(filename),
    },
    require(name) {
      if (name === './selector-loader') return { _cache: cache, _douyinVersion: '38.7.0' };
      if (name === './screen-context') return Object.assign({}, geometry, { read: () => { reads++; return options.layoutMoves && reads > 1 ? geometry.create({ width: 1080, height: 2400, contentBounds: { left: 0, top: 80, right: 1080, bottom: 2400 } }) : ctx; } });
      if (name === './ui-operator') return { _findManyByStrategy: () => options.ambiguous ? [node, node] : [node], _findByStrategy: () => null, _isOnScreen: () => true, detectPage: () => 'is_search_view' };
      if (name === './api-client') return { uploadCalibration: () => ({ uploaded: 1 }) };
      if (name === '../utils/logger') return { info() {}, warn() {}, error() {} };
      throw Error(name);
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../core/calibrator.js'), 'utf8'), sandbox);
  return { calibration: sandbox.module.exports, cache, captures, saves, recycled };
}

test('calibration excludes coordinate-only actions even on a matching page', () => {
  const h = harness();
  const targets = h.calibration._collectObservableActions('search');
  assert.deepEqual(Array.from(targets, t => t.action_name), ['search_tab']);
});

test('calibration crops the observed target through screenshot dimensions and records source provenance', () => {
  const h = harness();
  const result = h.calibration._captureTemplate({ action_name: 'search_tab', selector: h.cache.search_tab }, '1080x2400');
  assert.ok(result);
  assert.equal(result.source_selector_id, 'source');
  assert.equal(result.source_selector_version, 3);
  assert.equal(result.platform_version, '38.7.0');
  assert.equal(result.source_resolution, '540x1200');
  assert.equal(result.source_density, 1.5);
  assert.equal(h.captures.length, 1);
  const crop = h.captures[0];
  assert.ok(crop.x >= 395 && crop.x <= 400);
  assert.ok(crop.y >= 95 && crop.y <= 100);
  assert.ok(crop.width >= 100 && crop.width <= 110);
  assert.ok(crop.height >= 50 && crop.height <= 60);
  assert.deepEqual(h.recycled.sort(), ['screen', 'template']);
});

test('calibration refuses ambiguous targets and unverified capture transforms', () => {
  for (const opts of [{ ambiguous: true }, { captureWidth: 1200, captureHeight: 540 }, { layoutMoves: true }]) {
    const h = harness(opts);
    assert.equal(h.calibration._captureTemplate({ action_name: 'search_tab', selector: h.cache.search_tab }, '1080x2400'), null);
    assert.equal(h.saves.length, 0);
  }
});

test('calibration skips an oversized container instead of turning the entire page into an icon', () => {
  const h = harness({ bounds: { left: 0, top: 0, right: 1080, bottom: 2400 } });
  assert.equal(h.calibration._captureTemplate({ action_name: 'search_tab', selector: h.cache.search_tab }, '1080x2400'), null);
  assert.equal(h.saves.length, 0);
});

test('failed calibration crop recycles the screenshot once', () => {
  const h = harness({ clipThrows: true });
  assert.throws(() => h.calibration._captureTemplate({ action_name: 'search_tab', selector: h.cache.search_tab }, '1080x2400'), /clip failed/);
  assert.deepEqual(h.recycled, ['screen']);
});
