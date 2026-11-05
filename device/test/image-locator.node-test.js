const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');

function harness(options = {}) {
  const recycled=[],scales=[],matches=[];
  const image=(name,w,h)=>({getWidth:()=>w,getHeight:()=>h,recycle:()=>{assert.ok(!recycled.includes(name),'double recycle '+name);recycled.push(name);}});
  const ctx={width:720,height:1600,density:2,captureWidth:360,captureHeight:800,captureBounds:{left:0,top:0,right:720,bottom:1600},captureRotation:0,captureValid:true,contentBounds:{left:0,top:0,right:720,bottom:1600},signature:'live',observedAt:123,canInteract:true};
  Object.assign(ctx,options.ctx);
  let geometry={read:()=>ctx,rect:r=>r,intersect:(a,b)=>{const r={left:Math.max(a.left,b.left),top:Math.max(a.top,b.top),right:Math.min(a.right,b.right),bottom:Math.min(a.bottom,b.bottom)};return r.left<r.right && r.top<r.bottom?r:null;},regionForStrategy:(s)=>s.region?{left:0,top:0,right:360,bottom:800}:ctx.contentBounds,screenToCapture:p=>({x:p.x/2,y:p.y/2}),captureToScreen:p=>ctx.captureValid?{x:p.x*2,y:p.y*2}:null,isUsablePoint:(p,c,r)=>!!p&&c.canInteract&&p.x>=r.left&&p.x<r.right&&p.y>=r.top&&p.y<r.bottom};
  if (options.realGeometry) {
    const real=require('../core/screen-context');
    const snapshot=real.create(ctx);
    Object.assign(ctx,snapshot);
    geometry=Object.assign({},real,{read:()=>ctx});
  }
  const sandbox={module:{exports:{}},device:{width:720,height:1600},Date,files:{isDir:()=>false,listDir:()=>[],exists:path=>path.endsWith('/720x1600/icon@1080x2400.png')},images:{captureScreen:()=>image('screen',ctx.captureWidth,ctx.captureHeight),read:path=>path.endsWith('/icon@1080x2400.png')?image('template',60,30):null,scale:(tpl,x,y)=>{scales.push([x,y]);return image('scaled'+scales.length,Math.round(60*x),Math.round(30*y));},findImage:(screen,tpl,opts)=>{matches.push(opts);return options.match===false?null:{x:options.x || 0,y:options.y || 0};}},require:name=>name==='./task-cancellation'?{isCancelled:()=>false}:name==='./screen-context'?geometry:name==='./image-locator'?loadLocator():{info(){},warn(){},error(){},debug(){}}};
  function loadLocator(){const module={exports:{}};vm.runInNewContext(fs.readFileSync(require.resolve('../core/image-locator'),'utf8'),Object.assign({},sandbox,{module}));return module.exports;}
  vm.runInNewContext(fs.readFileSync(require.resolve('../core/ui-operator'),'utf8'),sandbox);
  return {ui:sandbox.module.exports,ctx,scales,matches,recycled,sandbox};
}

test('image matching uses equal multipliers, unchanged threshold and bounded capture region',()=>{
  const h=harness();
  const result=h.ui._findByImage('icon@1080x2400.png',0.91,{type:'image',source_resolution:'1080x2400',scales:[0.5],region:{space:'screen_normalized',left:0,top:0,right:0.5,bottom:0.5}});
  assert.deepEqual(h.scales,[[0.5,0.5]]);
  assert.equal(h.matches.length,1);assert.equal(h.matches[0].threshold,0.91);
  assert.deepEqual(Array.from(h.matches[0].region),[0,0,180,400]);
  assert.equal(result.x,30);assert.equal(result.y,15);assert.equal(result.signature,'live');
  assert.deepEqual(h.recycled.sort(),['scaled1','screen','template']);
});
test('no threshold relaxation and at most five scale attempts per candidate',()=>{
  const h=harness({match:false});
  assert.equal(h.ui._findByImage('icon@1080x2400.png',0.9,{scales:[0.5,0.75,1,1.25,1.5]}),null);
  assert.equal(h.matches.length,5);
  assert.ok(h.matches.every(m=>m.threshold===0.9));
  assert.ok(h.scales.every(s=>s[0]===s[1]&&s[0]<=4));
  assert.equal(h.recycled.length,new Set(h.recycled).size);
});
test('ambiguous screenshot mapping is rejected before matching',()=>{
  const h=harness({ctx:{captureValid:false}});
  assert.equal(h.ui._findByImage('icon@1080x2400.png',0.9,{scales:[1]}),null);
  assert.equal(h.matches.length,0);
  assert.deepEqual(h.recycled,['screen']);
});

