const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');

function node(x, y, extra) {
  return Object.assign({bounds: () => ({left:x-10, top:y-10, right:x+10, bottom:y+10, centerX:()=>x, centerY:()=>y}), clickable:()=>true, click:()=>true, visibleToUser:()=>true}, extra);
}
function harness(configs, nodes, options = {}) {
  let now = 0;
  const state = {width:720,height:1600,density:2,contentBounds:{left:0,top:0,right:720,bottom:1600},blockedBounds:[],signature:'initial',observedAt:0,canInteract:true};
  const ops = [];
  function usable(p, ctx, region) {
    const r=region || ctx.contentBounds;
    return ctx.canInteract && p && Number.isFinite(p.x) && Number.isFinite(p.y) && p.x>=r.left && p.y>=r.top && p.x<r.right && p.y<r.bottom && !(ctx.blockedBounds || []).some(b=>p.x>=b.left && p.x<b.right && p.y>=b.top && p.y<b.bottom);
  }
  // Runtime boundary fixture. Geometry itself is covered by screen-context.node-test.js.
  const geometry = {
    read:()=>Object.assign({},state,{observedAt:now}),
    rect:r=>r && ({left:r.left,top:r.top,right:r.right,bottom:r.bottom}),
    isUsablePoint:usable,
    contains:(r,x,y)=>x>=r.left && x<r.right && y>=r.top && y<r.bottom,
    regionForStrategy:(s,c,a)=>s.region ? {left:s.region.left*c.width,top:s.region.top*c.height,right:s.region.right*c.width,bottom:s.region.bottom*c.height}:a || c.contentBounds,
    pointForStrategy:(s,c,a)=> {
      const p=s.position || {space:'screen_normalized',x:s.x_percent,y:s.y_percent};
      if (p.space==='screen_px') return {x:p.x,y:p.y};
      if (![p.x,p.y].every(v=>Number.isFinite(v) && v>=0 && v<=1)) return null;
      const b=p.space==='anchor_normalized' ? a:c.contentBounds;
      if (!b) return null;
      return {x:Math.min(b.right-1,Math.round(b.left+p.x*(b.right-b.left))),y:Math.min(b.bottom-1,Math.round(b.top+p.y*(b.bottom-b.top)))};
    },
    offsetPoint:(p,s,b,c,kind)=> {
      let ox=0,oy=0;
      if (s.offset) { ox=s.offset.x||0; oy=s.offset.y||0; if(s.offset.unit==='target_fraction'){ox*=b.right-b.left;oy*=b.bottom-b.top;} if(s.offset.unit==='dp'){ox*=c.density;oy*=c.density;} }
      else if(kind!=='coordinate') {ox=s.x_percent||0;oy=s.y_percent||0;if(kind==='node'){ox*=(b.right-b.left)/100;oy*=(b.bottom-b.top)/100;}}
      return {x:p.x+ox,y:p.y+oy};
    }
  };
  const selector = value => ({find:()=>nodes && nodes[value] || [],findOne:()=>nodes && nodes[value] && nodes[value][0] || null});
  const sandbox = {module:{exports:{}}, require:name=>name==='./task-cancellation'?{isCancelled:()=>false}:name==='./selector-loader'?{get:name=>configs[name],_cache:configs}:name==='./screen-context'?geometry:name==='./image-locator'?{find:()=>null}:{info(){},warn(){},error(){},debug(){}}, device:state, Date:{now:()=>now},sleep:ms=>{now+=ms;},currentPackage:()=> 'com.ss.android.ugc.aweme',click:(x,y)=>{ops.push(['click',x,y]);return sandbox.actuationResult;},press:(x,y,d)=>{ops.push(['press',x,y,d]);return sandbox.actuationResult;},text:selector,id:selector,desc:selector,className:selector,textContains:selector,idContains:selector,descContains:selector,classNameContains:selector,actuationResult:true, shell:()=>({code:1}),setClip(){}};
  Object.assign(sandbox,options.globals || {});
  if (options.realGeometry) {
    sandbox.context = {getResources:()=>({getDisplayMetrics:()=>({density:state.density}),getConfiguration:()=>({fontScale:1})})};
    sandbox.auto = {};
    Object.defineProperty(sandbox.auto,'windows',{get:()=>[
      {getRoot:()=>({packageName:()=> 'com.ss.android.ugc.aweme'}),bounds:()=>state.contentBounds,getType:()=>1,getLayer:()=>0,isActive:()=>true,isFocused:()=>true},
      ...state.blockedBounds.map(bounds=>({getRoot:()=>({packageName:()=> 'ime'}),bounds:()=>bounds,getType:()=>2,getLayer:()=>2,isActive:()=>false,isFocused:()=>true}))
    ]});
    const geometryModule={exports:{}};
    vm.runInNewContext(fs.readFileSync(require.resolve('../core/screen-context'),'utf8'),Object.assign({},sandbox,{module:geometryModule}));
    const originalRequire=sandbox.require;
    sandbox.require=name=>name==='./screen-context'?geometryModule.exports:originalRequire(name);
  }
  vm.runInNewContext(fs.readFileSync(require.resolve('../core/ui-operator'),'utf8'),sandbox);
  return {ui:sandbox.module.exports,state,ops,sandbox,geometry};
}

