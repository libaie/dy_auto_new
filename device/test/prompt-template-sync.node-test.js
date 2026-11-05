var test = require('node:test');
var assert = require('node:assert/strict');
var fs = require('node:fs');
var path = require('node:path');
var vm = require('node:vm');

function loadSnapshots(snapshots) {
  var requests = [];
  var context = {
    module: { exports: {} }, global: {}, sleep: function () {},
    require: function (name) {
      if (name === './api-client') return {
        fetchPromptTemplates: function (version) { requests.push(version); return snapshots.shift(); },
      };
      if (name === '../utils/logger') return { info: function () {}, warn: function () {}, debug: function () {} };
      throw new Error('Unexpected dependency ' + name);
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../core/prompt-template-loader.js'), 'utf8'), context);
  return { loader: context.module.exports, requests: requests };
}

test('a full template snapshot removes disabled entries and never substitutes another explicit ID', function () {
  var h = loadSnapshots([
    { version: 1, changed: true, templates: [{ id: 'A', content: { identity: 'old' } }, { id: 'B', content: { identity: 'before' } }] },
    { version: 2, changed: true, templates: [{ id: 'B', content: { identity: 'after' } }] },
  ]);
  h.loader.init();
  h.loader.checkAndUpdate(2);
  assert.equal(h.loader.get('A'), null);
  assert.equal(h.loader.get('unknown-id'), null);
  assert.equal(h.loader.get('B').content.identity, 'after');
  assert.equal(h.loader.get().id, 'B');
  assert.equal(h.loader.getVersion(), 2);
});

test('an empty newer snapshot clears defaults and does not continually fetch the same revision', function () {
  var h = loadSnapshots([
    { version: 5, changed: true, templates: [{ id: 'A', content: { identity: 'old' } }] },
    { version: 6, changed: true, templates: [] },
  ]);
  h.loader.init();
  h.loader.checkAndUpdate(6);
  h.loader.checkAndUpdate(6);
  assert.equal(h.loader.get(), null);
  assert.equal(h.loader.get('A'), null);
  assert.equal(h.loader.getVersion(), 6);
  assert.deepEqual(h.requests, [0, 5]);
});
