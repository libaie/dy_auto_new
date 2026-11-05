const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const root = path.resolve(__dirname, '..');
const params = { searchKeyword: '睡眠习惯', nickname: '测试用户', commentText: '最近总是晚上醒来，日常作息有什么要注意的？' };
const plain = value => JSON.parse(JSON.stringify(value));

function choiceAnswer(criteria, selected, probability = 0.9) {
  const keys = Object.keys(criteria);
  if (keys.length === 1) probability = 1;
  const probabilities = {};
  for (const key of keys) probabilities[key] = key === selected ? probability : (1 - probability) / (keys.length - 1);
  return { type: 'choice', choice: selected, confidence: 0.8, probabilities };
}

function scoreAnswer(criteria, rawScore, confidence = 0.8) {
  const legend = {};
  const probabilities = {};
  for (let i = 0; i < criteria.length; i++) {
    legend[String(i)] = criteria[i];
    probabilities[String(i)] = 0;
  }
  const lower = Math.floor(rawScore);
  const upper = Math.ceil(rawScore);
  probabilities[String(lower)] = upper === lower ? 1 : upper - rawScore;
  if (upper !== lower) probabilities[String(upper)] = rawScore - lower;
  return { type: 'score', score: rawScore, confidence, legend, probabilities };
}

function nativeResponse(body) {
  const answers = {};
  for (const key of Object.keys(body.questions)) {
    const question = body.questions[key];
    if (question.type === 'score') {
      answers[key] = scoreAnswer(question.criteria, key === 'lead_score' ? 6.75 : 7);
    } else if (question.type === 'choice') {
      let selected = key === 'intent' ? 'health_consult' : key === 'sentiment' ? 'neutral' : 'quality';
      if (!Object.hasOwn(question.criteria, selected)) selected = Object.keys(question.criteria)[0];
      answers[key] = choiceAnswer(question.criteria, selected);
    } else {
      answers[key] = { type: 'noul', noul: key === 'is_bot' || key === 'is_competitor' ? 0.02 : 0.96 };
    }
  }
  return { model: 'jev-1.13.0', answers };
}