function parentResolver(h) {
  const sandbox = Object.assign({}, h.sandbox, { module: { exports: {} } });
  const originalRequire = sandbox.require;
  sandbox.require = name => name === './ui-operator' ? h.ui : originalRequire(name);
  vm.runInNewContext(fs.readFileSync(require.resolve('../core/selector-resolver'), 'utf8'), sandbox);
  return sandbox.module.exports;
}

test('parent lookup filters every candidate by the configured region and keeps its scope until click', () => {
  let y = 100;
  const outside = node(100, 1000);
  const inside = node(100, 100, { bounds: () => ({ left:90,top:y-10,right:110,bottom:y+10 }) });
  const h = harness({avatar:{strategies:[{type:'id',value:'avatar',priority:1,region:{space:'screen_normalized',left:0,top:0,right:1,bottom:0.2}}]}});
  const parent = {find:()=>[outside,inside],findOne:()=>outside};
  const resolved = parentResolver(h).findChildBySelector(parent, 'avatar');
  assert.equal(resolved, inside);
  y = 1000;
  assert.equal(h.ui.clickElement(resolved), false);
  assert.deepEqual(h.ops, []);
});

test('parent conditions retain the outer scope for AND and OR alternatives', () => {
  for (const logic of ['and', 'or']) {
    const outside=node(100,1000,{id:()=> 'avatar',desc:()=> 'person'});
    const inside=node(100,100,{id:()=> 'avatar',desc:()=> 'person'});
    const h=harness({});
    const strategy={conditions:[{type:'id',value:'avatar'},{type:'desc',value:'person'}],logic,region:{space:'screen_normalized',left:0,top:0,right:1,bottom:0.2}};
    const resolved=parentResolver(h).findByConditionsInParent({find:()=>[outside,inside],findOne:()=>outside},strategy);
    assert.equal(resolved,inside);
    h.state.blockedBounds=[{left:0,top:0,right:720,bottom:300}];
    assert.equal(h.ui.clickElement(resolved),false);
  }
});

test('parent chain lookup considers later candidates inside the final scope', () => {
  const outside=node(100,1000),inside=node(100,100);
  const h=harness({});
  const strategy={type:'chain',steps:[{type:'id',value:'avatar'}],region:{space:'screen_normalized',left:0,top:0,right:1,bottom:0.2}};
  assert.equal(parentResolver(h).findByStrategyInParent({find:()=>[outside,inside]},strategy),inside);
});

test('parent lookup enforces anchors and fails when the anchor is missing', () => {
  const outside=node(500,500),inside=node(100,100),anchor=node(100,100);
  const h=harness({}, {container:[anchor]});
  const resolver=parentResolver(h);
  const parent={find:()=>[outside,inside],findOne:()=>outside};
  assert.equal(resolver.findByStrategyInParent(parent,{type:'id',value:'avatar',anchor:{type:'text',value:'container'}}),inside);
  assert.equal(resolver.findByStrategyInParent(parent,{type:'id',value:'avatar',anchor:{type:'text',value:'missing'}}),null);
});