test('actual geometry maps resized image captures and infers a uniform resolution factor',()=>{
  const h=harness({realGeometry:true});
  const result=h.ui._findByImage('icon@1080x2400.png',0.85,{});
  assert.ok(Math.abs(h.scales[0][0]-1/3)<0.00001);
  assert.equal(h.scales[0][0],h.scales[0][1]);
  assert.equal(result.x,20);assert.equal(result.y,10);
  assert.equal(result.signature,h.ctx.signature);
  assert.deepEqual(Array.from(h.matches[0].region),[0,0,360,800]);
});
test('actual geometry maps an explicitly rotated capture and bounds without stretching',()=>{
  const h=harness({realGeometry:true,ctx:{captureWidth:800,captureHeight:360,captureRotation:90}});
  const result=h.ui._findByImage('icon@1080x2400.png',0.85,{scales:[1]});
  assert.equal(result.x,30);assert.equal(result.y,1539);
  assert.equal(result.bounds.left,0);assert.equal(result.bounds.bottom,1600);
  assert.deepEqual(Array.from(h.matches[0].region),[0,0,800,360]);
});
test('actual geometry rejects an unexplained capture crop before template reads',()=>{
  const h=harness({realGeometry:true,ctx:{captureWidth:360,captureHeight:600}});
  assert.equal(h.ui._findByImage('icon@1080x2400.png',0.85,{scales:[1]}),null);
  assert.equal(h.matches.length,0);assert.deepEqual(h.recycled,['screen']);
});
test('the direct legacy image lookup default threshold is preserved',()=>{
  const h=harness();h.ui._findByImage('icon@1080x2400.png',undefined,{scales:[1]});
  assert.equal(h.matches[0].threshold,0.75);
});

