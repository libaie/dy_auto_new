const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

function runtime(executor = {
  getCurrentTaskId: () => 'old-task', getCurrentLeaseId: () => 'old-lease',
  getCurrentAccountId: () => 'old-account', getNextOpIndex: () => 0,
}) {
  const root = path.resolve(__dirname, '..');
  const noOp = () => {};
  const logger = { info: noOp, warn: noOp, debug: noOp, error: noOp };
  const config = { serverUrl: 'https://old.invalid', deviceId: 'device', deviceSecret: 'old-secret',
    network: { requestTimeout: 1, maxRetries: 1, retryBaseDelay: 1, retryMaxDelay: 1, offlineQueueMax: 100 },
    decision: { enabled: true, min_confidence: 0.5, min_probability: 0.75 }, ai: {} };
  const requests = [], connections = [], timers = new Map();
  let timerId = 0;
  const state = { config, requests, connections, onRequest: () => ({ statusCode: 200, body: '{}' }) };
  function request(method, url, body, options) {
    const record = { method, url, body, secret: options.headers['X-Device-Secret'] };
    requests.push(record);
    return state.onRequest(record);
  }
  function ClientBuilder() {
    this.readTimeout = this.pingInterval = function () { return this; };
    this.build = () => ({ newWebSocket(request, listener) {
      const socket = { messages: [], closes: [], send(message) { this.messages.push(message); return true; }, close(code, reason) { this.closes.push([code, reason]); return true; } };
      connections.push({ request, listener, socket });
      return socket;
    } });
  }
  function RequestBuilder() { this.url = function (url) { this.value = url; return this; }; this.build = function () { return { url: this.value }; }; }
  const sandbox = vm.createContext({
    global: { __config: config }, console, sleep: noOp,
    http: { get: (url, options) => request('GET', url, null, options), postJson: (url, body, options) => request('POST', url, body, options) },
    Packages: { okhttp3: { OkHttpClient: { Builder: ClientBuilder }, Request: { Builder: RequestBuilder }, WebSocketListener: function () {} } },
    JavaAdapter: function (type, methods) { return methods; },
    java: { util: { concurrent: { TimeUnit: { MILLISECONDS: 1, SECONDS: 1000 } } } },
    setInterval(fn) { const id = ++timerId; timers.set(id, fn); return id; }, clearInterval(id) { timers.delete(id); },
    setTimeout(fn) { const id = ++timerId; timers.set(id, fn); return id; }, clearTimeout(id) { timers.delete(id); },
  });
  const cache = new Map();
  function load(relative) {
    const filename = path.resolve(root, relative.endsWith('.js') ? relative : relative + '.js');
    if (filename === path.join(root, 'config.js')) return config;
    if (filename === path.join(root, 'utils/logger.js')) return logger;
    if (filename === path.join(root, 'core/task-executor.js')) return executor;
    if (cache.has(filename)) return cache.get(filename).exports;
    const module = { exports: {} };
    cache.set(filename, module);
    const wrapper = vm.runInContext('(function(require,module,exports){\n' + fs.readFileSync(filename, 'utf8') + '\n})', sandbox, { filename });
    wrapper(name => load(path.relative(root, path.resolve(path.dirname(filename), name))), module, module.exports);
    return module.exports;
  }
  state.load = load;
  state.api = load('core/api-client');
  state.ws = load('core/device-ws');
  return state;
}

const offlineReports = [
  { name: 'task result', path: '/api/device/report', send: api => api.report('old-task', 'completed', { count: 1 }, null, 'old-lease') },
  { name: 'collection', path: '/api/device/collect-report', send: api => api.collectReport({ task_id: 'old-task', comment: { content: 'old comment' } }) },
  { name: 'operation stats', path: '/api/device/stats/increment', send: api => api.incrementStats('old-account', 'follow', 'old-target', 1) },
];

function replaceSession(h) {
  h.config.serverUrl = 'https://new.invalid';
  h.config.deviceSecret = 'new-secret';
  h.api.setAuthFailureHandler(() => {});
}