test('parent-scoped chains cannot climb above their container while global chains still can', () => {
  const outside = node(100,100);
  const container = node(100,100,{parent:()=>outside});
  const child = node(100,100,{parent:()=>container});
  container.find = () => [child];
  const h=harness({}, {seed:[child]});
  const strategy={type:'chain',steps:[{type:'id',value:'seed'},{nav:'parent'},{nav:'parent'}]};
  assert.equal(parentResolver(h).findByStrategyInParent(container,strategy),null);
  assert.equal(h.ui._findByStrategy(strategy),outside);
});

test('parent-scoped chains cannot select siblings of their container', () => {
  const sibling=node(100,100);
  const outside=node(100,100,{find:()=>[sibling]});
  sibling.parent=()=>outside;
  const container=node(100,100,{parent:()=>outside});
  const child=node(100,100,{parent:()=>container});
  container.find=()=>[child];
  const h=harness({});
  const strategy={type:'chain',steps:[{type:'id',value:'seed'},{nav:'parent'},{nav:'sibling',type:'id',value:'elsewhere'}]};
  assert.equal(parentResolver(h).findByStrategyInParent(container,strategy),null);
});

test('coordinate press uses legacy screen fraction once, including zero edge',()=>{
  const h=harness({target:{strategies:[{type:'coordinate',x_percent:0,y_percent:0.5,click_mode:'press'}]}});
  const target=h.ui.findElement('target',1);
  assert.equal(target.x,0); assert.equal(target.y,800);
  assert.equal(h.ui.clickElement(target),true);
  assert.deepEqual(h.ops,[['press',0,800,150]]);
});
test('package evidence does not actuate and coordinate guesses do not identify pages',()=>{
  const h=harness({page:{purpose:'page_detect',strategies:[{type:'coordinate',x_percent:0.5,y_percent:0.5}]}});
  assert.equal(h.ui.clickElement({isPackage:true,packageName:'com.ss.android.ugc.aweme'}),false);
  assert.equal(h.ui.isOnPage('page',1),false);
});
test('invalid coordinates and offsets fail before click',()=>{
  const h=harness({bad:{strategies:[{type:'coordinate',x_percent:2,y_percent:0.5}]},offset:{strategies:[{type:'text',value:'item',offset:{unit:'px',x:9999,y:0}}]}},{item:[node(100,100)]});
  assert.equal(h.ui.findElement('bad',1),null);
  assert.equal(h.ui.findElement('offset',1),null);
  assert.equal(h.ui.clickElement({isCoordinate:true,x:NaN,y:1}),false);
  assert.equal(h.ops.length,0);
});
test('filters every candidate by strategy region and keeps raw semantic UiObjects',()=>{
  const good=node(500,100); const h=harness({target:{strategies:[{type:'text',value:'item',region:{space:'screen_normalized',left:0.5,top:0,right:1,bottom:1}}]}},{item:[node(100,100),good]});
  assert.equal(h.ui.findElement('target',1),good);
});
test('anchor must be semantic and unique',()=>{
  const h=harness({target:{strategies:[{type:'coordinate',position:{space:'anchor_normalized',x:0.5,y:0.5},anchor:{type:'text',value:'container'}}]}},{container:[node(100,100),node(500,500)]});
  assert.equal(h.ui.findElement('target',1),null);
});
test('stale points reject moved geometry and clickAction resolves fresh coordinates',()=>{
  const h=harness({target:{strategies:[{type:'coordinate',x_percent:0.5,y_percent:0.5}]}});
  const old=h.ui.findElement('target',1);
  h.state.signature='keyboard';h.state.blockedBounds=[{left:0,top:1000,right:720,bottom:1600}];
  assert.equal(h.ui.clickElement(old),false);
  assert.equal(h.ui.clickAction('target',1,{click_mode:'press',press_duration:220}),true);
  assert.deepEqual(h.ops,[['press',360,800,220]]);
});
test('live semantic visibility and actual actuation results are checked',()=>{
  const h=harness({});const el=node(100,100);
  h.sandbox.actuationResult=false;
  assert.equal(h.ui.clickElement({isCoordinate:true,x:100,y:100,signature:'initial',observedAt:0}),false);
  assert.equal(h.ui.inputText(el,'hello'),false);
  el.visibleToUser=()=>false;
  assert.equal(h.ui.clickElement(el),false);
});
test('chain navigation considers later candidates before applying the final region',()=>{
  const good=node(500,200);
  const h=harness({target:{strategies:[{type:'chain',steps:[{type:'text',value:'seed'},{nav:'parent'}],region:{space:'screen_normalized',left:0.5,top:0,right:1,bottom:1}}]}},{seed:[node(100,100,{parent:()=>node(100,200)}),node(100,100,{parent:()=>good})]});
  assert.equal(h.ui.findElement('target',1),good);
});
test('explicit offsets override legacy offsets and raw node bounds are never resolution scaled',()=>{
  const h=harness({target:{strategies:[{type:'text',value:'item',x_percent:50,offset:{unit:'dp',x:2,y:0}}]}},{item:[node(100,100)]});
  const target=h.ui.findElement('target',1);assert.equal(target.x,104);assert.equal(target.y,100);
  assert.equal(h.ui.clickElement(target),true);assert.deepEqual(h.ops,[['click',104,100]]);
});