function runtime(options = {}) {
  const calls = [];
  const logs = [];
  let now = 1000;
  const cache = new Map();
  const logger = Object.fromEntries(['info', 'warn', 'error', 'debug'].map(level => [level, (...args) => logs.push(args.join(' '))]));
  const overrides = {
    'utils/logger.js': logger,
    'handlers/base-handler.js': {},
    'handlers/comment-base.js': {},
    'core/ui-operator.js': {},
    'core/anti-detect.js': {},
    'handlers/comment-utils.js': {},
    'core/flow-context.js': {},
  };
  const storage = new Map([['device_id', 'unit-device']]);
  const sandbox = vm.createContext({
    global: {}, console,
    Date: class extends Date { static now() { return now; } },
    storages: { create() { return { get(key, fallback) { return storage.has(key) ? storage.get(key) : fallback; }, put(key, value) { storage.set(key, value); } }; } },
    sleep(ms) { now += ms; },
  });
  function load(relativePath) {
    let filename = path.resolve(root, relativePath);
    if (!path.extname(filename)) filename += '.js';
    const rel = path.relative(root, filename);
    if (Object.hasOwn(overrides, rel)) return overrides[rel];
    if (cache.has(filename)) return cache.get(filename).exports;
    const module = { exports: {} };
    cache.set(filename, module);
    const wrapper = vm.runInContext('(function(require, module, exports) {\n' + fs.readFileSync(filename, 'utf8') + '\n})', sandbox, { filename });
    wrapper(request => load(path.relative(root, path.resolve(path.dirname(filename), request))), module, module.exports);
    return module.exports;
  }
  const config = load('config.js');
  config.serverUrl = 'https://unit.invalid';
  config.deviceSecret = 'unit-device-secret';
  config.network = { maxRetries: 3, requestTimeout: 1000, retryBaseDelay: 1, retryMaxDelay: 1, offlineQueueMax: 100 };
  config.decision = Object.assign({ enabled: true, model: 'typesafe-ai/jev', min_confidence: 0.5, min_probability: 0.75 }, options.decision || {});
  sandbox.http = {
    get(url, requestOptions) {
      calls.push({ url, requestOptions });
      return { statusCode: 200, body: JSON.stringify(options.poll || { task: null, device_config: {} }) };
    },
    postJson(url, body, requestOptions) {
      calls.push({ url, body: plain(body), requestOptions: plain(requestOptions) });
      if (url.endsWith('/decision-proxy')) {
        now += options.elapsed || 0;
        if (options.error) throw new Error(options.error);
        if (options.status) return { statusCode: options.status, body: 'sensitive upstream detail' };
        const response = nativeResponse(body);
        if (options.mutate) options.mutate(response, body);
        return { statusCode: 200, body: { string() { return options.rawResponse === undefined ? JSON.stringify(response) : options.rawResponse; } } };
      }
      if (url.endsWith('/ai-proxy')) {
        return { statusCode: 200, body: JSON.stringify({ content: options.generation === undefined ? '可以先记录作息和夜醒情况，方便发现规律' : options.generation }) };
      }
      throw new Error('Unexpected HTTP route: ' + url);
    },
  };
  const analyzer = load('core/ai-analyzer.js');
  function applyServerConfig(serverConfig) {
    const source = fs.readFileSync(path.join(root, 'main.js'), 'utf8');
    const start = source.indexOf('function applyServerConfig(serverConfig) {');
    const end = source.indexOf('\n// 启动', start);
    assert.ok(start >= 0 && end > start, 'main config function can be executed without AutoJS JSX');
    sandbox.config = config;
    sandbox.logger = logger;
    sandbox.TAG = '测试';
    sandbox.antiDetect = { updateFromServer() {} };
    sandbox._startIdlePoll = function () {};
    vm.runInContext(source.slice(start, end), sandbox);
    sandbox.applyServerConfig(serverConfig);
  }
  return { analyzer, config, load, calls, logs, applyServerConfig, decisionCalls: () => calls.filter(c => c.url.endsWith('/decision-proxy')), generationCalls: () => calls.filter(c => c.url.endsWith('/ai-proxy')) };
}

// Catches sending Jev through the generation proxy, wrong native question shapes,
// incorrect score normalization, profile inference, and reply overwrites.
test('Jev analysis uses one native request and preserves decisions while generating a reply', () => {
  const h = runtime({ generation: '{"score":1,"tier":"low","dimensions":{"intent":"other"},"reply":"建议先记录作息规律"}' });
  h.config.proxy = { type: 'http', host: 'proxy.invalid', port: 8080 };
  const result = h.analyzer.analyzeComment(params);
  assert.equal(h.decisionCalls().length, 1);
  assert.equal(h.generationCalls().length, 1);
  assert.equal(result.score, 75);
  assert.equal(result.tier, 'high');
  assert.equal(result.reply, '建议先记录作息规律');
  assert.deepEqual(plain(result.dimensions), {
    intent: 'health_consult', sentiment: 'neutral', focus: 'quality',
    profile: { role: 'unknown', spending: 'mid' },
    lead_quality: { urgency: 8, specific_condition: true, is_bot: false, is_competitor: false },
  });
  const request = h.decisionCalls()[0];
  assert.deepEqual(Object.keys(request.body).sort(), ['questions', 'state']);
  assert.equal(request.requestOptions.timeout, 25000);
  assert.equal(request.requestOptions.headers['X-Device-Secret'], 'unit-device-secret');
  assert.equal(request.requestOptions.proxy, 'http://proxy.invalid:8080');
  assert.ok(!JSON.stringify(request.body).includes('unit-device-secret'));
  assert.equal(request.body.state.comment.text, params.commentText);
  assert.deepEqual(Object.keys(request.body.questions.intent.criteria), ['strong_buy', 'health_consult', 'patient_self', 'other']);
  assert.equal(request.body.questions.lead_score.type, 'score');
  assert.equal(request.body.questions.lead_score.criteria.length, 10);
  for (const question of Object.values(request.body.questions)) {
    assert.ok(typeof question.instructions === 'string' && question.instructions.length > 15);
    assert.ok(!['role', 'spending', 'age', 'gender'].includes(question.instructions));
    assert.ok(['choice', 'score', 'noul'].includes(question.type));
  }
  const prompt = h.generationCalls()[0].body.prompt;
  assert.match(prompt, /75/);
  assert.match(prompt, /health_consult/);
  assert.match(prompt, /回复生成规则/);
  assert.match(prompt, /绝对禁用词/);
});

