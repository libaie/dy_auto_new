const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

// AutoJS services are unavailable in Node; run the actual handler modules against
// deterministic UI trees and geometry, never against a device or network.
function setup(overrides = {}) {
  const taps = [], swipes = [], shellCalls = [];
  const content = { left: 40, top: 100, right: 680, bottom: 1500 };
  const ctx = { width: 720, height: 1600, density: 2, contentBounds: content,
    blockedBounds: [{ left: 0, top: 1050, right: 720, bottom: 1600 }],
    captureWidth: 360, captureHeight: 800, signature: 'live', observedAt: 1, canInteract: true };
  function rect(b) {
    if (!b) return null;
    return {left: b.left, top: b.top, right: b.right, bottom: b.bottom};
  }
  const geometry = {
    read() { return ctx; }, rect,
    contains(b, x, y) { return !!b && x >= b.left && x < b.right && y >= b.top && y < b.bottom; },
    intersect(a, b) { if (!a || !b) return null; const r = {left: Math.max(a.left,b.left),top:Math.max(a.top,b.top),right:Math.min(a.right,b.right),bottom:Math.min(a.bottom,b.bottom)}; return r.right > r.left && r.bottom > r.top ? r : null; },
    dp(n, c) { return n * c.density; },
    isUsablePoint(p, c, region) { return geometry.contains(c.contentBounds,p.x,p.y) && (!region || geometry.contains(region,p.x,p.y)) && !c.blockedBounds.some(b=>geometry.contains(b,p.x,p.y)); },
    captureToScreen(p) { return {x:p.x*2,y:p.y*2}; },
    screenToCapture(p) { return {x:p.x/2,y:p.y/2}; }
  };
  function node(b, extra = {}) {
    const bounds = Object.assign({}, b, {centerX(){return (this.left+this.right)/2;},centerY(){return (this.top+this.bottom)/2;},width(){return this.right-this.left;},height(){return this.bottom-this.top;}});
    return Object.assign({ bounds(){return bounds;}, clickable(){return true;}, click(){taps.push([bounds.centerX(),bounds.centerY()]);return true;}, parent(){return null;}, text(){return '';}, className(){return '';} },extra);
  }
  const edit = node({left:80,top:800,right:600,bottom:900}, {value:'', focusable(){return true;},setText(s){this.value=s;return true;},text(){return this.value;}});
  let textMatches = [];
  const ui = Object.assign({findElement(){return null;},findElements(){return [];},isOnPage(){return true;},waitForPage(){return true;},clickElement(el){if(el.isCoordinate){taps.push([el.x,el.y]);return true;} return el.click();}, clickAction(a){const n=ui.findElement(a); return n ? ui.clickElement(n) : false;},swipeUp(){swipes.push('full-screen');}},overrides.ui);
  const image = {getWidth(){return 360;},getHeight(){return 800;},recycle(){}};
  const images = Object.assign({captureScreen(){return image;},paddleOcr(){return overrides.ocr || null;}},overrides.images);
  const globals = {console,device:{width:720,height:1600},sleep(){},back(){},press(x,y){taps.push([x,y]);return true;},gestures(s){swipes.push(s);return true;},shell(s){shellCalls.push(s);return {code:0};},input(s){edit.value+=s;},setClip(){},images,
    className(){return {focused(){return this;},findOne(){return edit;},find(){return [edit];}};},
    text(){return {find(){return textMatches;},findOne(){return textMatches[0]||null;}};},
    id(){return {findOne(){return null;},find(){return [];}};},
    ...overrides.globals};
  const cache = {};
  function load(name) {
    const full = path.resolve(__dirname,'..',name+'.js');
    if (cache[full]) return cache[full];
    const sandbox = {...globals,module:{exports:{}},exports:{}};
    sandbox.require = function(p) {
      const target=path.resolve(path.dirname(full),p);
      for (const [service, value] of Object.entries(overrides.services || {})) { if (target.endsWith('/'+service)) return value; }
      if(target.endsWith('/core/screen-context'))return geometry;
      if(target.endsWith('/core/ui-operator'))return ui;
      if(target.endsWith('/core/ocr-locator') || target.endsWith('/handlers/comment-utils'))return load(path.relative(path.resolve(__dirname,'..'),target));
      if(target.endsWith('/handlers/base-handler')||target.endsWith('/handlers/comment-base'))return {safeClick(a){return ui.clickAction(a);},safeInput(){return true;}};
      if(target.endsWith('/utils/logger'))return {info(){},warn(){},debug(){},error(){}};
      if(target.endsWith('/core/anti-detect'))return {};
      if(target.endsWith('/core/human-input'))return {typeFocusedText(){return true;}};
      return {};
    };
    vm.runInNewContext(fs.readFileSync(full,'utf8'),sandbox,{filename:full});
    return cache[full]=sandbox.module.exports;
  }
  return {load,node,edit,ui,ctx,geometry,taps,swipes,shellCalls,images,setMatches(v){textMatches=v;}};
}

