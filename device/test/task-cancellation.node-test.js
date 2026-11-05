const assert = require('node:assert/strict');
const { test } = require('node:test');
const mainLoop = require('./helpers/main-loop');
const taskRuntime = require('./helpers/task-runtime');

const task = (id = 'task', lease = 'lease-one', type = 'search_like', params = {}) => ({ id, type, lease_id: lease, params });

test('cancel after dequeue prevents a reserved worker from executing and acknowledges its lease', () => {
  const runtime = taskRuntime();
  const loop = mainLoop({ executor: runtime.executor });
  const actions = [];
  runtime.executor.registerHandler('search_like', { execute() { actions.push('like'); return { success: true, result: {} }; } });
  loop.dispatch(task());
  loop.cancel('task');
  loop.run();
  assert.deepEqual(actions, []);
  assert.deepEqual(loop.reports, [{ id: 'task', status: 'cancelled', lease: 'lease-one' }]);
});

test('cancellation between worker entry and executor entry survives executor initialization', () => {
  const runtime = taskRuntime();
  let loop;
  const executor = Object.create(runtime.executor);
  executor.execute = function (value, cancellation) {
    loop.cancel(value.id);
    return runtime.executor.execute(value, cancellation);
  };
  loop = mainLoop({ executor });
  const actions = [];
  runtime.executor.registerHandler('search_like', { execute() { actions.push('like'); return { success: true, result: {} }; } });
  loop.dispatch(task());
  loop.run();
  assert.deepEqual(actions, []);
  assert.equal(loop.reports.at(-1).status, 'cancelled');
});

test('watchdog expiry before worker start cannot run the expired task', () => {
  const runtime = taskRuntime();
  const loop = mainLoop({ executor: runtime.executor });
  const actions = [];
  runtime.executor.registerHandler('search_like', { execute() { actions.push('like'); return { success: true, result: {} }; } });
  loop.dispatch(task());
  loop.timeout(10 * 60 * 1000);
  loop.run();
  assert.deepEqual(actions, []);
});

for (const invalidation of ['authFail', 'remove']) {
  test(invalidation + ' cancels a running search before its next interaction', () => {
    const runtime = taskRuntime();
    const loop = mainLoop({ executor: runtime.executor });
    let interactions = 0;
    runtime.load('handlers/search-like')._interactWithVideo = () => {
      interactions++;
      if (interactions === 1) loop[invalidation]();
      return true;
    };
    loop.dispatch(task('old', 'old-lease', 'search_like', { keyword: 'query', video_count: 3 }));
    loop.run();
    assert.equal(interactions, 1);
    assert.equal(loop.config.deviceSecret, '');
    assert.deepEqual(loop.reports, [], 'an invalidated session must not report with replacement credentials');
  });

  test(invalidation + ' keeps replacement-session work queued until the old worker exits', () => {
    const runtime = taskRuntime();
    const loop = mainLoop({ executor: runtime.executor, pairResult: { status: 'approved', config: {} } });
    const leases = [];
    let scheduledWhileOldRuns;
    runtime.executor.registerHandler('search_like', { execute(params) {
      leases.push(runtime.executor.getCurrentLeaseId());
      if (leases.length === 1) {
        loop[invalidation]();
        loop.pair();
        loop.dispatch(task('same-task', 'new-lease'));
        scheduledWhileOldRuns = loop.pending();
      }
      return { success: true, result: {} };
    } });
    loop.dispatch(task('same-task', 'old-lease'));
    loop.run();
    assert.equal(scheduledWhileOldRuns, 0);
    assert.equal(loop.pending(), 1);
    loop.run();
    assert.deepEqual(leases, ['old-lease', 'new-lease']);
    assert.deepEqual(loop.reports, [{ id: 'same-task', status: 'completed', lease: 'new-lease' }]);
  });

  test(invalidation + ' also retires a reserved task before a replacement session starts', () => {
    const runtime = taskRuntime();
    const loop = mainLoop({ executor: runtime.executor, pairResult: { status: 'approved', config: {} } });
    const leases = [];
    runtime.executor.registerHandler('search_like', { execute() { leases.push(runtime.executor.getCurrentLeaseId()); return { success: true, result: {} }; } });
    loop.dispatch(task('same-task', 'old-lease'));
    loop[invalidation]();
    loop.pair();
    loop.dispatch(task('same-task', 'new-lease'));
    assert.equal(loop.pending(), 1, 'only the old reserved worker may be scheduled until it retires');
    loop.run();
    loop.run();
    assert.deepEqual(leases, ['new-lease']);
    assert.deepEqual(loop.reports, [{ id: 'same-task', status: 'completed', lease: 'new-lease' }]);
  });
}