test('fractional native score is normalized before rounding at the existing tier boundaries', () => {
  for (const fixture of [
    { raw: 3.51, score: 39, tier: 'low' }, { raw: 3.6, score: 40, tier: 'medium' },
    { raw: 6.21, score: 69, tier: 'medium' }, { raw: 6.3, score: 70, tier: 'high' },
    { raw: 6.75, score: 75, tier: 'high' }, { raw: 9, score: 100, tier: 'high' },
  ]) {
    const h = runtime({ mutate(response, body) { response.answers.lead_score = scoreAnswer(body.questions.lead_score.criteria, fixture.raw); } });
    const result = h.analyzer.analyzeComment({ ...params, generateReply: false });
    assert.equal(result && result.score, fixture.score, JSON.stringify(fixture));
    assert.equal(result.tier, fixture.tier);
    assert.equal(result.reply, '');
    assert.equal(h.generationCalls().length, 0);
  }
});

test('active industry template supplies intent candidates and the analysis context', () => {
  const h = runtime();
  h.analyzer.setIndustry('travel');
  const result = h.analyzer.analyzeComment({ ...params, commentText: '想去云南，行程怎么安排？', generateReply: false });
  assert.ok(result);
  const request = h.decisionCalls()[0].body;
  assert.deepEqual(Object.keys(request.questions.intent.criteria), ['strong_buy', 'travel_consult', 'other']);
  assert.match(JSON.stringify(request.state.analysis.intents), /目的地/);
  assert.deepEqual(request.state.analysis.scoringRules, plain(h.load("core/prompts-config.js").get().analysis.scoringRules));
  assert.match(JSON.stringify(request.state.semanticGuide), /出行/);
  assert.match(request.questions.intent.instructions, /意图/);
  assert.match(request.questions.is_bot.instructions, /机器人|水军/);
  assert.match(request.questions.is_competitor.instructions, /同行|竞争/);
});

test('malformed or uncertain native answers fail closed without generation or classification fallback', () => {
  const cases = [
    ['missing model', r => { delete r.model; }],
    ['missing answer', r => { delete r.answers.is_bot; }],
    ['wrong type', r => { r.answers.intent.type = 'noul'; }],
    ['score outside scale', r => { r.answers.lead_score.score = 10; }],
    ['nonfinite score', r => { r.answers.lead_score.score = Infinity; }],
    ['uncertain score', r => { r.answers.lead_score.confidence = 0.49; }],
    ['missing score confidence', r => { delete r.answers.lead_score.confidence; }],
    ['missing legend', r => { delete r.answers.lead_score.legend; }],
    ['incomplete score distribution', r => { delete r.answers.lead_score.probabilities['0']; }],
    ['bad score distribution total', r => { r.answers.lead_score.probabilities['0'] = 0.8; }],
    ['unknown intent', r => { r.answers.intent.choice = 'unknown_intent'; }],
    ['missing choice confidence', r => { delete r.answers.intent.confidence; }],
    ['uncertain chosen intent despite high confidence', r => { r.answers.intent.confidence = 0.99; r.answers.intent.probabilities = { strong_buy: 0.2, health_consult: 0.6, patient_self: 0.1, other: 0.1 }; }],
    ['incomplete choice distribution', r => { delete r.answers.intent.probabilities.other; }],
    ['nonfinite probability', r => { r.answers.intent.probabilities.other = NaN; }],
    ['uncertain bot', r => { r.answers.is_bot.noul = 0.5; }],
    ['uncertain competitor', r => { r.answers.is_competitor.noul = 0.6; }],
    ['untyped boolean', r => { r.answers.is_bot.noul = false; }],
    ['out of range boolean', r => { r.answers.is_bot.noul = -0.1; }],
  ];
  for (const [name, mutate] of cases) {
    const h = runtime({ mutate });
    assert.equal(h.analyzer.analyzeComment(params), null, name);
    assert.equal(h.decisionCalls().length, 1, name);
    assert.equal(h.generationCalls().length, 0, name);
  }
});