for (const change of ['server', 'secret', 'device', 'session', 'same-callback session']) {
  test('offline results cannot cross a replacement ' + change, () => {
    const h = runtime();
    const onAuthFailure = () => {};
    h.api.setAuthFailureHandler(onAuthFailure);
    h.onRequest = () => { throw Error('offline'); };
    for (const report of offlineReports) report.send(h.api);
    assert.equal(h.api.getOfflineQueueSize(), 3);
    if (change === 'server') h.config.serverUrl = 'https://new.invalid';
    else if (change === 'secret') h.config.deviceSecret = 'new-secret';
    else if (change === 'device') h.config.deviceId = 'new-device';
    else h.api.setAuthFailureHandler(change === 'session' ? () => {} : onAuthFailure);
    h.requests.length = 0;
    h.onRequest = () => ({ statusCode: 200, body: '{}' });
    h.api.poll();
    assert.deepEqual(h.requests.map(request => request.method), ['GET']);
    assert.equal(h.api.getOfflineQueueSize(), 0);
  });
}

for (const report of offlineReports) {
  test(report.name + ' returning after re-pairing cannot enter the replacement offline queue', () => {
    for (const outcome of ['success', 'exception', 'auth failure']) {
      const h = runtime();
      h.api.setAuthFailureHandler(() => {});
      h.onRequest = request => {
        if (request.url === 'https://old.invalid' + report.path) {
          replaceSession(h);
          h.api.heartbeat();
          if (outcome === 'exception') throw Error('old connection failed');
          return { statusCode: outcome === 'success' ? 200 : 401, body: '{}' };
        }
        return { statusCode: 200, body: '{}' };
      };
      assert.equal(report.send(h.api), null);
      assert.equal(h.api.getOfflineQueueSize(), 0, outcome);
      h.api.poll();
      assert.equal(h.requests.filter(request => request.url === 'https://new.invalid' + report.path).length, 0);
    }
  });

  test(report.name + ' uses its own failure status when a heartbeat finishes while reading the response', () => {
    for (const [status, otherStatus, expectedQueued] of [[404, 200, 0], [429, 404, 1]]) {
      const h = runtime();
      h.onRequest = request => request.url.endsWith(report.path)
        ? { statusCode: status, body: { string() { h.api.heartbeat(); return '{"detail":"report error"}'; } } }
        : { statusCode: otherStatus, body: '{}' };
      assert.equal(report.send(h.api), null);
      assert.equal(h.api.getOfflineQueueSize(), expectedQueued, 'report status ' + status);
      h.onRequest = () => ({ statusCode: 200, body: '{}' });
      h.api.poll();
      assert.equal(h.api.getOfflineQueueSize(), 0);
    }
  });
}

test('an offline replay retired in flight is discarded while a new-session queued result survives', () => {
  const h = runtime();
  h.api.setAuthFailureHandler(() => {});
  h.onRequest = () => { throw Error('offline'); };
  h.api.report('old-task', 'completed', {}, null, 'old-lease');
  h.onRequest = request => {
    if (request.url === 'https://old.invalid/api/device/report') {
      replaceSession(h);
      h.api.report('new-task', 'completed', {}, null, 'new-lease');
      h.api.heartbeat();
      throw Error('retired replay failed');
    }
    if (request.url === 'https://new.invalid/api/device/report') throw Error('new session offline');
    return { statusCode: 200, body: '{}' };
  };
  h.api.poll();
  assert.equal(h.api.getOfflineQueueSize(), 1, 'only the new result may remain queued');
  h.requests.length = 0;
  h.onRequest = () => ({ statusCode: 200, body: '{}' });
  h.api.poll();
  assert.deepEqual(h.requests.filter(request => request.method === 'POST').map(request => request.body.task_id), ['new-task']);
  assert.equal(h.api.getOfflineQueueSize(), 0);
});