for (const [width,height] of [[720,1600],[1080,2340],[1080,2400],[1440,3200]]) {
  test(`actual geometry integrates fresh actions at ${width}x${height}`,()=>{
    const h=harness({target:{strategies:[{type:'coordinate',position:{space:'screen_normalized',x:0,y:1}}]}},{},{realGeometry:true});
    Object.assign(h.state,{width,height,contentBounds:{left:0,top:0,right:width,bottom:height}});
    const first=h.ui.findElement('target',1);
    assert.equal(first.x,0);assert.equal(first.y,height-1);
    assert.equal(h.ui.clickElement(first),true);
    h.state.blockedBounds=[{left:0,top:height/2,right:width,bottom:height}];
    assert.equal(h.ui.clickElement(first),false);
    assert.equal(h.ui.clickAction('target',1),false);
    h.state.blockedBounds=[];
    assert.equal(h.ui.clickAction('target',1,{click_mode:'press'}),true);
    assert.deepEqual(h.ops,[['click',0,height-1],['press',0,height-1,150]]);
  });
}
test('package page markers remain compatible while mixed OR ignores coordinate guesses',()=>{
  const h=harness({app:{purpose:'page_detect',strategies:[{type:'package',value:'com.ss.android.ugc.aweme'}]},mixed:{purpose:'page_detect',strategy_logic:'or',strategies:[{type:'coordinate',x_percent:0.5,y_percent:0.5},{type:'text',value:'title'}]}},{title:[node(100,100)]});
  assert.equal(h.ui.isOnPage('app',1),true);
  assert.equal(h.ui.isOnPage('mixed',1),true);
});
test('capture_px positions capture actual dimensions, map, then recycle exactly once',()=>{
  const h=harness({target:{strategies:[{type:'coordinate',position:{space:'capture_px',x:359,y:799}}]}},{},{realGeometry:true});
  let recycled=0;h.sandbox.images={captureScreen:()=>({getWidth:()=>360,getHeight:()=>800,recycle:()=>{recycled++;}})};
  const target=h.ui.findElement('target',1);
  assert.equal(target.x,719);assert.equal(target.y,1599);assert.equal(recycled,1);
  assert.equal(h.ui.clickElement(target),true);
});
test('a semantic target disappearing during press preparation returns false',()=>{
  let reads=0;const target=node(100,100);const original=target.bounds;
  target.bounds=()=>++reads>=3?null:original();
  const h=harness({target:{strategies:[{type:'text',value:'item'}]}},{item:[target]});
  assert.equal(h.ui.clickAction('target',1,{click_mode:'press'}),false);
  assert.equal(h.ops.length,0);
});