test('decision transport never retries and does not expose upstream errors in logs', () => {
  for (const options of [{ error: 'credential-sensitive-value' }, { status: 503 }, { rawResponse: '{not JSON sensitive' }, { elapsed: 25001 }]) {
    const h = runtime(options);
    assert.equal(h.analyzer.analyzeComment(params), null);
    assert.equal(h.decisionCalls().length, 1);
    assert.equal(h.generationCalls().length, 0);
    assert.ok(!h.logs.join('\n').includes('sensitive'));
  }
  const h = runtime({ status: 401 });
  let authFailures = 0;
  h.load('core/api-client').setAuthFailureHandler(() => { authFailures++; });
  assert.equal(h.analyzer.analyzeComment(params), null);
  assert.equal(authFailures, 1);
  assert.equal(h.decisionCalls().length, 1);
});

test('confidence thresholds apply at runtime while a confident false bot answer remains usable', () => {
  const h = runtime();
  assert.ok(h.analyzer.analyzeComment({ ...params, generateReply: false }));
  h.config.decision.min_confidence = 0.81;
  assert.equal(h.analyzer.analyzeComment({ ...params, generateReply: false }), null);
  h.config.decision.min_confidence = 0.5;
  h.config.decision.min_probability = 0.91;
  assert.equal(h.analyzer.analyzeComment({ ...params, generateReply: false }), null);
  const boundary = runtime({ mutate(r) { r.answers.lead_score.confidence = 0.5; r.answers.intent.probabilities = { strong_buy: 0.1, health_consult: 0.75, patient_self: 0.1, other: 0.05 }; r.answers.is_bot.noul = 0.25; } });
  assert.ok(boundary.analyzer.analyzeComment({ ...params, generateReply: false }));
});

test('collection uses decisions without requiring replies and rejects detected bots or competitors', () => {
  const h = runtime({ generation: '' });
  const handler = h.load('handlers/search-collect.js');
  assert.equal(handler._aiQualify({ nickname: '采集测试', text: params.commentText, _keyword: '睡眠' }), true);
  assert.equal(h.decisionCalls().length, 1);
  assert.equal(h.generationCalls().length, 0);
  for (const field of ['is_bot', 'is_competitor']) {
    const excluded = runtime({ mutate(r) { r.answers[field].noul = 0.98; } });
    assert.equal(excluded.load('handlers/search-collect.js')._aiQualify({ text: params.commentText }), false, field);
    assert.equal(excluded.generationCalls().length, 0, field);
  }
});

test('Jev relevance preserves deterministic local matches and rejects uncertainty or unavailable decisions', () => {
  const h = runtime();
  assert.equal(h.analyzer.checkRelevance('今天分享养生方法'), true);
  assert.equal(h.analyzer.checkRelevance('今天教你编程'), false);
  assert.equal(h.analyzer.checkRelevance(''), false);
  assert.equal(h.decisionCalls().length, 0);
  assert.equal(h.analyzer.checkRelevance('听听今天的分享', '生活习惯'), true);
  assert.equal(h.decisionCalls().length, 1);
  assert.deepEqual(h.decisionCalls()[0].body.questions.related.type, 'noul');
  assert.equal(h.decisionCalls()[0].body.state.domain, '生活习惯');
  assert.equal(h.generationCalls().length, 0);
  for (const probability of [0.02, 0.5, 0.74]) {
    const uncertain = runtime({ mutate(r) { r.answers.related.noul = probability; } });
    assert.equal(uncertain.analyzer.checkRelevance('听听今天的分享', '生活习惯'), false);
    assert.equal(uncertain.generationCalls().length, 0);
  }
  const unavailable = runtime({ error: 'offline' });
  assert.equal(unavailable.analyzer.checkRelevance('听听今天的分享'), false);
  assert.equal(unavailable.generationCalls().length, 0);
});