test('same-session task, collection and stats results retain their original payloads for offline replay', () => {
  const h = runtime();
  h.api.setAuthFailureHandler(() => {});
  h.onRequest = () => { throw Error('offline'); };
  const originals = [];
  for (const report of offlineReports) {
    const firstAttempt = h.requests.length;
    report.send(h.api);
    originals.push(JSON.stringify(h.requests[firstAttempt].body));
  }
  h.requests.length = 0;
  h.onRequest = () => ({ statusCode: 200, body: '{}' });
  h.api.poll();
  assert.deepEqual(h.requests.filter(request => request.method === 'POST').map(request => JSON.stringify(request.body)), originals);
  assert.equal(h.api.getOfflineQueueSize(), 0);
});

test('a queued permanent failure cannot borrow a successful nested heartbeat status and block later results', () => {
  const h = runtime();
  h.onRequest = () => { throw Error('offline'); };
  h.api.report('deleted', 'completed', {});
  h.api.report('valid', 'completed', {});
  h.requests.length = 0;
  h.onRequest = request => request.body && request.body.task_id === 'deleted'
    ? { statusCode: 404, body: { string() { h.api.heartbeat(); return '{"detail":"deleted"}'; } } }
    : { statusCode: 200, body: '{}' };
  h.api.poll();
  assert.deepEqual(h.requests.filter(request => request.body && request.body.task_id).map(request => request.body.task_id), ['deleted', 'valid']);
  assert.equal(h.api.getOfflineQueueSize(), 0);
});

for (const delivery of ['completion', 'cancel acknowledgement']) {
  test('main binds its ' + delivery + ' to the originating session even after executor cleanup', () => {
    const h = runtime();
    const loop = require('./helpers/main-loop')({ autoStart: false });
    const originalAuthHandler = loop.api.setAuthFailureHandler;
    loop.api.setAuthFailureHandler = handler => { originalAuthHandler(handler); h.api.setAuthFailureHandler(handler); };
    loop.api.captureSession = () => h.api.captureSession();
    loop.api.report = (...args) => {
      // The pairing callback wins after main's final authFailed check, before
      // the transport starts. The result still belongs to main's old session.
      replaceSession(h);
      return h.api.report(...args);
    };
    loop.start();
    if (delivery === 'completion') {
      loop.dispatch({ id: 'old-task', type: 'collect', lease_id: 'old-lease', params: {} });
      loop.run();
    } else {
      loop.cancel('old-task');
    }
    assert.deepEqual(h.requests, []);
    assert.equal(h.api.getOfflineQueueSize(), 0);
  });
}

function taskApiRuntime() {
  const task = require('./helpers/task-runtime')();
  const h = runtime(task.executor);
  for (const [name, method] of Object.entries(h.api)) {
    if (typeof method === 'function') task.api[name] = method.bind(h.api);
  }
  h.api.setAuthFailureHandler(() => {});
  return { h, task };
}

test('a retired collection worker cannot start side-data requests with replacement credentials', () => {
  const { h, task } = taskApiRuntime();
  const handler = task.load('handlers/search-collect');
  const utils = task.load('handlers/comment-utils');
  utils.parseCommentItem = () => ({ nickname: 'old-nick', text: 'old comment', time: 'just now' });
  utils.localPreFilter = () => true;
  utils.parseTime = () => new Date(1000);
  task.ui.findElements = () => [{}];
  handler._collectCommentData = () => ({ nickname: 'old-nick', content: 'old comment' });
  handler._collectUserData = () => {
    task.cancellation.cancel();
    replaceSession(h);
    return { douyin_id: 'old-user' };
  };
  task.executor.registerHandler('collect', { execute(params) {
    handler._processComments(params, { success_count: 0, details: [] }, 0);
    return { success: true, result: {} };
  } });
  const result = task.executor.execute({ id: 'old-task', lease_id: 'old-lease', account_id: 'old-account', type: 'collect', params: { keyword: 'old-query', count: 1, max_age_seconds: -1 } });
  assert.equal(result.status, 'cancelled');
  assert.deepEqual(h.requests, []);
  assert.equal(h.api.getOfflineQueueSize(), 0);
});

