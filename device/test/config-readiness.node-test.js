const assert = require('node:assert/strict');
const { test } = require('node:test');
const mainLoop = require('./helpers/main-loop');

const enabledConfig = { decision_config: { enabled: true, model: 'typesafe-ai/jev', min_confidence: 0, min_probability: 0 } };
const task = { id: 'chain-task', type: 'reply_comment', lease_id: 'lease-one' };

test('direct startup pushes wait for an authoritative config when register and polls fail', () => {
  const loop = mainLoop({ register: () => null, poll: () => null, wsStart(h) { h.connect(); h.dispatch(task); } });
  assert.equal(loop.pending(), 0, 'no task thread is allowed to classify with the default disabled flag');
  assert.equal(loop.executed.length, 0);
  assert.equal(loop.context._mainLoopRuntime.isIdle(), false, 'a blocked queue is not idle');
});

test('a blocked startup queue continues polling and releases a task once when configuration recovers', () => {
  let recovered = false;
  const loop = mainLoop({ register: () => null,
    poll: () => recovered ? { device_config: enabledConfig, task } : null,
    wsStart(h) { h.dispatch(task); h.dispatch(task); },
  });
  const initialPolls = loop.polls();
  for (let n = 0; n < 6; n++) loop.tick();
  assert.equal(loop.polls(), initialPolls + 6);
  assert.equal(loop.closedApps(), 0, 'configuration retry must not count a queued task as idle');
  recovered = true;
  loop.tick();
  assert.equal(loop.pending(), 1);
  loop.run();
  loop.tick();
  assert.equal(loop.pending(), 0, 'the poll replay remains deduplicated after release');
  assert.equal(loop.executed.length, 1);
  assert.deepEqual(loop.executed[0].decision, enabledConfig.decision_config);
  assert.equal(loop.reports[0].lease, 'lease-one');
});

test('partial WebSocket config cannot establish readiness but explicit decision config can', () => {
  const loop = mainLoop({ register: () => null, poll: () => null });
  loop.dispatch(task);
  loop.update({ poll_interval: 1234 });
  assert.equal(loop.pending(), 0);
  assert.equal(loop.config.pollInterval, 1234);
  loop.update(enabledConfig);
  assert.equal(loop.pending(), 1);
  loop.run();
  assert.deepEqual(loop.executed[0].decision, enabledConfig.decision_config);
});

test('config arriving during selector initialization cannot run a task before both loaders finish', () => {
  let scheduledDuringInitialization;
  const loop = mainLoop({ register: () => null,
    duringSelectorInit(h) {
      h.dispatch(task);
      h.update(enabledConfig);
      scheduledDuringInitialization = h.pending();
    },
  });
  assert.equal(scheduledDuringInitialization, 0);
  assert.equal(loop.pending(), 1);
  loop.run();
  assert.equal(loop.executed[0].selectorsReady, true);
  assert.equal(loop.executed[0].templatesReady, true);
  assert.equal(loop.executed[0].decision.enabled, true);
});

test('pairing config is available to the first push before registration has returned', () => {
  const loop = mainLoop({ initialConfig: enabledConfig, register: () => null,
    immediateThreads: true, wsStart(h) { h.dispatch(task); },
  });
  assert.equal(loop.executed.length, 1);
  assert.deepEqual(loop.executed[0].decision, enabledConfig.decision_config);
  assert.ok(loop.events.indexOf('execute:chain-task') < loop.events.indexOf('register'));
});

test('every approved pairing branch passes its authoritative configuration to the main loop', () => {
  for (const entry of ['request', 'wait', 'poll', 'retry', 'auth', 'removed']) {
    const loop = mainLoop({ autoStart: false, pairResult: { status: 'approved', config: enabledConfig },
      register: () => null, poll: () => null, immediateThreads: true,
      wsStart(h) { h.dispatch({ ...task, id: entry }); },
    });
    if (entry === 'request') { loop.context.startPairingFlow(); loop.pair(); }
    if (entry === 'wait') loop.context.startPairingWait();
    if (entry === 'poll') { loop.context.startPairingPoll(); loop.tick(5000); }
    if (entry === 'retry') {
      loop.context.startPairingPoll(); loop.advance(300001); loop.tick(5000); loop.timeout(2000); loop.pair();
    }
    if (entry === 'auth' || entry === 'removed') {
      loop.start();
      if (entry === 'auth') loop.authFail(); else loop.remove();
      loop.pair();
    }
    assert.equal(loop.executed.length, 1, entry);
    assert.deepEqual(loop.executed[0].decision, enabledConfig.decision_config, entry);
  }
});

test('successful older-server registration and polling authorize legacy mode without stale decisions', () => {
  for (const channel of ['register', 'poll', 'pair']) {
    const loop = mainLoop({ previousDecision: { enabled: true, model: 'old-server', min_confidence: 1, min_probability: 1 },
      initialConfig: channel === 'pair' ? {} : undefined,
      register: () => channel === 'register' ? { device_id: 'unit-device', config: { poll_interval: 30000 } } : null,
      poll: () => channel === 'poll' ? { task: null, device_config: {} } : null,
      wsStart(h) { h.dispatch(task); },
    });
    assert.equal(loop.pending(), 1, channel);
    loop.run();
    assert.deepEqual(loop.executed[0].decision, {
      enabled: false, model: 'typesafe-ai/jev', min_confidence: 0.5, min_probability: 0.75,
    }, channel);
  }
});