test('a raw semantic target moving outside its saved strategy region cannot click',()=>{
  let x=600;const target=node(600,100);target.bounds=()=>({left:x-10,top:90,right:x+10,bottom:110,centerX:()=>x,centerY:()=>100});
  let clicks=0;target.click=()=>{clicks++;return true;};
  const h=harness({target:{strategies:[{type:'text',value:'item',region:{space:'screen_normalized',left:0.5,top:0,right:1,bottom:1}}]}},{item:[target]});
  assert.equal(h.ui.findElement('target',1),target);
  x=100;
  assert.equal(h.ui.clickElement(target),false);assert.equal(clicks,0);
});
test('actuation re-resolves a semantic anchor after it moves within an unchanged window',()=>{
  let anchorX=100;const anchor=node(100,100);anchor.bounds=()=>({left:anchorX-50,top:50,right:anchorX+50,bottom:150});
  let clicks=0;const target=node(100,100,{click:()=>{clicks++;return true;}});
  const h=harness({target:{strategies:[{type:'text',value:'item',anchor:{type:'text',value:'container'}}]}},{item:[target],container:[anchor]});
  assert.equal(h.ui.findElement('target',1),target);
  anchorX=500;
  assert.equal(h.ui.clickElement(target),false);assert.equal(clicks,0);
});
test('distinct overlapping nodes remain ambiguous for OR and chain calibration candidates',()=>{
  const first=node(100,100,{className:()=> 'Container'}),second=node(100,100,{className:()=> 'Container'});
  const h=harness({}, {first:[first],second:[second],seed:[node(100,200,{parent:()=>first}),node(100,300,{parent:()=>second})]});
  const or=h.ui._findManyByStrategy({type:'text',logic:'or',conditions:[{type:'text',value:'first'},{type:'text',value:'second'}]});
  assert.equal(or.length,2);assert.equal(or[0],first);assert.equal(or[1],second);
  const chain=h.ui._findManyByStrategy({type:'chain',steps:[{type:'text',value:'seed'},{nav:'parent'}]});
  assert.equal(chain.length,2);assert.equal(chain[0],first);assert.equal(chain[1],second);
});
test('the same actual node matching multiple OR conditions is deduplicated by identity',()=>{
  const same=node(100,100);const h=harness({}, {first:[same],second:[same]});
  assert.equal(h.ui._findManyByStrategy({type:'text',logic:'or',conditions:[{type:'text',value:'first'},{type:'text',value:'second'}]}).length,1);
});
test('weak scope metadata survives hundreds of later nodes and keeps direct native clicks compatible',()=>{
  let x=600;const first=node(600,100);first.bounds=()=>({left:x-10,top:90,right:x+10,bottom:110});
  const nodes={item:[first]};
  const h=harness({target:{strategies:[{type:'text',value:'item',region:{space:'screen_normalized',left:0.5,top:0,right:1,bottom:1}}]}},nodes);
  assert.equal(h.ui.findElement('target',1),first);
  for(let i=0;i<300;i++){nodes.item=[node(600,100)];assert.ok(h.ui.findElement('target',1));}
  x=100;assert.equal(h.ui.clickElement(first),false);
  assert.equal(h.ui.clickElement(node(100,100)),true);
});
test('native Java weak-map association preserves raw objects without attaching node fields',()=>{
  const map=new Map();let synchronized=0;
  const java={util:{WeakHashMap:function(){return {put:(key,value)=>map.set(key,value),get:key=>map.get(key)};},Collections:{synchronizedMap:map=>{synchronized++;return map;}}}};
  const target=Object.freeze(node(600,100));
  const h=harness({target:{strategies:[{type:'text',value:'item',region:{space:'screen_normalized',left:0.5,top:0,right:1,bottom:1}}]}},{item:[target]},{globals:{java}});
  assert.equal(h.ui.findElement('target',1),target);assert.equal(synchronized,1);
  assert.equal(h.ui.clickElement(target),true);
  assert.equal(JSON.stringify(map.get(target)).includes('node'),false);
});
test('fixture fallback refuses new scoped lookups on capacity instead of losing earlier scope',()=>{
  let x=600;const first=node(600,100);first.bounds=()=>({left:x-10,top:90,right:x+10,bottom:110});
  const nodes={item:[first]};const h=harness({target:{strategies:[{type:'text',value:'item',region:{space:'screen_normalized',left:0.5,top:0,right:1,bottom:1}}]}},nodes,{globals:{WeakMap:undefined}});
  assert.equal(h.ui.findElement('target',1),first);
  for(let i=0;i<255;i++){nodes.item=[node(600,100)];assert.ok(h.ui.findElement('target',1));}
  nodes.item=[node(600,100)];assert.equal(h.ui.findElement('target',1),null);
  x=100;assert.equal(h.ui.clickElement(first),false);
  assert.equal(h.ui.clickElement(node(100,100)),true);
});
test('actual calibrator refuses to crop two distinct overlapping OR or chain targets',()=>{
  const first=node(100,100,{className:()=> 'Container'}),second=node(100,100,{className:()=> 'Container'});
  const h=harness({}, {first:[first],second:[second],seed:[node(100,200,{parent:()=>first}),node(100,300,{parent:()=>second})]});
  let captured=0,saved=0;const calibrationModule={exports:{}};
  const sandbox={module:calibrationModule,images:{captureScreen:()=>{captured++;return null;},save:()=>{saved++;}},require:name=>name==='./ui-operator'?h.ui:name==='./screen-context'?h.geometry:{info(){},warn(){},error(){}}};
  vm.runInNewContext(fs.readFileSync(require.resolve('../core/calibrator'),'utf8'),sandbox);
  for(const strategy of [{type:'text',logic:'or',conditions:[{type:'text',value:'first'},{type:'text',value:'second'}]},{type:'chain',steps:[{type:'text',value:'seed'},{nav:'parent'}]}]) {
    const result=calibrationModule.exports._captureTemplate({action_name:'target',selector:{strategies:[strategy]}},'720x1600');
    assert.equal(result,null);
  }
  assert.equal(captured,0);assert.equal(saved,0);
});

