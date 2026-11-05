const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');

const updaterSource = fs.readFileSync(path.join(__dirname, '../core/update-checker.js'), 'utf8');

function writeArchive(filename, contents, options = {}) {
  const entries = Object.entries(contents).map(([name, data]) => [name, Buffer.from(data).toString('base64')]);
  const manifest = { format: 1, entry: 'main.js', files: {} };
  for (const [name, data] of Object.entries(contents)) {
    manifest.files[name] = { size: Buffer.byteLength(data), sha256: crypto.createHash('sha256').update(data).digest('hex') };
  }
  if (options.badHash) manifest.files['main.js'].sha256 = '0'.repeat(64);
  if (!options.noManifest) entries.push(['device-update.json', Buffer.from(JSON.stringify(manifest)).toString('base64')]);
  for (const [name, data] of options.extra || []) entries.push([name, Buffer.from(data).toString('base64')]);
  execFileSync('python', ['-W', 'ignore::UserWarning', '-c', 'import sys,json,zipfile,base64\na=zipfile.ZipFile(sys.argv[1],"w",zipfile.ZIP_DEFLATED)\nfor n,d in json.load(sys.stdin): a.writestr(n,base64.b64decode(d))\na.close()', filename], { input: JSON.stringify(entries) });
}

function harness(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'dy-fullchain-locator-update-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const project = path.join(root, 'project');
  const internal = path.join(root, 'internal');
  fs.mkdirSync(path.join(project, 'core'), { recursive: true });
  fs.mkdirSync(path.join(project, 'cache'), { recursive: true });
  fs.mkdirSync(path.join(internal, 'update'), { recursive: true });
  fs.writeFileSync(path.join(project, 'main.js'), 'global.started = require("./core/ai-analyzer");');
  fs.writeFileSync(path.join(project, 'core/ai-analyzer.js'), 'module.exports = "old";');
  fs.writeFileSync(path.join(project, 'config.js'), 'module.exports = { userSetting: "kept" };');
  fs.writeFileSync(path.join(project, 'cache/state.json'), '{"persist":true}');
  fs.writeFileSync(path.join(internal, 'update/local_version.txt'), '1.0.0');
  const state = { cwd: project, version: '1.0.1', failCopy: () => false, failRename: () => false, onCopy: () => {} };
  const archivePath = path.join(root, 'incoming.zip');

  function File(first, child) {
    this.path = child === undefined ? String(first) : path.join(String(first), String(child));
    this.toString = () => this.path;
    this.getAbsolutePath = this.getCanonicalPath = () => path.resolve(this.path);
    this.exists = () => fs.existsSync(this.path);
    this.isDirectory = () => this.exists() && fs.statSync(this.path).isDirectory();
    this.isFile = () => this.exists() && fs.statSync(this.path).isFile();
    this.length = () => this.exists() ? fs.statSync(this.path).size : 0;
    this.mkdirs = () => { fs.mkdirSync(this.path, { recursive: true }); return true; };
    this.delete = () => { try { fs.rmSync(this.path); return true; } catch (_) { return false; } };
    this.renameTo = target => {
      if (state.failRename(this.path, String(target))) return false;
      fs.renameSync(this.path, String(target)); return true;
    };
  }
  File.separator = path.sep;
  function input(data) {
    let offset = 0;
    return { read(buffer) { if (offset >= data.length) return -1; const size = Math.min(buffer.length, data.length - offset); data.copy(buffer, 0, offset, offset + size); offset += size; return size; }, close() {} };
  }
  function ZipFile(filename) {
    const encoded = JSON.parse(execFileSync('python', ['-c', 'import sys,zipfile,json,base64\na=zipfile.ZipFile(sys.argv[1]);print(json.dumps([[i.filename,base64.b64encode(a.read(i)).decode()] for i in a.infolist()]))', String(filename)], { encoding: 'utf8' }));
    this.items = encoded.map(([name, encodedData]) => {
      const data = Buffer.from(encodedData, 'base64');
      return { getName: () => name, getSize: () => data.length, getMethod: () => 8, isDirectory: () => name.endsWith('/'), data };
    });
    this.entries = () => { let i = 0; return { hasMoreElements: () => i < this.items.length, nextElement: () => this.items[i++] }; };
    this.getInputStream = entry => input(entry.data);
    this.close = () => {};
  }
  const java = {
    io: {
      File,
      FileInputStream: function (name) { return input(fs.readFileSync(String(name))); },
      BufferedInputStream: function (stream) { return stream; },
      FileOutputStream: function (name) {
        const fd = fs.openSync(String(name), 'w');
        this.write = (data, offset = 0, length = data.length - offset) => fs.writeSync(fd, Buffer.from(data).subarray(offset, offset + length));
        this.close = () => fs.closeSync(fd);
      },
      BufferedOutputStream: function (stream) { return stream; },
    },
    util: { zip: { ZipFile } },
    lang: { Byte: { TYPE: 0 }, reflect: { Array: { newInstance: (_, size) => Buffer.alloc(size) } } },
    security: { MessageDigest: { getInstance: name => {
      const hash = crypto.createHash(name.toLowerCase().replace('-', ''));
      return { update: (data, offset = 0, length = data.length - offset) => hash.update(Buffer.from(data).subarray(offset, offset + length)), digest: () => hash.digest() };
    } } },
  };
  const files = {
    cwd: () => state.cwd,
    exists: name => fs.existsSync(name),
    isDir: name => fs.existsSync(name) && fs.statSync(name).isDirectory(),
    listDir: name => fs.readdirSync(name),
    read: name => fs.readFileSync(name, 'utf8'),
    readBytes: name => fs.readFileSync(name),
    write: (name, value) => fs.writeFileSync(name, value),
    copy: (from, to) => { state.onCopy(from, to); if (state.failCopy(from, to)) return false; fs.copyFileSync(from, to); return true; },
    remove: name => { fs.rmSync(name, { force: true }); return true; },
    removeDir: name => { fs.rmSync(name, { recursive: true, force: true }); return true; },
  };
  const api = {
    getScriptVersion: () => state.version,
    downloadScript: () => { fs.copyFileSync(archivePath, path.join(internal, 'update/device-script.zip')); return true; },
  };
  const globals = { __updateApi: api };
  const sandbox = {
    module: { exports: {} }, global: globals, files, java,
    context: { getFilesDir: () => new File(internal) },
    $zip: { extract: (zip, target) => execFileSync('python', ['-c', 'import sys,zipfile\nzipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])', zip, target]) },
    require: name => name === './api-client' ? api : { info() {}, warn() {}, error() {} },
  };
  vm.runInNewContext(updaterSource, sandbox, { filename: 'update-checker.js' });
  const updater = sandbox.module.exports;
  function packageFiles(label = 'new') {
    return {
      'main.js': 'global.started = require("./core/ai-analyzer"); global.runningUpdater = require("./core/update-checker");',
      'config.js': 'module.exports = {};',
      'project.json': '{"main":"main.js"}',
      'core/ai-analyzer.js': 'module.exports = require("./decision-client");',
      'core/decision-client.js': 'module.exports = ' + JSON.stringify(label) + ';',
      'core/update-checker.js': updaterSource,
      'core/api-client.js': 'module.exports = global.__updateApi;',
      'utils/logger.js': 'module.exports = { info: function () {}, warn: function () {}, error: function () {} };',
    };
  }
  function boot() {
    state.cwd = project;
    delete globals.started;
    delete globals.__dyAutoProjectRoot;
    const loaded = {};
    const run = filename => {
      if (loaded[filename]) return loaded[filename].exports;
      const module = { exports: {} }; loaded[filename] = module;
      if (filename !== path.join(project, 'main.js') && path.basename(filename) === 'main.js') state.cwd = path.dirname(filename);
      const requireLocal = name => {
        let resolved = path.resolve(path.dirname(filename), name);
        if (!path.extname(resolved)) resolved += '.js';
        return run(resolved);
      };
      vm.runInNewContext(fs.readFileSync(filename, 'utf8'), { ...sandbox, module, require: requireLocal }, { filename });
      return module.exports;
    };
    run(path.join(project, 'main.js'));
    return globals.started;
  }
  return { root, project, internal, state, globals, updater, boot, packageFiles, useArchive(filename) { fs.copyFileSync(filename, archivePath); }, prepare(contents = packageFiles(), options) { writeArchive(archivePath, contents, options); } };
}

