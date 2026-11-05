const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const geometry = require('../core/screen-context');

function loader(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'dy-fullchain-locator-templates-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const logicalRoot = '/sdcard/dy_auto/templates';
  const physical = name => String(name).startsWith(logicalRoot) ? path.join(root, String(name).slice(logicalRoot.length)) : String(name);
  const state = { now: 1000, manifestDown: false, failedDownload: '', failedWrite: '', manifests: 0, downloads: [] };
  const assets = { 'a.png': Buffer.from('first-image'), 'b.png': Buffer.from('second-image') };
  const manifest = Object.entries(assets).map(([filename, data]) => ({ filename, resolution: '1080x2400', size: data.length, md5: crypto.createHash('md5').update(data).digest('hex') }));
  const selector = { action_name: 'button', resolution_profile: '1080x2400', platform_version: 'default', strategies: [{ priority: 1, type: 'image', template: 'b.png' }] };
  function File(first, child) {
    this.path = physical(child === undefined ? first : path.join(String(first), String(child)));
    this.toString = () => this.path;
    this.exists = () => fs.existsSync(this.path);
    this.isDirectory = () => this.exists() && fs.statSync(this.path).isDirectory();
    this.length = () => this.exists() ? fs.statSync(this.path).size : 0;
    this.mkdirs = () => { fs.mkdirSync(this.path, { recursive: true }); return true; };
    this.delete = () => { fs.rmSync(this.path, { force: true }); return true; };
    this.renameTo = target => { fs.renameSync(this.path, String(target)); return true; };
  }
  const java = {
    io: {
      File,
      FileOutputStream: function (name) {
        const filename = physical(name);
        const fd = fs.openSync(filename, 'w');
        this.write = bytes => { if (state.failedWrite && filename.includes(state.failedWrite)) throw Error('storage temporarily unavailable'); fs.writeSync(fd, Buffer.from(bytes)); };
        this.close = () => fs.closeSync(fd);
      },
      FileInputStream: function (name) {
        const data = fs.readFileSync(physical(name)); let offset = 0;
        this.read = buffer => { if (offset === data.length) return -1; const size = Math.min(buffer.length, data.length - offset); data.copy(buffer, 0, offset, offset + size); offset += size; return size; };
        this.close = () => {};
      },
    },
    lang: { Byte: { TYPE: 0 }, reflect: { Array: { newInstance: (_, size) => Buffer.alloc(size) } } },
    security: { MessageDigest: { getInstance: name => {
      const hash = crypto.createHash(name.toLowerCase().replace('-', ''));
      return { update: (data, offset = 0, length = data.length - offset) => hash.update(Buffer.from(data).subarray(offset, offset + length)), digest: () => hash.digest() };
    } } },
  };
  const files = {
    exists: name => fs.existsSync(physical(name)),
    isDir: name => fs.existsSync(physical(name)) && fs.statSync(physical(name)).isDirectory(),
    listDir: name => fs.readdirSync(physical(name)),
    remove: name => { const filename = physical(name); if (fs.existsSync(filename) && fs.statSync(filename).isDirectory()) fs.rmdirSync(filename); else fs.rmSync(filename, { force: true }); return true; },
    writeBytes: (name, bytes) => { if (state.failedWrite && name.includes(state.failedWrite)) throw Error('storage temporarily unavailable'); fs.writeFileSync(physical(name), Buffer.from(bytes)); },
  };
  const api = {
    fetchSelectors: () => ({ changed: true, version: 2, selectors: [selector] }),
    fetchTemplateList: resolution => { assert.equal(resolution, '1080x2400'); state.manifests++; return state.manifestDown ? null : { templates: manifest }; },
    downloadTemplate: (filename, resolution) => { assert.equal(resolution, '1080x2400'); state.downloads.push(filename); return state.failedDownload === filename ? null : assets[filename]; },
  };
  const sandbox = {
    module: { exports: {} }, global: {}, files, java, device: { width: 1080, height: 2400 },
    Date: { now: () => state.now },
    context: { getPackageManager: () => ({ getPackageInfo: () => ({ versionName: '38.6.0' }) }) },
    require: name => name === './api-client' ? api : name === './screen-context' ? { read: () => geometry.create({ width: 1080, height: 2400 }) } : { info() {}, warn() {}, error() {}, debug() {} },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../core/selector-loader.js'), 'utf8'), sandbox);
  const instance = sandbox.module.exports;
  instance._resolution = '1080x2400'; instance._version = 1; instance._initialized = true;
  const write = (relative, data) => { const filename = path.join(root, relative); fs.mkdirSync(path.dirname(filename), { recursive: true }); fs.writeFileSync(filename, data); };
  return { instance, state, root, write, read: relative => fs.readFileSync(path.join(root, relative), 'utf8'), exists: relative => fs.existsSync(path.join(root, relative)), advance: ms => { state.now += ms; } };
}

test('a manifest outage is retried at a bounded interval without changing selector revision', t => {
  const h = loader(t); h.state.manifestDown = true;
  h.instance.checkAndUpdate(2);
  assert.equal(h.instance.getVersion(), 2);
  h.state.manifestDown = false;
  h.advance(9999);
  for (let i = 0; i < 3; i++) { h.instance.checkAndUpdate(2); h.instance.get('button'); }
  assert.equal(h.exists('1080x2400/b.png'), false);
  assert.equal(h.state.manifests, 1);
  h.advance(1); h.instance.checkAndUpdate(2);
  assert.equal(h.exists('1080x2400/b.png'), true, 'the same revision must retry the missing asset after recovery');
  assert.equal(h.read('1080x2400/b.png'), 'second-image');
  assert.equal(h.state.manifests, 2);
});

test('partial success is retained and old fallback caches survive until every download succeeds', t => {
  const h = loader(t); h.write('1080x2400/old.png', 'old fallback'); h.write('720x1600/old.png', 'other profile');
  h.state.failedDownload = 'b.png'; h.instance.checkAndUpdate(2);
  assert.equal(h.read('1080x2400/a.png'), 'first-image');
  assert.equal(h.read('1080x2400/old.png'), 'old fallback');
  assert.equal(h.exists('720x1600/old.png'), true, 'partial sync must not delete fallback profiles');
  assert.equal(h.read('720x1600/old.png'), 'other profile');
  h.state.failedDownload = ''; h.advance(10000); h.instance.get('button');
  assert.equal(h.read('1080x2400/b.png'), 'second-image');
  assert.equal(h.state.downloads.filter(name => name === 'a.png').length, 1);
  assert.equal(h.exists('1080x2400/old.png'), false);
  assert.equal(h.exists('720x1600/old.png'), false);
  const successfulRequests = h.state.manifests;
  h.advance(10000); h.instance.checkAndUpdate(2);
  assert.equal(h.state.manifests, successfulRequests, 'completed sync stops retrying');
});

test('a failed template write stays pending and never publishes a partial image', t => {
  const h = loader(t); h.state.failedWrite = 'b.png';
  h.instance.checkAndUpdate(2);
  assert.equal(h.exists('1080x2400/b.png'), false);
  h.state.failedWrite = ''; h.advance(10000); h.instance.checkAndUpdate(2);
  assert.equal(h.exists('1080x2400/b.png'), true, 'a failed write must be retried after recovery');
  assert.equal(h.read('1080x2400/b.png'), 'second-image');
});

test('a truncated cached image is repaired while a verified cached image is reused', t => {
  const h = loader(t); h.write('1080x2400/a.png', 'first-image'); h.write('1080x2400/b.png', 'partial');
  h.instance.checkAndUpdate(2);
  assert.equal(h.read('1080x2400/a.png'), 'first-image');
  assert.equal(h.read('1080x2400/b.png'), 'second-image');
  assert.deepEqual(h.state.downloads, ['b.png']);
});