test('retained same-node aliases from conflicting scopes fail closed and fresh clickAction recovers',()=>{
  let x=600;const target=node(600,100);target.bounds=()=>({left:x-10,top:90,right:x+10,bottom:110});
  const h=harness({a:{strategies:[{type:'text',value:'item',region:{space:'screen_normalized',left:0.5,top:0,right:1,bottom:1}}]},b:{strategies:[{type:'text',value:'item',region:{space:'screen_normalized',left:0,top:0,right:1,bottom:1}}]}},{item:[target]});
  const a=h.ui.findElement('a',1),b=h.ui.findElement('b',1);assert.equal(a,target);assert.equal(b,target);
  x=100;
  assert.equal(h.ui.clickElement(a),false);assert.equal(h.ui.clickElement(b),false);
  assert.equal(h.ui.clickAction('b',1),true);
  assert.equal(h.ui.clickAction('b',1,{click_mode:'press'}),true);
});
test('scope versus no-scope aliases cannot silently clear or inherit a restriction',()=>{
  let x=600;const target=node(600,100);target.bounds=()=>({left:x-10,top:90,right:x+10,bottom:110});
  const h=harness({a:{strategies:[{type:'text',value:'item',region:{space:'screen_normalized',left:0.5,top:0,right:1,bottom:1}}]},b:{strategies:[{type:'text',value:'item'}]}},{item:[target]});
  const a=h.ui.findElement('a',1),b=h.ui.findElement('b',1);
  assert.equal(h.ui.clickElement(a),false);assert.equal(h.ui.clickElement(b),false);
  x=100;assert.equal(h.ui.clickAction('b',1),true);
});
for (const press of [false,true]) {
  test(`an overlapping anchor movement invalidates its observed point${press?' including press overrides':''}`,()=>{
    let left=0;const anchor=node(50,50);anchor.bounds=()=>({left,top:0,right:left+100,bottom:100});
    const h=harness({target:{strategies:[{type:'coordinate',position:{space:'anchor_normalized',x:0.5,y:0.5},anchor:{type:'text',value:'anchor'}}]}},{anchor:[anchor]});
    const old=h.ui.findElement('target',1);assert.equal(old.x,50);left=10;
    if(press){old.isPress=true;old.duration=150;}
    assert.equal(h.ui.clickElement(old),false);
    assert.equal(h.ui.clickAction('target',1,press?{click_mode:'press'}:{}),true);
    assert.equal(h.ops[0][1],60);
  });
}
test('native weak-map equals aliases retain scope ambiguity without key-retaining metadata',()=>{
  const entries=[];
  const map={get:key=>{const item=entries.find(item=>item.key===key || item.key.equals(key));return item && item.value;},put:(key,value)=>{const item=entries.find(item=>item.key===key || item.key.equals(key));if(item)item.value=value;else entries.push({key,value});}};
  const java={util:{WeakHashMap:function(){return map;},Collections:{synchronizedMap:map=>map}}};
  const a=node(600,100,{equals:other=>other && other.nativeId===1,nativeId:1});const b=node(600,100,{equals:other=>other && other.nativeId===1,nativeId:1});
  const nodes={item:[a]};const h=harness({a:{strategies:[{type:'text',value:'item',region:{space:'screen_normalized',left:0.5,top:0,right:1,bottom:1}}]},b:{strategies:[{type:'text',value:'item'}]}},nodes,{globals:{java}});
  assert.equal(h.ui.findElement('a',1),a);nodes.item=[b];assert.equal(h.ui.findElement('b',1),b);
  assert.equal(h.ui.clickElement(a),false);assert.equal(h.ui.clickElement(b),false);
  assert.equal(h.ui.clickAction('b',1),true);
  assert.equal(entries[0].value.ambiguous,true);
  assert.equal(JSON.stringify(entries[0].value).includes('nativeId'),false);
});
test('clickAction press override never refreshes a point that aged during lookup',()=>{
  const h=harness({target:{strategies:[{type:'coordinate',x_percent:0.5,y_percent:0.5}]}});
  const resolve=h.ui._findElementResolution;let originalPoint;
  h.ui._findElementResolution=function(){const result=resolve.apply(this,arguments);originalPoint=result.element;h.sandbox.sleep(6000);return result;};
  assert.equal(h.ui.clickAction('target',1,{click_mode:'press'}),false);
  assert.equal(originalPoint.observedAt,0);assert.equal(h.ops.length,0);
});
test('clickAction press override rejects an anchor that shifted after its fresh lookup',()=>{
  let left=0;const anchor=node(50,50);anchor.bounds=()=>({left,top:0,right:left+100,bottom:100});
  const h=harness({target:{strategies:[{type:'coordinate',position:{space:'anchor_normalized',x:0.5,y:0.5},anchor:{type:'text',value:'anchor'}}]}},{anchor:[anchor]});
  const resolve=h.ui._findElementResolution;
  h.ui._findElementResolution=function(){const result=resolve.apply(this,arguments);left=10;return result;};
  assert.equal(h.ui.clickAction('target',1,{click_mode:'press'}),false);assert.equal(h.ops.length,0);
});
for(const mode of [{offset:{unit:'dp',x:0,y:0}},{click_mode:'press'}]) {
  test(`a semantic derived point rejects source-node movement within the same scope ${JSON.stringify(mode)}`,()=>{
    let x=100;const target=node(100,100);target.bounds=()=>({left:x-10,top:90,right:x+10,bottom:110});
    const h=harness({target:{strategies:[Object.assign({type:'text',value:'item'},mode)]}},{item:[target]});
    const old=h.ui.findElement('target',1);assert.equal(old.x,100);x=110;
    assert.equal(h.ui.clickElement(old),false);
    assert.equal(h.ui.clickAction('target',1,{click_mode:'press'}),true);
    assert.equal(h.ops[0][1],110);
  });
}
for(const mode of [{},{offset:{unit:'px',x:0,y:0}},{click_mode:'press'}]) {
  test(`native cached bounds refresh before scoped raw or derived-point actuation ${JSON.stringify(mode)}`,()=>{
    let actualX=600,cachedX=600,refreshes=0;
    const target=node(600,100,{refresh:()=>{refreshes++;cachedX=actualX;return true;}});
    target.bounds=()=>({left:cachedX-10,top:90,right:cachedX+10,bottom:110});
    const h=harness({target:{strategies:[Object.assign({type:'text',value:'item',region:{space:'screen_normalized',left:0.5,top:0,right:1,bottom:1}},mode)]}},{item:[target]});
    const retained=h.ui.findElement('target',1);assert.ok(retained);actualX=100;
    assert.equal(h.ui.clickElement(retained),false);assert.ok(refreshes>=1);assert.equal(h.ops.length,0);
  });
}
for(const failure of [false,'exception']) {
  test(`native refresh ${String(failure)} rejects actuation`,()=>{
    let valid=true;const target=node(100,100,{refresh:()=>{if(valid)return true;if(failure==='exception')throw Error('stale');return false;}});
    const h=harness({target:{strategies:[{type:'text',value:'item'}]}},{item:[target]});
    assert.equal(h.ui.findElement('target',1),target);valid=false;
    assert.equal(h.ui.clickElement(target),false);assert.equal(h.ops.length,0);
  });
}