test('text-only sorting OCR cannot produce guessed taps',()=>{
  const s=setup({ocr:'最新发布'});
  const search=s.load('handlers/search-base');
  search.safeClick=()=>true;
  assert.equal(search._sortResults('latest'),false);
  assert.deepEqual(s.taps,[]);
});

test('multiple structured sorting OCR matches are rejected',()=>{
  const s=setup({ocr:[{text:'最新发布',bounds:{left:40,top:100,right:90,bottom:120}},{text:'最新发布',bounds:{left:100,top:100,right:150,bottom:120}}]});
  const search=s.load('handlers/search-base'); search.safeClick=()=>true;
  assert.equal(search._sortResults('latest'),false);
  assert.deepEqual(s.taps,[]);
});

test('structured sorting OCR uses capture mapping and content scope',()=>{
  const s=setup({ocr:[{text:'最新发布',bounds:{left:100,top:100,right:150,bottom:120}}]});
  const search=s.load('handlers/search-base'); search.safeClick=()=>true;
  assert.equal(search._sortResults('latest'),true);
  assert.deepEqual(s.taps,[[250,220]]);
});

test('follow retry resolves a fresh target after it moves',()=>{
  const s=setup();let calls=0;
  s.ui.findElement=(a)=> a==='user_nickname'?{}:a==='is_follow'?(s.taps.length===2?{}:null):a==='follow_button'?s.node({left:100+calls++*100,top:300,right:160+(calls-1)*100,bottom:360},{text(){return '关注';}}):null;
  const r=s.load('handlers/reply-comment');
  assert.equal(r._followUser(),true);
  assert.deepEqual(s.taps,[[130,330],[230,330]]);
});

test('disappearing follow button is not success without followed evidence',()=>{
  const s=setup();let n=0;
  s.ui.findElement=a=>a==='user_nickname'?{}:a==='follow_button'&&n++===0?s.node({left:100,top:300,right:160,bottom:360}):null;
  assert.equal(s.load('handlers/reply-comment')._followUser(),false);
});

test('comment click with unknown result returns false and never submits Enter',()=>{
  const s=setup();s.ui.findElement=a=>a==='comment_submit'?s.node({left:610,top:800,right:670,bottom:900}):a==='comment_input'?s.edit:null;
  const r=s.load('handlers/reply-comment');
  assert.equal(r._replyToComment('test reply','nick'),false);
  assert.equal(s.taps.length,1);
  assert.equal(s.shellCalls.includes('input keyevent 66'),false);
  assert.equal(r._lastSendOutcome,'unknown');
});

test('missing comment send target does not blindly submit Enter',()=>{
  const s=setup();const r=s.load('handlers/reply-comment');
  assert.equal(r._replyToComment('test reply','nick'),false);
  assert.equal(s.shellCalls.includes('input keyevent 66'),false);
  assert.equal(r._lastSendOutcome,'not_attempted');
});

test('sequence stops at first unknown submission and counts no sends',()=>{
  const s=setup();s.ui.findElement=a=>a==='dm_send'?s.node({left:610,top:800,right:670,bottom:900}):a==='dm_input'?s.edit:null;
  const r=s.load('handlers/search-base'); const stats={details:[]};
  assert.equal(r._sendMessageSequence([{content:'first'},{content:'second'}],stats,''),0);
  assert.equal(s.taps.length,1);
  assert.equal(r._lastSendOutcome,'unknown');
  assert.deepEqual(stats.details,[]);
});