test('explicit disable and numeric zero remain authoritative in startup config', () => {
  const decision = { enabled: false, model: 'typesafe-ai/jev', min_confidence: 0, min_probability: 0 };
  const loop = mainLoop({ initialConfig: { decision_config: decision }, register: () => null, wsStart(h) { h.dispatch(task); } });
  loop.run();
  assert.deepEqual(loop.executed[0].decision, decision);
});

test('a cancellation accompanying recovered config removes the queued task before release', () => {
  let recovered = false;
  const loop = mainLoop({ register: () => null,
    poll: () => recovered ? { device_config: enabledConfig, cancelled_task_id: task.id } : null,
    wsStart(h) { h.dispatch(task); },
  });
  recovered = true;
  loop.tick();
  assert.equal(loop.pending(), 0);
  assert.equal(loop.executed.length, 0);
  assert.equal(loop.reports.length, 1);
  assert.equal(loop.reports[0].id, task.id);
  assert.equal(loop.reports[0].status, 'cancelled');
});

test('cancellation during recovery poll rejects its already-claimed task while retaining configuration', () => {
  const unleased = { id: 'chain-task', type: 'reply_comment' };
  const loop = mainLoop({ register: () => null, wsStart(h) { h.dispatch(unleased); } });
  loop.api.poll = () => {
    // The server has claimed a lease and formed this task before its awaited
    // broadcast. The cancellation arrives over WS before HTTP returns it.
    const response = { device_config: enabledConfig, task: { ...unleased, lease_id: 'poll-lease' } };
    loop.cancel(unleased.id);
    return response;
  };
  loop.tick();
  assert.equal(loop.pending(), 0, 'a stale poll must not resurrect the cancelled chain push');
  assert.equal(loop.executed.length, 0);
  assert.equal(loop.config.decision.enabled, true, 'valid config can still recover readiness');
  assert.deepEqual(loop.reports.map(report => report.status), ['cancelled']);
});

test('late unleased WS replays after cancellation require fresh server confirmation', () => {
  const unleased = { id: 'chain-task', type: 'reply_comment' };
  const loop = mainLoop({ register: () => null, wsStart(h) { h.dispatch(unleased); } });
  loop.cancel(unleased.id);
  loop.update(enabledConfig);
  loop.dispatch(unleased);
  loop.dispatch({ ...unleased, lease_id: 'cancelled-poll-lease' });
  assert.equal(loop.pending(), 0);
  assert.equal(loop.executed.length, 0);
  assert.deepEqual(loop.reports.map(report => report.status), ['cancelled']);
});

test('fresh authoritative polling permits a new retry lease after cancellation and ignores old WS replays', () => {
  const unleased = { id: 'chain-task', type: 'reply_comment' };
  const loop = mainLoop({ register: () => null, wsStart(h) { h.dispatch(unleased); } });
  loop.cancel(unleased.id);
  loop.api.poll = () => ({ device_config: enabledConfig, task: { ...unleased, lease_id: 'retry-lease' } });
  loop.tick();
  assert.equal(loop.pending(), 1, 'cancellation must not permanently blacklist the task ID');
  loop.run();
  assert.deepEqual(loop.executed.map(item => item.lease_id), ['retry-lease']);
  assert.deepEqual(loop.reports.map(report => report.status), ['cancelled', 'completed']);
  assert.equal(loop.reports[1].lease, 'retry-lease');
  loop.api.poll = () => ({ device_config: enabledConfig, task: null });
  loop.dispatch(unleased);
  assert.equal(loop.pending(), 0, 'a no-lease replay must not start again after the retry finishes');
});

test('an unrelated cancellation preserves immediate delivery of work already claimed by an in-flight poll', () => {
  const loop = mainLoop({ register: () => null });
  let firstPoll = true;
  loop.api.poll = () => {
    if (firstPoll) {
      firstPoll = false;
      loop.cancel('another-task');
    }
    return { device_config: enabledConfig, task };
  };
  loop.tick();
  assert.equal(loop.pending(), 1);
  loop.run();
  assert.deepEqual(loop.executed.map(item => item.lease_id), ['lease-one']);
});

test('authentication failure or device removal prevents a late config from releasing an old queue', () => {
  for (const reason of ['auth', 'removed']) {
    const loop = mainLoop({ register: () => null, wsStart(h) { h.dispatch(task); } });
    if (reason === 'auth') loop.authFail(); else loop.remove();
    loop.update(enabledConfig);
    loop.dispatch({ ...task, id: 'late-task' });
    assert.equal(loop.pending(), 0, reason);
    assert.equal(loop.executed.length, 0, reason);
  }
});

test('idle app closing still waits six idle polling intervals after readiness', () => {
  const loop = mainLoop();
  for (let n = 0; n < 5; n++) loop.tick();
  assert.equal(loop.closedApps(), 0);
  loop.tick();
  assert.equal(loop.closedApps(), 1);
});