function taskSideEffects(api) {
  api.report('old-task', 'cancelled', {}, null, 'old-lease');
  api.collectReport({ task_id: 'old-task', comment: { content: 'old comment' } });
  api.incrementStats('old-account', 'follow', 'old-user', 1);
  api.saveUserProfile({ nickname: 'old-user', _taskId: 'old-task' });
  api.uploadUserAvatar('old-user', 'synthetic-image');
  api.saveCommentAIReply('old-user', 'old comment', 'old reply', 'old-task');
  api.claimCommentReply('old-user', 'old comment');
  api.releaseCommentReply('old-user', 'old comment');
  api.claimDMRecipient({ recipient_key: 'old-user' });
  api.releaseDMRecipient({ conversation_id: 'old-conversation' });
  api.reportDMSend({ conversation_id: 'old-conversation' });
  api.reportRiskControl('old-account', 'captcha', {});
  api.reportProgress('old-task', 'profile', '', 0.5);
}

test('a retired attempt blocks task side effects while new-session control traffic remains available', () => {
  const { h, task } = taskApiRuntime();
  task.executor.registerHandler('collect', { execute() {
    task.cancellation.cancel();
    replaceSession(h);
    taskSideEffects(h.api);
    h.api.heartbeat();
    h.api.register({ device_id: 'device' });
    h.api.poll();
    h.api.fetchSelectors(0);
    h.api.fetchPromptTemplates(0);
    return { success: true, result: {} };
  } });
  task.executor.execute({ id: 'old-task', type: 'collect', lease_id: 'old-lease', params: {} });
  assert.deepEqual(h.requests.map(request => request.url.split('?')[0]), [
    'https://new.invalid/api/device/heartbeat', 'https://new.invalid/api/device/register',
    'https://new.invalid/api/device/poll', 'https://new.invalid/api/device/selectors',
    'https://new.invalid/api/device/prompt-templates',
  ]);
  assert.equal(h.api.getOfflineQueueSize(), 0);
  h.requests.length = 0;
  task.executor.registerHandler('collect', { execute() { h.api.incrementStats('new-account', 'follow', 'new-user', 1); return { success: true, result: {} }; } });
  assert.equal(task.executor.execute({ id: 'new-task', type: 'collect', lease_id: 'new-lease', params: {} }).status, 'completed');
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0].body.lease_id, 'new-lease');
});

test('ordinary cancellation preserves same-session reports and known-unsent claim cleanup', () => {
  const { h, task } = taskApiRuntime();
  task.executor.registerHandler('collect', { execute() {
    task.cancellation.cancel();
    h.api.report('old-task', 'cancelled', {}, null, 'old-lease');
    h.api.incrementStats('old-account', 'follow', 'already-followed', 1);
    h.api.releaseCommentReply('old-user', 'unsent comment');
    h.api.releaseDMRecipient({ conversation_id: 'unsent-conversation' });
    return { success: true, result: {} };
  } });
  task.executor.execute({ id: 'old-task', type: 'collect', lease_id: 'old-lease', params: {} });
  assert.deepEqual(h.requests.map(request => request.url.split('/api/device/')[1]), ['report', 'stats/increment', 'comment-claim-release', 'dm-release-recipient']);
});

for (const mode of ['http', 'decision']) {
  test(mode + ' 401 from a retired request cannot invalidate the replacement pairing', () => {
    const h = runtime();
    let invalidated = 0;
    h.api.setAuthFailureHandler(() => {});
    h.onRequest = () => {
      h.config.deviceSecret = 'new-secret';
      h.api.setAuthFailureHandler(() => { invalidated++; });
      return { statusCode: 401, body: '{}' };
    };
    if (mode === 'http') h.api.get('/api/device/poll');
    else h.load('core/decision-client').decide({}, { relevant: { type: 'noul', instructions: 'Relevant?' } });
    assert.equal(invalidated, 0);
  });
}

