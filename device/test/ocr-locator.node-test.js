const assert = require('node:assert/strict');
const {test} = require('node:test');
const geometry = require('../core/screen-context');
const locator = require('../core/ocr-locator');

for (const [width,height] of [[720,1600],[1080,2340],[1080,2400],[1440,3200]]) {
  test('OCR maps resized capture into current physical content '+width+'x'+height,()=>{
    const ctx=geometry.create({width,height,captureWidth:width/2,captureHeight:height/2,density:width/360});
    const bounds={left:100,top:100,right:140,bottom:120};
    const result=locator.locateUnique([{text:'最新发布',bounds}],['最新'],ctx,ctx.contentBounds);
    const expected=geometry.captureToScreen({x:120,y:110},ctx);
    assert.equal(result.x,expected.x);assert.equal(result.y,expected.y);
    assert.equal(result.signature,ctx.signature);assert.equal(result.observedAt,ctx.observedAt);
  });
}

test('OCR rejects text-only, missing coordinates, invalid capture and ambiguous matches',()=>{
  const ctx=geometry.create({width:720,height:1600});
  for(const result of ['最新发布',[{text:'最新发布'}],[{text:'最新发布',x:NaN,y:100}],[{text:'最新发布',x:100,y:100},{text:'最新发布',x:200,y:100}]]) {
    assert.equal(locator.locateUnique(result,['最新'],ctx,ctx.contentBounds),null);
  }
  const bad=geometry.create({width:720,height:1600,captureWidth:800,captureHeight:360});
  assert.equal(locator.locateUnique([{text:'最新',x:100,y:100}],['最新'],bad,bad.contentBounds),null);
});

test('OCR uses scoped region and excludes keyboard-covered candidates',()=>{
  const ctx=geometry.create({width:720,height:1600,blockedBounds:[{left:0,top:1000,right:720,bottom:1600}]});
  const scope={left:400,top:200,right:700,bottom:1000};
  const result=locator.locateUnique([{text:'最新',x:100,y:300},{text:'最新',x:500,y:400},{text:'最新',x:500,y:1200}],['最新'],ctx,scope);
  assert.equal(result.x,500);assert.equal(result.y,400);
});

test('OCR zero coordinates remain valid and explicit rotated capture is mapped',()=>{
  const ctx=geometry.create({width:720,height:1600});
  assert.equal(locator.locateUnique([{text:'最新',x:0,y:0}],['最新'],ctx,ctx.contentBounds).x,0);
  const rotated=geometry.create({width:720,height:1600,captureWidth:800,captureHeight:360,captureRotation:90});
  const actual=locator.locateUnique([{text:'最新',x:400,y:180}],['最新'],rotated,rotated.contentBounds);
  const expected=geometry.captureToScreen({x:400,y:180},rotated);
  assert.equal(actual.x,expected.x);assert.equal(actual.y,expected.y);
});

test('OCR capture crop maps only into its known screen bounds',()=>{
  const ctx=geometry.create({width:1080,height:2400,captureWidth:300,captureHeight:400,captureBounds:{left:300,top:500,right:900,bottom:1300}});
  const result=locator.locateUnique([{text:'最新',x:0,y:0}],['最新'],ctx,ctx.contentBounds);
  assert.equal(result.x,300);assert.equal(result.y,500);
});
