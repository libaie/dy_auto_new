const assert = require('node:assert/strict');
const { test } = require('node:test');
const mainLoop = require('./helpers/main-loop');

test('main accepts a new retry lease after completing the same task ID', () => {
  const loop = mainLoop();
  loop.dispatch({ id: 'task', type: 'search_like', lease_id: 'attempt-one' });
  loop.run();
  loop.dispatch({ id: 'task', type: 'search_like', lease_id: 'attempt-two' });
  assert.equal(loop.pending(), 1);
  loop.run();
  assert.deepEqual(loop.executed.map(task => task.lease_id), ['attempt-one', 'attempt-two']);
});

test('main rejects completed-attempt replays and concurrent leases for one task', () => {
  const loop = mainLoop();
  const first = { id: 'task', type: 'search_like', lease_id: 'attempt-one' };
  loop.dispatch(first);
  loop.dispatch({ ...first, lease_id: 'attempt-two' });
  assert.equal(loop.pending(), 1);
  loop.run();
  loop.dispatch(first);
  assert.equal(loop.pending(), 0);
  assert.equal(loop.executed.length, 1);
});

test('main still deduplicates replayed legacy tasks without a lease', () => {
  const loop = mainLoop();
  const task = { id: 'legacy', type: 'search_like' };
  loop.dispatch(task);
  loop.run();
  loop.dispatch(task);
  assert.equal(loop.pending(), 0);
  assert.equal(loop.executed.length, 1);
});