test('a blocked first icon does not hide a usable icon at the same scale',()=>{
  const h=harness({realGeometry:true,ctx:{blockedBounds:[{left:0,top:0,right:720,bottom:400}]}});
  h.sandbox.images.findImage=(screen,tpl,options)=>{h.matches.push(options);return options.region[1]>=190?{x:10,y:400}:{x:10,y:10};};
  const result=h.ui._findByImage('icon@1080x2400.png',0.93,{scales:[1]});
  assert.ok(result);assert.ok(result.y>400);
  assert.ok(h.matches.every(m=>m.threshold===0.93));
  assert.ok(h.matches.every(m=>m.region[1]>=190));
});
for (const metadata of [{source_resolution:'1080x2400'},{source_density:3,source_resolution:'1080x2400'}]) {
  test(`fallback assets use their own directory provenance ${JSON.stringify(metadata)}`,()=>{
    const h=harness({realGeometry:true,ctx:{width:1080,height:2400,density:3,captureWidth:1080,captureHeight:2400,captureBounds:{left:0,top:0,right:1080,bottom:2400},contentBounds:{left:0,top:0,right:1080,bottom:2400}}});
    const asset='/sdcard/dy_auto/templates/720x1600/icon.png';
    h.sandbox.files.exists=path=>path===asset;
    h.sandbox.files.isDir=path=>path==='/sdcard/dy_auto/templates/' || path.indexOf('720x1600')!==-1;
    h.sandbox.files.listDir=path=>path==='/sdcard/dy_auto/templates/'?['720x1600']:['icon.png'];
    h.sandbox.images.read=path=>path===asset?{getWidth:()=>60,getHeight:()=>30,recycle:()=>h.recycled.push('fallback-template')}:null;
    assert.ok(h.ui._findByImage('icon.png',0.9,metadata));
    assert.equal(h.scales[0] && h.scales[0][0],1.5);assert.equal(h.scales[0] && h.scales[0][1],1.5);
  });
}
test('oversized inferred dimensions are rejected before allocating a scaled bitmap',()=>{
  const h=harness();
  assert.equal(h.ui._findByImage('icon@1080x2400.png',0.9,{scales:[4],region:{space:'screen_normalized',left:0,top:0,right:0.5,bottom:0.5}}),null);
  assert.equal(h.scales.length,0);assert.equal(h.matches.length,0);
});
test('the referenced asset retains explicit capture density instead of directory dimensions',()=>{
  const h=harness({realGeometry:true,ctx:{width:1080,height:2400,density:3,captureWidth:1080,captureHeight:2400,captureBounds:{left:0,top:0,right:1080,bottom:2400},contentBounds:{left:0,top:0,right:1080,bottom:2400}}});
  const asset='/sdcard/dy_auto/templates/1080x2400/icon.png';
  h.sandbox.files.exists=path=>path===asset;
  h.sandbox.images.read=path=>path===asset?{getWidth:()=>60,getHeight:()=>30,recycle:()=>{}}:null;
  assert.ok(h.ui._findByImage('icon.png',0.9,{source_resolution:'540x1200',source_density:1.5}));
  assert.equal(h.scales[0] && h.scales[0][0],2);
});
for(const profile of ['default','720x1600']) {
  for(const metadata of [{source_density:1.5},{source_resolution:'540x1200'}]) {
    test(`selected ${profile} profile exact asset keeps source metadata ${JSON.stringify(metadata)}`,()=>{
      const h=harness({realGeometry:true,ctx:{width:1080,height:2400,density:3,captureWidth:1080,captureHeight:2400,captureBounds:{left:0,top:0,right:1080,bottom:2400},contentBounds:{left:0,top:0,right:1080,bottom:2400}}});
      const asset='/sdcard/dy_auto/templates/'+profile+'/icon.png';
      h.sandbox.files.exists=path=>path===asset;
      h.sandbox.files.isDir=path=>path==='/sdcard/dy_auto/templates/' || path.indexOf(profile)!==-1;
      h.sandbox.files.listDir=path=>path==='/sdcard/dy_auto/templates/'?[profile]:['icon.png'];
      h.sandbox.images.read=path=>path===asset?{getWidth:()=>60,getHeight:()=>30,recycle:()=>{}}:null;
      const loader={get:()=>({purpose:'page_detect',resolution_profile:profile,strategies:[Object.assign({type:'image',template:'icon.png'},metadata)]})};
      const original=h.sandbox.require;h.sandbox.require=name=>name==='./selector-loader'?loader:original(name);
      let now=123;h.sandbox.Date={now:()=>now++};h.sandbox.sleep=ms=>{now+=ms;};h.sandbox.currentPackage=()=> 'com.ss.android.ugc.aweme';
      const module={exports:{}};vm.runInNewContext(fs.readFileSync(require.resolve('../core/ui-operator'),'utf8'),Object.assign({},h.sandbox,{module}));
      assert.ok(module.exports.findElement('target',1));
      assert.equal(h.scales[0] && h.scales[0][0],2);
      assert.equal(module.exports.isOnPage('target',10),true);
    });
  }
}
test('unblocked icons crossing a blocker partition seam remain searchable',()=>{
  const h=harness({realGeometry:true,ctx:{width:100,height:100,captureWidth:100,captureHeight:100,captureBounds:{left:0,top:0,right:100,bottom:100},contentBounds:{left:0,top:0,right:100,bottom:100},blockedBounds:[{left:40,top:40,right:60,bottom:60}]}});
  h.sandbox.files.exists=path=>path.endsWith('/100x100/icon.png');
  h.sandbox.images.read=()=>({getWidth:()=>20,getHeight:()=>10,recycle:()=>{}});
  h.sandbox.images.findImage=(screen,tpl,options)=>{
    h.matches.push(options);const r=options.region;
    return r[0]<=0 && r[1]<=35 && r[0]+r[2]>=20 && r[1]+r[3]>=45?{x:0,y:35}:null;
  };
  const found=h.ui._findByImage('icon.png',0.94,{scales:[1]});
  assert.ok(found);assert.equal(found.x,10);assert.equal(found.y,40);
  assert.ok(h.matches.every(m=>m.threshold===0.94));assert.ok(h.matches.length<=32);
});