test('nurture model fallback uses Jev with keyword matrix context while keeping local hits', () => {
  const h = runtime({ mutate(r) { if (r.answers.related) r.answers.related.noul = 0.6; } });
  const nurture = h.load('handlers/nurture.js');
  nurture._keywordMatrix = ['古典音乐', '钢琴'];
  assert.equal(nurture._isKeywordRelevant('钢琴练习'), true);
  assert.equal(h.decisionCalls().length, 0);
  assert.equal(nurture._isKeywordRelevant('养生和生活分享'), false);
  assert.equal(h.decisionCalls().length, 1);
  assert.deepEqual(h.decisionCalls()[0].body.state.keywords, ['古典音乐', '钢琴']);
  assert.match(h.decisionCalls()[0].body.state.domain, /古典音乐/);
  assert.equal(h.generationCalls().length, 0);
});

test('poll configuration hot-enables and explicitly disables Jev without copying provider secrets', () => {
  const legacy = { score: 60, tier: 'medium', dimensions: { intent: 'other' }, reply: '旧生成回复' };
  const h = runtime({ decision: { enabled: false }, generation: JSON.stringify(legacy), poll: {
    task: null, device_config: { decision_config: { enabled: true, model: 'typesafe-ai/jev', min_confidence: 0.6, min_probability: 0.8, api_key: 'must-never-copy', api_url: 'https://must-not-use.invalid' } },
  } });
  assert.deepEqual(plain(h.analyzer.analyzeComment(params)), legacy);
  const poll = h.load('core/api-client.js').poll();
  h.applyServerConfig(poll.device_config);
  assert.deepEqual(plain(h.config.decision), { enabled: true, model: 'typesafe-ai/jev', min_confidence: 0.6, min_probability: 0.8 });
  assert.equal(h.analyzer.analyzeComment({ ...params, generateReply: false }).score, 75);
  h.applyServerConfig({ decision_config: { enabled: false, model: 'typesafe-ai/jev', min_confidence: 0.5, min_probability: 0.75 } });
  assert.equal(h.config.decision.enabled, false);
  assert.deepEqual(plain(h.analyzer.analyzeComment(params)), legacy);
  assert.equal(h.decisionCalls().length, 1);
  assert.equal(h.generationCalls().length, 2);
});

test('malformed config fields cannot corrupt valid decision thresholds or silently disable an enabled client', () => {
  const h = runtime();
  h.applyServerConfig({ decision_config: { enabled: 'false', model: '', min_confidence: NaN, min_probability: -1, api_key: 'never-copy' } });
  assert.deepEqual(plain(h.config.decision), { enabled: true, model: 'typesafe-ai/jev', min_confidence: 0.5, min_probability: 0.75 });
  h.applyServerConfig({ decision_config: { enabled: true, model: 'typesafe-ai/jev', min_confidence: 0, min_probability: 1 } });
  assert.equal(h.config.decision.min_confidence, 0);
  assert.equal(h.config.decision.min_probability, 1);
  assert.equal(h.analyzer.analyzeComment({ ...params, generateReply: false }), null);
});

test('disabled Jev preserves legacy analysis and model relevance routing', () => {
  const h = runtime({ decision: { enabled: false }, generation: '{"related":true}' });
  assert.equal(h.analyzer.checkRelevance('听听今天的分享'), true);
  assert.equal(h.analyzer.checkRelevance(''), true);
  const nurture = h.load('handlers/nurture.js');
  nurture._keywordMatrix = ['钢琴'];
  assert.equal(nurture._isKeywordRelevant('今天的分享'), true);
  assert.equal(h.decisionCalls().length, 0);
  assert.equal(h.generationCalls().length, 2);
});


test('custom templates can provide a single native choice while retaining their own intent key', () => {
  const h = runtime();
  const prompts = h.load('core/prompts-config.js');
  const template = plain(prompts.get());
  template.analysis.tiers = { custom_consult: '当前模板的唯一咨询意图' };
  assert.equal(prompts.setOverride(template), true);
  const result = h.analyzer.analyzeComment({ ...params, generateReply: false });
  assert.ok(result);
  assert.equal(result.dimensions.intent, 'custom_consult');
  assert.deepEqual(h.decisionCalls()[0].body.questions.intent.criteria, template.analysis.tiers);
});