test('a fresh retry lease does not inherit cancellation from the previous attempt', () => {
  const runtime = taskRuntime();
  const loop = mainLoop({ executor: runtime.executor });
  const actions = [];
  runtime.executor.registerHandler('search_like', { execute() { actions.push(runtime.executor.getCurrentLeaseId()); return { success: true, result: {} }; } });
  loop.dispatch(task());
  loop.cancel('task');
  loop.run();
  let delivered = false;
  loop.api.poll = () => delivered ? null : (delivered = true, { device_config: {}, task: task('task', 'lease-two') });
  loop.connect();
  loop.run();
  assert.deepEqual(actions, ['lease-two']);
  assert.deepEqual(loop.reports.map(report => [report.status, report.lease]), [['cancelled', 'lease-one'], ['completed', 'lease-two']]);
});

function comments(runtime) {
  const reply = runtime.load('handlers/reply-comment');
  runtime.load('handlers/comment-utils').localPreFilter = () => true;
  reply._parseCommentItem = () => ({ nickname: 'nick', text: 'long comment' });
  reply._filterByTime = value => value;
  runtime.ui.findElements = () => [{}];
  runtime.executor.registerHandler('reply_comment', { execute(params) {
    const stats = reply._initStats();
    reply._processComments(params, stats, 0);
    return { success: true, result: stats };
  } });
  return reply;
}

test('a comment analysis returning after cancel cannot reach reply or follow', () => {
  const runtime = taskRuntime();
  const reply = comments(runtime);
  const actions = [];
  runtime.analyzer.analyzeComment = () => {
    runtime.executor.cancel('task');
    return { score: 90, tier: 'high', reply: 'generated reply' };
  };
  reply._replyToComment = () => { actions.push('reply'); return true; };
  reply._followUser = () => { actions.push('follow'); return true; };
  const result = runtime.executor.execute(task('task', 'lease-one', 'reply_comment', { keyword: 'query', count: 1, max_age_seconds: -1 }));
  assert.deepEqual(actions, []);
  assert.deepEqual(runtime.calls.releases, [['nick', 'long comment']], 'a claim without a submission can be released');
  assert.equal(result.status, 'cancelled');
});

for (const failure of ['empty', 'exception']) {
  test('a comment claim is retryable after ' + failure + ' analysis before any submission', () => {
    const runtime = taskRuntime();
    const reply = comments(runtime);
    let claimed = false, sends = 0;
    runtime.api.claimCommentReply = () => {
      if (claimed) return { claimed: false };
      claimed = true;
      return { claimed: true };
    };
    runtime.api.releaseCommentReply = () => { claimed = false; };
    runtime.analyzer.analyzeComment = () => {
      if (failure === 'exception') throw Error('analysis unavailable');
      return null;
    };
    reply._replyToComment = () => { sends++; reply._lastSendOutcome = 'confirmed'; return true; };
    runtime.executor.execute(task('first', 'first-lease', 'reply_comment', { keyword: 'query', count: 1, max_age_seconds: -1 }));
    assert.equal(claimed, false, 'failed analysis must not permanently occupy an unsent comment');
    assert.equal(sends, 0);
    runtime.analyzer.analyzeComment = () => ({ score: 90, tier: 'low', reply: 'retry reply' });
    runtime.executor.execute(task('retry', 'retry-lease', 'reply_comment', { keyword: 'query', count: 1, max_age_seconds: -1 }));
    assert.equal(sends, 1);
    assert.equal(claimed, true, 'confirmed sends retain the dedup claim');
  });
}