test('search input skips offscreen and keyboard-covered edits',()=>{
  const s=setup();const off=s.node({left:-200,top:150,right:-20,bottom:200},{focusable(){return true;},setText(){throw Error('offscreen edit selected');}});
  const good=s.node({left:100,top:150,right:550,bottom:200},{focusable(){return true;},setText(t){this.value=t;}});
  const x=setup({globals:{className(){return {find(){return [off,good];}};}}});
  assert.equal(x.load('handlers/search-base')._inputKeyword('query'),true);
  assert.equal(good.value,'query');
});

test('search result traversal scrolls within its visible list above keyboard',()=>{
  const s=setup();const rv=s.node({left:50,top:300,right:650,bottom:1450},{className(){return 'androidx.recyclerview.widget.RecyclerView';},children(){return [];}});
  s.ui.findElements=()=>[];
  const s2=setup({globals:{id(){return {findOne(){return rv;},find(){return [rv];}};},className(){return {find(){return [rv];}};}}});
  assert.equal(s2.load('handlers/search-base')._clickSearchResult(0),false);
  assert.ok(s2.swipes.length>0);
  s2.swipes.forEach(g=>{assert.notEqual(g,'full-screen');g.slice(2).forEach(p=>{assert.ok(p[0]>=50&&p[0]<650);assert.ok(p[1]>=300&&p[1]<1050);});});
});

test('avatar crop maps and clips to actual screenshot dimensions',()=>{
  let clip;
  const s=setup({images:{clip(im,x,y,w,h){clip=[x,y,w,h];throw Error('stop after checking crop');}}});
  s.load('handlers/comment-utils')._cropCircularAvatar(s.node({left:-20,top:100,right:180,bottom:300}));
  assert.ok(clip);assert.ok(clip[0]>=0&&clip[1]>=0&&clip[0]+clip[2]<=360&&clip[1]+clip[3]<=800);
  assert.ok(clip[2]<=100,'physical bounds must be mapped to half-size capture');
});

test('send is confirmed only when new visible content and cleared input are observed',()=>{
  const s=setup();s.edit.value='reply';
  s.ui.findElement=a=>a==='comment_submit'?s.node({left:610,top:800,right:670,bottom:900}):a==='comment_input'?s.edit:null;
  s.ui.clickAction=()=>{s.edit.value='';s.setMatches([s.node({left:80,top:500,right:500,bottom:600})]);return true;};
  assert.equal(s.load('handlers/comment-utils').submitAndObserve('comment_submit','comment_input','reply','comment_send_failed'),'confirmed');
});

test('cleared input without newly visible content remains unknown',()=>{
  const s=setup();s.ui.findElement=a=>a==='comment_submit'?s.node({left:610,top:800,right:670,bottom:900}):a==='comment_input'?s.edit:null;
  s.ui.clickAction=()=>true;
  assert.equal(s.load('handlers/comment-utils').submitAndObserve('comment_submit','comment_input','reply','comment_send_failed'),'unknown');
});

test('an existing failed-message marker does not prove current submission failed',()=>{
  const s=setup();s.ui.findElement=a=>a==='comment_submit'||a==='comment_send_failed'?s.node({left:610,top:800,right:670,bottom:900}):a==='comment_input'?s.edit:null;
  assert.equal(s.load('handlers/comment-utils').submitAndObserve('comment_submit','comment_input','reply','comment_send_failed'),'unknown');
});

test('a newly observed failure is returned as failed and never counted',()=>{
  const s=setup();let attempted=false;
  s.ui.findElement=a=>a==='comment_submit'||a==='comment_send_failed'&&attempted?s.node({left:610,top:800,right:670,bottom:900}):a==='comment_input'?s.edit:null;
  s.ui.clickAction=()=>{attempted=true;return true;};
  assert.equal(s.load('handlers/comment-utils').submitAndObserve('comment_submit','comment_input','reply','comment_send_failed'),'failed');
});