test('missing nested static dependency is rejected before changing the runnable tree or version', t => {
  const h = harness(t), files = h.packageFiles();
  delete files['core/decision-client.js']; h.prepare(files);
  assert.equal(h.updater.checkAndUpdate(), false);
  assert.equal(h.updater.getLocalVersion(), '1.0.0');
  assert.equal(h.boot(), 'old');
});

test('a false copy result keeps every previous module and version runnable', t => {
  const h = harness(t); h.prepare();
  h.state.failCopy = (_, target) => target.endsWith('/decision-client.js');
  assert.equal(h.updater.checkAndUpdate(), false);
  assert.equal(h.updater.getLocalVersion(), '1.0.0');
  assert.equal(h.boot(), 'old');
  assert.equal(fs.readFileSync(path.join(h.project, 'config.js'), 'utf8'), 'module.exports = { userSetting: "kept" };');
});

test('hash mismatch, traversal, duplicate entries and non-root layout never activate', t => {
  for (const options of [{ badHash: true }, { extra: [['../outside.js', 'bad']] }, { extra: [['main.js', 'duplicate']] }, { noManifest: true }]) {
    const h = harness(t); h.prepare(h.packageFiles(), options);
    assert.equal(h.updater.checkAndUpdate(), false, JSON.stringify(options));
    assert.equal(h.boot(), 'old');
  }
  const h = harness(t), wrapped = {};
  for (const [name, data] of Object.entries(h.packageFiles())) wrapped['device/' + name] = data;
  h.prepare(wrapped);
  assert.equal(h.updater.checkAndUpdate(), false);
  assert.equal(h.boot(), 'old');
});

