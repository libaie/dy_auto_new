const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('new device claims request a persistent hold for an unknown send outcome', () => {
  const sandbox = { module: { exports: {} }, global: { __config: {} }, require: () => ({}) };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../core/api-client.js'), 'utf8'), sandbox);
  const api = sandbox.module.exports;
  let submitted;
  api.post = (url, data) => { submitted = JSON.parse(JSON.stringify(data)); return { claimed: true }; };
  const original = { account_id: 'account', recipient_douyin_id: 'recipient', recipient_nickname: 'Test' };
  api.claimDMRecipient(original);
  assert.equal(submitted.preserve_on_unknown, true);
  assert.equal(original.preserve_on_unknown, undefined);
  assert.equal(submitted.recipient_douyin_id, 'recipient');
});