test('enabled analysis fails closed on unusable template data and never falls back to legacy analysis', () => {
  const h = runtime();
  const prompts = h.load('core/prompts-config.js');
  const template = plain(prompts.get());
  template.identity.constraints = null;
  assert.equal(prompts.setOverride(template), true);
  assert.equal(h.analyzer.analyzeComment(params), null);
  assert.equal(h.generationCalls().length, 0);
});

test('reply-comment consumes Jev decisions and checks scores and exclusions before the send boundary', () => {
  for (const scenario of ['qualified', 'low_score', 'bot', 'competitor']) {
    const h = runtime({ mutate(response, body) {
      if (scenario === 'low_score') response.answers.lead_score = scoreAnswer(body.questions.lead_score.criteria, 3);
      if (scenario === 'bot') response.answers.is_bot.noul = 0.98;
      if (scenario === 'competitor') response.answers.is_competitor.noul = 0.98;
    } });
    const ui = h.load('core/ui-operator.js');
    const utils = h.load('handlers/comment-utils.js');
    const api = h.load('core/api-client.js');
    const handler = h.load('handlers/reply-comment.js');
    let sent = 0;
    ui.findElements = () => [{}];
    ui.findElement = () => null;
    utils.localPreFilter = () => true;
    utils.toBeijingTime = () => '';
    h.load('core/anti-detect.js').maybePause = () => {};
    api.claimCommentReply = () => ({ claimed: true });
    api.incrementStats = () => {};
    api.saveCommentAIReply = () => {};
    api.collectReport = () => {};
    handler._storageGet = () => 0;
    handler._storageSet = () => {};
    handler._parseCommentItem = () => ({ nickname: params.nickname, text: params.commentText });
    handler._filterByTime = comments => comments;
    handler._replyToComment = reply => { assert.equal(reply, '可以先记录作息和夜醒情况，方便发现规律'); sent++; return true; };
    const stats = handler._initStats();
    handler._processComments({ keyword: '睡眠习惯', count: 1, max_age_seconds: -1, max_follows: 0, max_dms: 0 }, stats, 0);
    assert.equal(sent, scenario === 'qualified' ? 1 : 0, scenario);
    assert.equal(stats.success_count, sent, scenario);
    assert.equal(h.decisionCalls().length, 1, scenario);
    assert.equal(h.generationCalls().length, sent, scenario);
    if (scenario === 'qualified') assert.equal(stats.details[0].score, 75);
    else assert.equal(stats.skipped, 1, scenario);
  }
});

test('follow-only comment processing keeps a valid Jev decision when reply generation is unavailable', () => {
  const h = runtime({ generation: '' });
  const ui = h.load('core/ui-operator.js');
  const utils = h.load('handlers/comment-utils.js');
  const api = h.load('core/api-client.js');
  const handler = h.load('handlers/reply-comment.js');
  let profiles = 0;
  let replies = 0;
  ui.findElements = () => [{}];
  ui.findElement = () => null;
  utils.localPreFilter = () => true;
  utils.toBeijingTime = () => '';
  h.load('core/anti-detect.js').maybePause = () => {};
  api.claimCommentReply = () => ({ claimed: true });
  api.collectReport = () => {};
  handler._storageGet = () => 0;
  handler._storageSet = () => {};
  handler._parseCommentItem = () => ({ nickname: params.nickname, text: params.commentText });
  handler._filterByTime = comments => comments;
  handler._replyToComment = () => { replies++; return true; };
  // Stop at the hardware navigation boundary after the real score/exclusion/quota gates.
  handler._enterCommenterProfile = () => { profiles++; return false; };
  utils.swipeList = () => false;
  const stats = handler._initStats();
  handler._processComments({ keyword: '睡眠习惯', count: 1, max_age_seconds: -1,
    skip_reply: true, max_follows: 1, max_dms: 0 }, stats, 0);
  assert.equal(profiles, 1);
  assert.equal(stats.skipped, 0);
  assert.equal(stats.details[0].score, 75);
  assert.equal(stats.details[0].reply, '');
  assert.equal(h.decisionCalls().length, 1);
  assert.equal(h.generationCalls().length, 0);
  assert.equal(replies, 0);
});