test('DM sequence cancellation after a confirmed send stops later messages without resetting its outcome', () => {
  const runtime = taskRuntime();
  const search = runtime.load('handlers/search-base');
  const sends = [];
  runtime.load('handlers/comment-utils').submitAndObserve = (action, input, content) => {
    sends.push(content);
    runtime.executor.cancel('task');
    return 'confirmed';
  };
  runtime.ui.findElement = () => ({});
  runtime.executor.registerHandler('search_dm', { execute() {
    const sent = search._sendMessageSequence([{ content: 'one', delay_ms: 10000 }, { content: 'two' }], { details: [] }, 'query');
    return { success: true, result: { sent } };
  } });
  const result = runtime.executor.execute(task('task', 'lease-one', 'search_dm'));
  assert.deepEqual(sends, ['one']);
  assert.equal(search._lastSendOutcome, 'confirmed');
  assert.equal(result.status, 'cancelled');
});

test('DM cancellation during input delay never reaches the submit boundary', () => {
  const runtime = taskRuntime();
  const search = runtime.load('handlers/search-base');
  const sends = [];
  search.safeInput = () => { runtime.cancellation.cancel(); return true; };
  runtime.load('handlers/comment-utils').submitAndObserve = (action, input, content) => { sends.push(content); return 'confirmed'; };
  const sent = search._sendMessageSequence([{ content: 'one' }], { details: [] }, 'query');
  assert.equal(sent, 0);
  assert.deepEqual(sends, []);
  assert.equal(search._lastSendOutcome, 'not_attempted');
});

test('cancellation while resolving a send button leaves the comment claim releasable', () => {
  const runtime = taskRuntime();
  runtime.ui.findElement = action => {
    if (action === 'comment_submit') runtime.cancellation.cancel();
    return {};
  };
  const outcome = runtime.load('handlers/comment-utils').submitAndObserve('comment_submit', 'comment_input', 'reply', 'comment_send_failed');
  assert.equal(outcome, 'not_attempted');
  assert.deepEqual(runtime.calls.clicks, []);
});

test('cancellation after an attempted send preserves unknown and does not retry', () => {
  const runtime = taskRuntime();
  runtime.ui.findElement = () => ({});
  runtime.ui.clickAction = action => { runtime.calls.clicks.push(action); runtime.cancellation.cancel(); return false; };
  const outcome = runtime.load('handlers/comment-utils').submitAndObserve('dm_send', 'dm_input', 'message', 'dm_send_failed');
  assert.equal(outcome, 'unknown');
  assert.deepEqual(runtime.calls.clicks, ['dm_send']);
});

test('cancellation during anti-detection delay stops a pending like or follow click', () => {
  const runtime = taskRuntime();
  runtime.ui.findElement = () => ({});
  runtime.antiDetect.wrapAction = (action, fn) => { runtime.cancellation.cancel(); return fn(); };
  assert.equal(runtime.load('handlers/base-handler').safeClick('follow_button'), false);
  assert.deepEqual(runtime.calls.clicks, []);
});

test('a direct follow lookup completing after cancel cannot click the fresh button', () => {
  const runtime = taskRuntime();
  runtime.ui.findElement = action => {
    if (action === 'user_nickname') return {};
    if (action === 'follow_button') { runtime.cancellation.cancel(); return { text: () => '关注' }; }
    return null;
  };
  assert.equal(runtime.load('handlers/reply-comment')._followUser(), false);
  assert.deepEqual(runtime.calls.clicks, []);
});

test('search comment submission failure is not counted as a successful interaction', () => {
  const runtime = taskRuntime();
  runtime.ui.findElement = () => ({});
  runtime.ui.submitViaKeyboard = () => false;
  runtime.load('handlers/comment-utils').preCheckCommentCount = () => ({ count: 1, rawDesc: '1' });
  const stats = { details: [] };
  assert.equal(runtime.load('handlers/search-comment')._interactWithVideo('provided comment', stats), false);
  assert.deepEqual(runtime.calls.stats, []);
  assert.deepEqual(stats.details, []);
});

test('search comment generation returning after cancel cannot start a submission', () => {
  const runtime = taskRuntime();
  runtime.ui.findElement = () => ({});
  runtime.load('handlers/comment-utils').preCheckCommentCount = () => ({ count: 1, rawDesc: '1' });
  runtime.analyzer.generateVideoComment = () => { runtime.cancellation.cancel(); return 'late reply'; };
  const handler = runtime.load('handlers/search-comment');
  handler._extractVideoText = () => 'video';
  assert.equal(handler._interactWithVideo('', { details: [] }), false);
  assert.deepEqual(runtime.calls.clicks, []);
  assert.deepEqual(runtime.calls.stats, []);
});