test('comment statistics and dedup claims distinguish unknown from pre-submit failure',()=>{
  // The isolated module loader exposes service adapters for these side effects.
  for(const outcome of ['unknown','not_attempted','confirmed']) {
    let released=0,counted=0;
    const s=setup({services:{'core/ai-analyzer':{SCORE_THRESHOLD:50,analyzeComment(){return {score:90,tier:'low',reply:'reply'};}},'core/api-client':{claimCommentReply(){return {claimed:true};},releaseCommentReply(){released++;},incrementStats(){counted++;}}}});
    const r=s.load('handlers/reply-comment');const util=s.load('handlers/comment-utils');
    util.localPreFilter=()=>true;
    r._storageGet=()=>0;r._storageSet=()=>true;r._parseCommentItem=()=>({nickname:'nick',text:'long comment'});r._filterByTime=v=>v;
    r._replyToComment=()=>{r._lastSendOutcome=outcome;return outcome==='confirmed';};
    s.ui.findElements=()=>[{}];
    const stats=r._initStats();r._processComments({keyword:'query',count:1,max_age_seconds:-1},stats,0);
    assert.equal(stats.success_count,outcome==='confirmed'?1:0);
    assert.equal(counted,outcome==='confirmed'?1:0);
    assert.equal(released,outcome==='not_attempted'?1:0);
  }
});

test('already-followed state does not count a new follow',()=>{
  const s=setup();s.ui.findElement=a=>a==='is_follow'||a==='user_nickname'?{}:null;
  assert.equal(s.load('handlers/reply-comment')._followUser(),false);
  assert.deepEqual(s.taps,[]);
});

test('search result skips the first offscreen or keyboard-covered candidate',()=>{
  const s=setup();
  const off=s.node({left:-200,top:300,right:-20,bottom:500});
  const covered=s.node({left:100,top:1100,right:400,bottom:1300});
  const usable=s.node({left:100,top:350,right:400,bottom:600});
  s.ui.findElements=()=>[off,covered,usable];
  assert.equal(s.load('handlers/search-base')._clickSearchResult(0),true);
  assert.deepEqual(s.taps,[[250,475]]);
});

test('missing comment list container never triggers full-screen gestures',()=>{
  const s=setup();
  const util=s.load('handlers/comment-utils');
  assert.equal(util.swipeList('comment_list'),false);
  assert.deepEqual(s.swipes,[]);
});

test('gesture retry cannot reuse a container that disappeared',()=>{
  const s=setup();const stale=s.node({left:50,top:300,right:650,bottom:900});
  assert.equal(s.load('handlers/comment-utils').swipeList('comment_list',false,stale),false);
  assert.deepEqual(s.swipes,[]);
});

test('follow retry rejects a pure coordinate fallback after unconfirmed actuation',()=>{
  const s=setup();s.ui.findElement=a=>a==='user_nickname'?{}:a==='follow_button'?{isCoordinate:true,x:200,y:400}:null;
  assert.equal(s.load('handlers/reply-comment')._followUser(),false);
  assert.equal(s.taps.length,1);
});

test('a stable follow resource ID changing to 已关注 is never clicked again',()=>{
  const s=setup();let following=false;
  const target=s.node({left:100,top:300,right:300,bottom:380},{text(){return following?'已关注':'关注';},desc(){return '';},id(){return 'com.ss.android.ugc.aweme:id/jym';},click(){following=!following;s.taps.push([200,340]);return true;}});
  s.ui.findElement=a=>a==='user_nickname'?{}:a==='follow_button'?target:null;
  assert.equal(s.load('handlers/reply-comment')._followUser(),false);
  assert.equal(s.taps.length,1);
  assert.equal(following,true);
});

test('an unlabeled generic follow node is insufficient retry state evidence',()=>{
  const s=setup();const target=s.node({left:100,top:300,right:300,bottom:380});
  s.ui.findElement=a=>a==='user_nickname'?{}:a==='follow_button'?target:null;
  assert.equal(s.load('handlers/reply-comment')._followUser(),false);
  assert.equal(s.taps.length,1);
});

