const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

function client(t, executor) {
  const root = path.resolve(__dirname, '..');
  const originalLoad = Module._load;
  const oldConfig = global.__config;
  const oldHttp = global.http;
  let online = false;
  const responses = new Map();
  const attempts = [];
  const payloads = [];
  const ok = { statusCode: 200, body: '{"ok":true}' };
  Module._load = function (request, parent, isMain) {
    const resolved = Module._resolveFilename(request, parent, isMain);
    if (resolved === path.join(root, 'utils/logger.js')) return { info() {}, warn() {}, error() {}, debug() {} };
    if (executor && resolved === path.join(root, 'core/task-executor.js')) return executor;
    return originalLoad.apply(this, arguments);
  };
  global.__config = {
    serverUrl: 'https://unit.invalid', deviceSecret: 'unit-secret', deviceId: 'unit-device',
    network: { maxRetries: 0, requestTimeout: 1, offlineQueueMax: 100 },
  };
  global.http = {
    get() { if (!online) throw Error('offline'); return ok; },
    postJson(url, body) {
      if (!online) throw Error('offline');
      attempts.push(body.task_id || 'heartbeat');
      payloads.push(JSON.parse(JSON.stringify(body)));
      const code = responses.get(body.task_id) || 200;
      return code === 200 ? ok : { statusCode: code, body: '{"detail":"test error"}' };
    },
  };
  const filename = require.resolve('../core/api-client');
  delete require.cache[filename];
  const api = require(filename);
  t.after(() => {
    Module._load = originalLoad;
    global.__config = oldConfig;
    global.http = oldHttp;
    delete require.cache[filename];
  });
  return { api, attempts, payloads, responses, reconnect: () => { online = true; } };
}

test('permanent failure at queue head does not block later valid results', t => {
  const { api, attempts, responses, reconnect } = client(t);
  api.report('deleted', 'completed', {});
  api.report('valid', 'completed', {});
  assert.equal(api.getOfflineQueueSize(), 2);
  responses.set('deleted', 404);
  reconnect();
  api.poll();
  assert.deepEqual(attempts, ['deleted', 'valid']);
  assert.equal(api.getOfflineQueueSize(), 0);
});

test('temporary rate limiting retries on later healthy requests and retains critical reports', t => {
  const { api, attempts, responses, reconnect } = client(t);
  api.report('limited', 'completed', {});
  api.report('valid', 'completed', {});
  responses.set('limited', 429);
  reconnect();
  for (let i = 0; i < 4; i++) api.heartbeat();
  assert.equal(api.getOfflineQueueSize(), 2);
  responses.delete('limited');
  api.heartbeat();
  assert.equal(attempts.filter(id => id === 'limited').length, 5);
  assert.equal(attempts.filter(id => id === 'valid').length, 1);
  assert.equal(api.getOfflineQueueSize(), 0);
});

test('successful replay does not recursively flush or duplicate queued results', t => {
  const { api, attempts, reconnect } = client(t);
  for (const id of ['a', 'b', 'c']) api.report(id, 'completed', {});
  reconnect();
  api.heartbeat();
  api.heartbeat();
  assert.deepEqual(attempts.filter(id => id !== 'heartbeat'), ['a', 'b', 'c']);
  assert.equal(api.getOfflineQueueSize(), 0);
});

test('authentication failure retains queued reports for re-pairing', t => {
  const { api, responses, reconnect } = client(t);
  api.report('auth', 'completed', {});
  responses.set('auth', 401);
  reconnect();
  api.poll();
  assert.equal(api.getOfflineQueueSize(), 1);
  responses.delete('auth');
  api.poll();
  assert.equal(api.getOfflineQueueSize(), 0);
});

test('queued stats preserve their original attempt lease after the executor advances', t => {
  let lease = 'attempt-one';
  const executor = {
    getCurrentTaskId: () => 'task', getCurrentAccountId: () => 'account',
    getCurrentLeaseId: () => lease, getNextOpIndex: () => 0,
  };
  const { api, payloads, reconnect } = client(t, executor);
  api.incrementStats('account', 'follow', 'target', 1);
  assert.equal(api.getOfflineQueueSize(), 1);
  lease = 'attempt-two';
  reconnect();
  api.poll();
  assert.equal(payloads[0].lease_id, 'attempt-one');
  assert.equal(payloads[0].op_index, 0);
  assert.equal(api.getOfflineQueueSize(), 0);
});