test('final node actuation checks cancellation after the live geometry read', () => {
  const runtime = taskRuntime();
  const ui = runtime.loadUI();
  let clicks = 0;
  const node = { clickable: () => true, click() { clicks++; return true; } };
  const read = runtime.geometry.read;
  runtime.geometry.read = () => { runtime.cancellation.cancel(); return read(); };
  ui._liveScopeForElement = () => ({ region: read().contentBounds });
  ui._isOnScreen = () => true;
  assert.equal(ui.clickElement(node), false);
  assert.equal(clicks, 0);
});

test('a cancelled task cannot submit an Enter key or fall back to a button', () => {
  const runtime = taskRuntime();
  const ui = runtime.loadUI();
  runtime.cancellation.cancel();
  assert.equal(ui.submitViaKeyboard('comment_submit'), false);
  assert.deepEqual(runtime.calls.shells, []);
});

test('collection avatar navigation honors a rejected scoped click', () => {
  const runtime = taskRuntime();
  const handler = runtime.load('handlers/search-collect');
  let rawClicks = 0, profiles = 0;
  handler._findChildBySelector = () => ({ bounds: () => ({}), clickable: () => true, click() { rawClicks++; return true; } });
  runtime.load('handlers/comment-utils')._cropCircularAvatar = () => null;
  runtime.load('handlers/comment-utils').collectProfileData = () => { profiles++; return {}; };
  runtime.ui.clickElement = () => false;
  assert.equal(handler._collectUserData({}), null);
  assert.equal(rawClicks, 0);
  assert.equal(profiles, 0);
});

for (const method of ['_likeCurrentVideo', '_followCurrentUser', '_commentOnVideo']) {
  test('nurture ' + method + ' does not act on an AI result received after cancellation', () => {
    const runtime = taskRuntime();
    const handler = runtime.load('handlers/nurture');
    handler._isAdContent = () => false;
    handler._isKeywordRelevant = () => true;
    handler._extractVideoText = () => 'video';
    runtime.analyzer.checkHealthRelevance = () => { runtime.cancellation.cancel(); return true; };
    runtime.analyzer.generateVideoComment = () => { runtime.cancellation.cancel(); return 'late comment'; };
    runtime.ui.findElement = () => ({});
    runtime.load('handlers/comment-utils').preCheckCommentCount = () => ({ count: 1, rawDesc: '1' });
    assert.equal(handler[method](), false);
    assert.deepEqual(runtime.calls.clicks, []);
  });
}

test('collection analysis received after cancellation cannot navigate to a profile or report new data', () => {
  const runtime = taskRuntime();
  const handler = runtime.load('handlers/search-collect');
  const utils = runtime.load('handlers/comment-utils');
  const actions = [];
  utils.parseCommentItem = () => ({ nickname: 'nick', text: 'long comment', time: 'just now' });
  utils.localPreFilter = () => true;
  utils.parseTime = () => new Date();
  runtime.ui.findElements = () => [{}];
  runtime.analyzer.analyzeComment = () => { runtime.cancellation.cancel(); return { score: 90 }; };
  handler._collectCommentData = () => ({});
  handler._collectUserData = () => { actions.push('profile'); return {}; };
  handler._reportCollection = () => actions.push('report');
  handler._openComments = () => true;
  handler._processComments({ keyword: 'query', count: 1, max_age_seconds: -1 }, { success_count: 0, details: [] }, 0);
  assert.deepEqual(actions, []);
});

test('share-link collection stops opening further links after cancellation', () => {
  const runtime = taskRuntime();
  const handler = runtime.load('handlers/search-collect');
  let opened = 0;
  handler._openSearch = () => { opened++; runtime.cancellation.cancel(); return true; };
  handler._submitSearch = () => true;
  handler._backToSearchResults = () => {};
  runtime.load('handlers/comment-utils').openComments = () => false;
  handler._executeShareLinks({ share_links: ['https://v.douyin.com/one/', 'https://v.douyin.com/two/'] });
  assert.equal(opened, 1);
});