test('failed entry activation preserves the previous runnable entry and version', t => {
  const h = harness(t); h.prepare();
  h.state.failRename = (_, target) => target === path.join(h.project, 'main.js');
  assert.equal(h.updater.checkAndUpdate(), false);
  assert.equal(h.updater.getLocalVersion(), '1.0.0');
  assert.equal(h.boot(), 'old');
});

test('two complete upgrades and a later failed upgrade keep a stable root, matching version and persistent data', t => {
  const h = harness(t); h.prepare(h.packageFiles('first'));
  h.state.onCopy = () => assert.equal(fs.readFileSync(path.join(h.project, 'core/ai-analyzer.js'), 'utf8'), 'module.exports = "old";');
  assert.equal(h.updater.checkAndUpdate(), true);
  assert.equal(h.boot(), 'first');
  const secondUpdater = h.globals.runningUpdater;
  assert.equal(secondUpdater.getLocalVersion(), '1.0.1');
  assert.equal(h.globals.__dyAutoProjectRoot, h.project);
  assert.notEqual(h.state.cwd, h.project, 'simulate AutoJS module cwd inside the release');

  h.state.version = '1.0.2'; h.prepare(h.packageFiles('second'));
  assert.equal(secondUpdater.checkAndUpdate(), true);
  assert.equal(h.boot(), 'second');
  const thirdUpdater = h.globals.runningUpdater;
  assert.equal(thirdUpdater.getLocalVersion(), '1.0.2');
  assert.equal(h.globals.__dyAutoProjectRoot, h.project);
  h.state.version = '1.0.3'; h.prepare(h.packageFiles('broken'));
  h.state.failCopy = (_, target) => target.endsWith('/decision-client.js');
  assert.equal(thirdUpdater.checkAndUpdate(), false);
  assert.equal(h.boot(), 'second');
  assert.equal(h.globals.runningUpdater.getLocalVersion(), '1.0.2');
  assert.equal(fs.readFileSync(path.join(h.project, 'cache/state.json'), 'utf8'), '{"persist":true}');
  assert.equal(fs.readFileSync(path.join(h.project, 'config.js'), 'utf8'), 'module.exports = { userSetting: "kept" };');
});

test('the tracked packer produces a real repository release accepted by the device validator', t => {
  const h = harness(t);
  const repo = path.resolve(__dirname, '../..');
  const archive = path.join(h.root, 'repository.zip');
  execFileSync('python', [path.join(repo, 'tools/pack_device.py'), '--output', archive], { env: { ...process.env, PYTHON_DOTENV_DISABLED: '1' } });
  h.useArchive(archive);
  assert.equal(h.updater.checkAndUpdate(), true);
  assert.equal(h.updater.getLocalVersion(), '1.0.1');
  const releaseRoot = path.join(h.project, '.dy_auto_releases');
  const releases = fs.readdirSync(releaseRoot).filter(name => fs.statSync(path.join(releaseRoot, name)).isDirectory());
  assert.equal(releases.length, 1);
  assert.equal(
    fs.readFileSync(path.join(releaseRoot, releases[0], 'core/decision-client.js'), 'utf8'),
    fs.readFileSync(path.join(repo, 'device/core/decision-client.js'), 'utf8'),
  );
  assert.equal(fs.existsSync(path.join(releaseRoot, releases[0], 'test')), false);
});