test('share-link execution selects its current template and resets it for the next task', () => {
  const h = runtime({ generation: '' });
  const prompts = h.load('core/prompts-config.js');
  h.analyzer.setIndustry('travel');
  const travel = plain(prompts.get());
  travel.domain = 'requested travel template';
  travel.analysis.scoringRules = ['只使用本次旅行咨询规则'];
  h.load('core/prompt-template-loader.js')._applyTemplates([
    { id: 'requested-travel', name: 'Travel', industry: 'travel', content: travel },
  ]);
  h.analyzer.setIndustry('health');
  const handler = h.load('handlers/search-collect.js');
  const ui = h.load('core/ui-operator.js');
  const utils = h.load('handlers/comment-utils.js');
  h.load('handlers/comment-base.js')._shouldProcessVideo = () => true;
  ui.isOnPage = () => true;
  ui.findElements = () => [{}];
  ui.findElement = () => null;
  utils.localPreFilter = () => true;
  utils.parseCommentItem = () => ({ nickname: '旅行测试', text: '想去云南，行程怎么安排？', time: '刚刚' });
  utils.parseTime = () => new Date();
  utils.openComments = () => true;
  handler._openSearch = () => true;
  handler._inputKeyword = () => true;
  handler._submitSearch = () => true;
  handler.safeClick = () => true;
  handler._backToSearchResults = () => {};
  handler._collectCommentData = () => ({});
  handler._collectUserData = () => null;
  handler._reportCollection = () => {};
  const task = { share_links: ['https://v.douyin.com/unit/'], count: 1, max_age_seconds: -1 };
  const first = handler.execute({ ...task, prompt_template_id: 'requested-travel' });
  assert.equal(first.result.success_count, 1);
  const firstRequest = h.decisionCalls()[0].body;
  assert.equal(firstRequest.state.industry, 'travel');
  assert.equal(firstRequest.state.domain, 'requested travel template');
  assert.deepEqual(firstRequest.state.analysis.scoringRules, ['只使用本次旅行咨询规则']);
  assert.deepEqual(Object.keys(firstRequest.questions.intent.criteria), ['strong_buy', 'travel_consult', 'other']);
  const next = handler.execute(task);
  assert.equal(next.result.success_count, 1);
  const nextRequest = h.decisionCalls()[1].body;
  assert.equal(nextRequest.state.industry, 'health');
  assert.notEqual(nextRequest.state.domain, firstRequest.state.domain);
  assert.deepEqual(Object.keys(nextRequest.questions.intent.criteria), ['strong_buy', 'health_consult', 'patient_self', 'other']);
  assert.equal(h.generationCalls().length, 0);
});

test('relaxed probability thresholds never invert false or tied native relevance answers', () => {
  for (const threshold of [0, 0.25]) {
    for (const probability of [0, 0.2, 0.5, 0.8]) {
      const h = runtime({ mutate(r) { r.answers.related.noul = probability; } });
      h.applyServerConfig({ decision_config: { min_probability: threshold } });
      assert.equal(h.config.decision.min_probability, threshold);
      assert.equal(h.analyzer.checkRelevance('听听今天的分享', '生活习惯'), probability > 0.5, threshold + '/' + probability);
      assert.equal(h.decisionCalls().length, 1);
      assert.equal(h.generationCalls().length, 0);
    }
  }
});

test('an exact native boolean tie is uncertain even when probability thresholds are relaxed', () => {
  for (const field of ['is_bot', 'is_competitor', 'specific_condition']) {
    const h = runtime({ decision: { min_probability: 0 }, mutate(r) { r.answers[field].noul = 0.5; } });
    assert.equal(h.analyzer.analyzeComment(params), null, field);
    assert.equal(h.generationCalls().length, 0);
  }
});
