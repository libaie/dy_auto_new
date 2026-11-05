const assert = require('node:assert/strict');
const test = require('node:test');
const taskRuntime = require('./helpers/task-runtime');

function deliveryRuntime(mode) {
  const runtime = taskRuntime();
  let submissions = 0;
  let bubbles = 1;
  const bubble = {className:()=> 'android.widget.TextView',bounds:()=>({left:30,top:200,right:300,bottom:250})};
  runtime.context.text = () => ({find:()=>Array.from({length:bubbles},()=>bubble)});
  runtime.ui.findElement = action => {
    if (action === 'video_comment_input') return runtime.edit;
    if (action === 'comment_send_failed') return mode === 'failed' && submissions ? {} : null;
    return {};
  };
  function submit() {
    submissions++;
    if (mode === 'confirmed' || mode === 'new-text-only') bubbles++;
    if (mode === 'confirmed' || mode === 'cleared-only') runtime.edit.value = '';
    return mode !== 'actuation-failed';
  }
  runtime.ui.submitViaKeyboard = submit;
  runtime.ui.clickAction = action => action === 'comment_submit' ? submit() : true;
  runtime.load('handlers/comment-utils').preCheckCommentCount = () => ({count:1,rawDesc:'1'});
  return {runtime, submissions:()=>submissions};
}

for (const mode of ['unchanged', 'new-text-only', 'cleared-only', 'failed', 'actuation-failed', 'confirmed']) {
  test('search comment counts only observed delivery: ' + mode, () => {
    const h = deliveryRuntime(mode);
    const stats = {details:[]};
    const result = h.runtime.load('handlers/search-comment')._interactWithVideo('synthetic comment', stats);
    assert.equal(result, mode === 'confirmed');
    assert.equal(h.runtime.calls.stats.length, mode === 'confirmed' ? 1 : 0);
    assert.equal(h.submissions(), 1, 'never resubmit an unconfirmed comment');
  });
}

test('an unknown send stops the current search before another video interaction', () => {
  const runtime = taskRuntime();
  const handler = runtime.load('handlers/search-base');
  let interactions = 0;
  handler._interactWithVideo = function () { interactions++; this._lastSendOutcome = 'unknown'; return false; };
  const result = handler.execute({keyword:'synthetic',video_count:3});
  assert.equal(interactions,1);
  assert.equal(result.result.success_count,0);
  assert.equal(result.result.fail_count,1);
});

test('cancellation during page detection cannot dispatch the center press fallback', () => {
  const runtime = taskRuntime();
  let presses=0;
  runtime.context.press=()=>{presses++;return true;};
  runtime.ui.isOnPage=()=>{runtime.cancellation.cancel();return false;};
  assert.equal(runtime.load('handlers/search-comment')._interactWithVideo('synthetic', {details:[]}),false);
  assert.equal(presses,0);
});