for(const index of [0,1]) {
  test('fresh wrappers of the search list select visible child index '+index,()=>{
    const s=setup();
    const children=[s.node({left:100,top:330,right:300,bottom:470}),s.node({left:100,top:500,right:300,bottom:650})];
    function wrappedList(){return s.node({left:50,top:300,right:650,bottom:950},{className(){return 'androidx.recyclerview.widget.RecyclerView';},id(){return 'recycler_view';},children(){return children;}});}
    s.ui.findElements=()=>[wrappedList()];
    const r=s.load('handlers/search-base');r.safeClick=()=>true;
    assert.equal(r._clickSearchResult(index),true);
    assert.deepEqual(s.taps,[index===0?[200,400]:[200,575]]);
  });
}

function actualOcrRuntime(advanceMs, moveWindow) {
  let now=0,captures=0,recycled=0;
  const clicks=[];
  const state={width:720,height:1600,density:2,contentBounds:{left:0,top:0,right:720,bottom:1600}};
  const clock={now:()=>now};
  const runtime={device:state,Date:clock,currentPackage:()=> 'com.ss.android.ugc.aweme',
    context:{getResources:()=>({getDisplayMetrics:()=>({density:2}),getConfiguration:()=>({fontScale:1})})},auto:{}};
  Object.defineProperty(runtime.auto,'windows',{get:()=>[{getRoot:()=>({packageName:()=> 'com.ss.android.ugc.aweme'}),bounds:()=>state.contentBounds,getType:()=>1,getLayer:()=>0,isActive:()=>true,isFocused:()=>true}]});
  const geometryModule={exports:{}};
  vm.runInNewContext(fs.readFileSync(require.resolve('../core/screen-context'),'utf8'),{...runtime,module:geometryModule});
  const services={'core/screen-context':geometryModule.exports};
  const s=setup({services,globals:{...runtime,sleep(ms){now+=ms;},click(x,y){clicks.push([x,y]);return true;}},images:{captureScreen(){captures++;return {getWidth(){return 360;},getHeight(){return 800;},recycle(){recycled++;}};},paddleOcr(){now+=advanceMs;if(moveWindow)state.contentBounds={left:50,top:150,right:670,bottom:1500};return [{text:'最新发布',bounds:{left:100,top:100,right:150,bottom:120}}];}}});
  const ui=s.load('core/ui-operator');
  // Only lookup is adapted here: the geometry and click executor stay real.
  ui.findElement=()=>null;
  services['core/ui-operator']=ui;
  const search=s.load('handlers/search-base');search.safeClick=()=>true;
  return {run:()=>search._sortResults('latest'),clicks,get captures(){return captures;},get recycled(){return recycled;}};
}

test('actual executor accepts fresh OCR capture provenance',()=>{
  const h=actualOcrRuntime(0,false);
  assert.equal(h.run(),true);assert.equal(h.clicks.length,1);assert.equal(h.recycled,1);
});

test('actual executor rejects OCR taking six seconds without restamping capture age',()=>{
  const h=actualOcrRuntime(6000,false);
  assert.equal(h.run(),false);assert.deepEqual(h.clicks,[]);assert.equal(h.captures,1);assert.equal(h.recycled,1);
});

test('actual executor rejects a window change during OCR despite a still-visible point',()=>{
  const h=actualOcrRuntime(100,true);
  assert.equal(h.run(),false);assert.deepEqual(h.clicks,[]);assert.equal(h.captures,1);assert.equal(h.recycled,1);
});

test('an initially followed persistent ID cannot be toggled when is_follow is unavailable',()=>{
  const s=setup();const target=s.node({left:100,top:300,right:300,bottom:380},{text(){return '已关注';},desc(){return '';},id(){return 'com.ss.android.ugc.aweme:id/jym';}});
  s.ui.findElement=a=>a==='user_nickname'?{}:a==='follow_button'?target:null;
  assert.equal(s.load('handlers/reply-comment')._followUser(),false);
  assert.deepEqual(s.taps,[]);
});
