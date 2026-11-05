const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const geometry = require('../core/screen-context');

function selector(profile, value, version) {
  return { action_name: 'button', resolution_profile: profile, platform_version: version || 'default', strategies: [{ type: 'text', value }] };
}

function loader(initial) {
  let width = 1080, height = 2400, now = 1000;
  const requests = [];
  let response = null;
  const api = { fetchSelectors(version, resolution) { requests.push({ version, resolution }); return response; } };
  const sandbox = {
    module: { exports: {} }, global: {}, device: { width: 1080, height: 2400 },
    Date: { now: () => now },
    context: { getPackageManager: () => ({ getPackageInfo: () => ({ versionName: '38.6.0' }) }) },
    files: { exists: filename => filename.endsWith('/ready.png') },
    require(name) {
      if (name === './api-client') return api;
      if (name === './screen-context') return { read: () => geometry.create({ width, height }) };
      if (name === '../utils/logger') return { info() {}, warn() {}, error() {}, debug() {} };
      throw Error(name);
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../core/selector-loader.js'), 'utf8'), sandbox);
  const instance = sandbox.module.exports;
  instance.syncTemplates = () => {};
  instance._applySelectors(initial);
  instance._initialized = true;
  return { instance, requests, setSize(w, h) { width = w; height = h; }, setResponse(value) { response = value; }, advance(ms) { now += ms; } };
}

test('geometry changes request a fresh resolution-specific selector snapshot even without revision change', () => {
  const h = loader([selector('1080x2400', 'portrait'), selector('default', 'fallback')]);
  assert.equal(h.instance.get('button').strategies[0].value, 'portrait');
  h.setSize(2400, 1080);
  h.setResponse({ version: 1, changed: true, selectors: [selector('2400x1080', 'landscape'), selector('default', 'fallback')] });
  assert.equal(h.instance.get('button').strategies[0].value, 'landscape');
  assert.equal(h.instance._resolution, '2400x1080');
  assert.deepEqual(h.requests, [{ version: 0, resolution: '2400x1080' }]);
  h.instance.get('button');
  assert.equal(h.requests.length, 1);
});

test('calibration coverage is checked per action and app version rather than one exact profile', () => {
  const rows = [
    { action_name: 'covered', platform_version: '38.6.0', resolution_profile: '1080x2400', strategies: [{ type: 'text', value: 'a' }, { type: 'image', template: 'ready.png' }] },
    { action_name: 'missing', platform_version: '38.6.0', resolution_profile: 'default', strategies: [{ type: 'text', value: 'b' }, { type: 'image', template: 'missing.png' }] },
    { action_name: 'old_app', platform_version: '38.5.0', resolution_profile: '1080x2400', strategies: [{ type: 'text', value: 'c' }, { type: 'image', template: 'ready.png' }] },
    { action_name: 'unobservable', resolution_profile: 'default', strategies: [{ type: 'coordinate', x_percent: 0.5, y_percent: 0.5 }, { type: 'image', template: 'missing.png' }] },
  ];
  const h = loader(rows);
  assert.deepEqual(Array.from(h.instance._calibrationActions()).sort(), ['missing', 'old_app']);
});

test('calibration upload keeps selector identity, app version and capture metadata', () => {
  const sandbox = { module: { exports: {} }, global: { __config: {} }, require: () => ({}), android: { util: { Base64: { encodeToString: () => 'aW1hZ2U=' } } } };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../core/api-client.js'), 'utf8'), sandbox);
  const api = sandbox.module.exports;
  let body;
  api.post = (url, value) => { body = JSON.parse(JSON.stringify(value)); return {}; };
  api.uploadCalibration([{ action_name: 'button', filename: 'observed.png', data: [1], source_selector_id: 'selector', source_selector_version: 3, platform_version: '38.7.0', source_resolution: '540x1200', source_density: 1.5 }], '1080x2400');
  assert.equal(body.templates[0].source_selector_id, 'selector');
  assert.equal(body.templates[0].source_selector_version, 3);
  assert.equal(body.templates[0].source_resolution, '540x1200');
  assert.equal(body.templates[0].source_density, 1.5);
  assert.equal(body.templates[0].platform_version, '38.7.0');
});

test('offline geometry refresh uses compatible default and retries at a bounded interval', () => {
  const h = loader([selector('1080x2400', 'old-specific', '38.6.0'), selector('default', 'fallback')]);
  h.setSize(720, 1280);
  assert.equal(h.instance.get('button').strategies[0].value, 'fallback');
  h.instance.get('button');
  assert.equal(h.requests.length, 1);
  h.setResponse({ version: 2, changed: true, selectors: [selector('720x1280', 'fresh')] });
  h.advance(30000);
  assert.equal(h.instance.get('button').strategies[0].value, 'fresh');
  assert.equal(h.requests.length, 2);
});

test('resolution refresh does not carry removed authoritative selectors forward', () => {
  const h = loader([selector('1080x2400', 'portrait')]);
  h.setSize(1440, 3200);
  h.setResponse({ version: 2, changed: true, selectors: [] });
  assert.equal(h.instance.get('button'), null);
  assert.equal(Object.keys(h.instance._cache).length, 0);
});

test('device API sends live resolution only when supplied', () => {
  const sandbox = { module: { exports: {} }, global: { __config: {} }, require: () => ({}) };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../core/api-client.js'), 'utf8'), sandbox);
  const api = sandbox.module.exports;
  const calls = [];
  api.get = (url, params) => { calls.push(JSON.parse(JSON.stringify({ url, params }))); return {}; };
  api.fetchSelectors(4, '2400x1080');
  api.fetchSelectors(4);
  assert.deepEqual(calls, [
    { url: '/api/device/selectors', params: { version: 4, resolution: '2400x1080' } },
    { url: '/api/device/selectors', params: { version: 4 } },
  ]);
});