test('an old HTTP request cannot retry its URL with replacement credentials', () => {
  const h = runtime();
  h.api.setAuthFailureHandler(() => {});
  h.onRequest = () => {
    h.config.serverUrl = 'https://new.invalid';
    h.config.deviceSecret = 'new-secret';
    h.api.setAuthFailureHandler(() => {});
    throw Error('old connection failed');
  };
  assert.equal(h.api.get('/api/device/poll'), null);
  assert.deepEqual(h.requests.map(request => [request.url, request.secret]), [['https://old.invalid/api/device/poll', 'old-secret']]);
});

test('successful old HTTP side data is discarded after the session changes', () => {
  const h = runtime();
  h.api.setAuthFailureHandler(() => {});
  h.onRequest = () => {
    h.api.setAuthFailureHandler(() => {});
    return { statusCode: 200, body: '{"version":99,"templates":[]}' };
  };
  assert.equal(h.api.get('/api/device/prompt-templates'), null);
});

test('current-session authentication failure still requests re-pairing once', () => {
  const h = runtime();
  let invalidated = 0;
  h.api.setAuthFailureHandler(() => { invalidated++; });
  h.onRequest = () => ({ statusCode: 401, body: '{}' });
  h.api.get('/api/device/poll');
  assert.equal(invalidated, 1);
  assert.equal(h.requests.length, 1);
});

test('Jev result received after task cancellation is discarded', () => {
  const h = runtime();
  h.onRequest = () => {
    h.load('core/task-cancellation').cancel();
    return { statusCode: 200, body: '{"model":"jev","answers":{"relevant":{"type":"noul","noul":0.99}}}' };
  };
  assert.equal(h.load('core/decision-client').decide({}, { relevant: { type: 'noul', instructions: 'Relevant?' } }), null);
});

test('generation result received after task cancellation is discarded', () => {
  const h = runtime();
  h.onRequest = () => {
    h.load('core/task-cancellation').cancel();
    return { statusCode: 200, body: '{"content":"late reply"}' };
  };
  assert.equal(h.load('core/ai-analyzer')._callAI('prompt'), null);
});

function reconnect(h, openOld) {
  h.ws.start();
  const old = h.connections[0];
  if (openOld) old.listener.onOpen(old.socket, {});
  h.ws.stop();
  h.config.deviceSecret = 'new-secret';
  h.ws.start();
  const current = h.connections[1];
  current.listener.onOpen(current.socket, {});
  return { old, current };
}

test('a pending old WebSocket opening after re-pairing cannot authenticate or replace the new socket', () => {
  const h = runtime();
  const { old, current } = reconnect(h, false);
  old.listener.onOpen(old.socket, {});
  assert.equal(h.ws._ws, current.socket);
  assert.deepEqual(old.socket.messages, []);
  assert.equal(JSON.parse(current.socket.messages[0]).secret, 'new-secret');
});

test('a retired WebSocket cannot deliver a cancellation into a new task lease', () => {
  const h = runtime();
  const { old, current } = reconnect(h, true);
  const cancelled = [];
  h.ws.setCallbacks({ onCancelTask(id) { cancelled.push(id); } });
  old.listener.onMessage(old.socket, '{"event":"cancel_task","task_id":"same-task"}');
  assert.deepEqual(cancelled, []);
  current.listener.onMessage(current.socket, '{"event":"cancel_task","task_id":"current-task"}');
  assert.deepEqual(cancelled, ['current-task']);
});

for (const event of ['onClosing', 'onFailure']) {
  test('retired WebSocket ' + event + ' leaves the current pairing connected', () => {
    const h = runtime();
    const { old, current } = reconnect(h, true);
    let invalidated = 0;
    h.ws.setAuthFailureHandler(() => { invalidated++; });
    if (event === 'onClosing') old.listener.onClosing(old.socket, 4001, 'old auth failure');
    else old.listener.onFailure(old.socket, { getMessage: () => 'old failure' }, null);
    assert.equal(h.ws._ws, current.socket);
    assert.equal(h.ws.isConnected(), true);
    assert.equal(invalidated, 0);
  });
}
