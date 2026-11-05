const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const screen = require('../core/screen-context');

function context(overrides) {
  return screen.create(Object.assign({ width: 1080, height: 2400, density: 3 }, overrides));
}

test('normalizes screen coordinates at four resolutions without assuming an aspect ratio', () => {
  [[720, 1600], [1080, 2340], [1080, 2400], [1440, 3200]].forEach(([width, height]) => {
    const ctx = context({ width, height });
    assert.deepEqual(screen.pointForStrategy({ type: 'coordinate', x_percent: 0.25, y_percent: 0.5 }, ctx), { x: width / 4, y: height / 2 });
    assert.deepEqual(screen.pointForStrategy({ position: { space: 'screen_normalized', x: 1, y: 0 } }, ctx), { x: width - 1, y: 0 });
  });
});

test('content and anchor positions use their origins, including split-screen and insets', () => {
  const ctx = context({ contentBounds: { left: 100, top: 80, right: 980, bottom: 1600 } });
  assert.deepEqual(screen.pointForStrategy({ position: { space: 'content_normalized', x: 0.5, y: 0.5 } }, ctx), { x: 540, y: 840 });
  const anchor = { left: 700, top: 1200, right: 900, bottom: 1300 };
  assert.deepEqual(screen.pointForStrategy({ position: { space: 'anchor_normalized', x: 0.5, y: 0.5 } }, ctx, anchor), { x: 800, y: 1250 });
  assert.equal(screen.pointForStrategy({ position: { space: 'anchor_normalized', x: 0.5, y: 0.5 } }, ctx), null);
});

test('invalid coordinate values fail instead of being coerced to usable pixels', () => {
  const ctx = context();
  [undefined, null, NaN, Infinity, '0.5', -0.1, 1.01].forEach(value => {
    assert.equal(screen.normalizedPoint(value, 0.5, ctx.contentBounds), null);
  });
  assert.equal(screen.pointForStrategy({ position: { space: 'other', x: 10, y: 20 } }, ctx), null);
  assert.equal(screen.create({ width: 0, height: 2400 }), null);
});

test('legacy coordinate positions are not applied again as click offsets', () => {
  const ctx = context();
  const strategy = { type: 'coordinate', x_percent: 0.5, y_percent: 0.25, click_mode: 'press' };
  const point = screen.pointForStrategy(strategy, ctx);
  assert.deepEqual(screen.offsetPoint(point, strategy, null, ctx, 'coordinate'), { x: 540, y: 600 });
});

test('legacy node percentage and image pixel offsets keep their original meanings', () => {
  const ctx = context();
  const bounds = { left: 400, top: 1000, right: 600, bottom: 1100 };
  const strategy = { x_percent: 10, y_percent: -20 };
  assert.deepEqual(screen.offsetPoint({ x: 500, y: 1050 }, strategy, bounds, ctx, 'node'), { x: 520, y: 1030 });
  assert.deepEqual(screen.offsetPoint({ x: 500, y: 1050 }, strategy, bounds, ctx, 'image'), { x: 510, y: 1030 });
});

test('explicit offset units override legacy fields and scale dp by density', () => {
  const bounds = { left: 400, top: 1000, right: 600, bottom: 1100 };
  const p = { x: 500, y: 1050 };
  const strategy = { x_percent: 99, y_percent: 99, offset: { unit: 'dp', x: 10, y: -5 } };
  assert.deepEqual(screen.offsetPoint(p, strategy, bounds, context(), 'node'), { x: 530, y: 1035 });
  strategy.offset = { unit: 'target_fraction', x: 0.25, y: -0.5 };
  assert.deepEqual(screen.offsetPoint(p, strategy, bounds, context(), 'image'), { x: 550, y: 1000 });
  assert.equal(screen.offsetPoint(p, strategy, null, context(), 'image'), null);
  strategy.offset = { unit: 'px', x: 0, y: 0 };
  assert.deepEqual(screen.offsetPoint(p, strategy, bounds, context(), 'node'), p);
  strategy.offset = { unit: 'dp', x: NaN, y: 0 };
  assert.equal(screen.offsetPoint(p, strategy, bounds, context(), 'node'), null);
});

test('image capture pixels map through crop and resize rather than screen size alone', () => {
  const ctx = context({ captureBounds: { left: 180, top: 400, right: 900, bottom: 1600 }, captureWidth: 360, captureHeight: 600 });
  assert.deepEqual(screen.captureToScreen({ x: 100, y: 200 }, ctx), { x: 380, y: 800 });
  assert.deepEqual(screen.screenToCapture({ x: 380, y: 800 }, ctx), { x: 100, y: 200 });
  assert.equal(screen.captureToScreen({ x: 360, y: 200 }, ctx), null);
  assert.equal(screen.screenToCapture({ x: 100, y: 800 }, ctx), null);
});

test('explicit capture rotation round trips without guessing swapped dimensions', () => {
  [0, 90, 180, 270].forEach(rotation => {
    const sideways = rotation === 90 || rotation === 270;
    const ctx = context({ captureRotation: rotation, captureWidth: sideways ? 1200 : 540, captureHeight: sideways ? 540 : 1200 });
    const point = { x: 300, y: 900 };
    const captured = screen.screenToCapture(point, ctx);
    assert.ok(captured);
    const restored = screen.captureToScreen(captured, ctx);
    assert.ok(Math.abs(restored.x - point.x) <= 1);
    assert.ok(Math.abs(restored.y - point.y) <= 1);
  });
  const unknown = context({ captureWidth: 1200, captureHeight: 540 });
  assert.equal(unknown.captureValid, false);
  assert.equal(screen.captureToScreen({ x: 300, y: 100 }, unknown), null);
});

test('scope rectangles are clipped to app content and missing or invalid anchors fail closed', () => {
  const ctx = context({ contentBounds: { left: 0, top: 100, right: 1080, bottom: 2000 } });
  assert.deepEqual(screen.regionForStrategy({ region: { space: 'screen_normalized', left: 0, top: 0, right: 1, bottom: 0.5 } }, ctx), { left: 0, top: 100, right: 1080, bottom: 1200 });
  const anchor = { left: 100, top: 300, right: 500, bottom: 500 };
  assert.deepEqual(screen.regionForStrategy({ anchor: { type: 'id', value: 'panel' } }, ctx, anchor), anchor);
  assert.equal(screen.regionForStrategy({ anchor: { type: 'id', value: 'panel' } }, ctx), null);
  assert.equal(screen.regionForStrategy({ region: { space: 'content_normalized', left: 0.8, top: 0, right: 0.2, bottom: 1 } }, ctx), null);
});

test('clickable points exclude screen edges, out-of-window targets, keyboard and foreign foreground', () => {
  const ctx = context({ contentBounds: { left: 0, top: 80, right: 1080, bottom: 2400 }, blockedBounds: [{ left: 0, top: 1500, right: 1080, bottom: 2400 }] });
  assert.equal(screen.isUsablePoint({ x: 0, y: 100 }, ctx), true);
  assert.equal(screen.isUsablePoint({ x: 1080, y: 100 }, ctx), false);
  assert.equal(screen.isUsablePoint({ x: 10, y: 20 }, ctx), false);
  assert.equal(screen.isUsablePoint({ x: 500, y: 1600 }, ctx), false);
  assert.equal(screen.isUsablePoint({ x: NaN, y: 100 }, ctx), false);
  assert.equal(screen.isUsablePoint({ x: 500, y: 100 }, context({ foregroundPackage: 'another.app' })), false);
});

test('layout signatures change with keyboard, window, font and orientation but not capture size or time', () => {
  const base = context();
  assert.equal(context({ captureWidth: 540, captureHeight: 1200, observedAt: 123 }).signature, base.signature);
  assert.notEqual(context({ blockedBounds: [{ left: 0, top: 1500, right: 1080, bottom: 2400 }] }).signature, base.signature);
  assert.notEqual(context({ contentBounds: { left: 0, top: 80, right: 1080, bottom: 2400 } }).signature, base.signature);
  assert.notEqual(context({ fontScale: 1.3 }).signature, base.signature);
  assert.notEqual(context({ rotation: 90 }).signature, base.signature);
});

function runtime(overrides) {
  const sandbox = Object.assign({ module: { exports: {} }, device: { width: 1080, height: 2400 }, Date, Math, isFinite, currentPackage: () => 'com.ss.android.ugc.aweme' }, overrides);
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../core/screen-context.js'), 'utf8'), sandbox);
  return sandbox.module.exports;
}

function windowInfo(pkg, type, layer, bounds, active) {
  return { getRoot: () => ({ getPackageName: () => pkg }), getType: () => type, getLayer: () => layer, isActive: () => !!active, isFocused: () => !!active, getBoundsInScreen: rect => Object.assign(rect, bounds) };
}

test('runtime uses target app window below IME, never the automation app resource bounds', () => {
  const app = windowInfo('com.ss.android.ugc.aweme', 1, 1, { left: 0, top: 90, right: 1080, bottom: 1600 }, false);
  const ime = windowInfo('test.ime', 2, 3, { left: 0, top: 1600, right: 1080, bottom: 2400 }, true);
  const module = runtime({ auto: { windows: [app, ime] }, currentPackage: () => 'test.ime', context: { getResources: () => ({ getDisplayMetrics: () => ({ widthPixels: 800, heightPixels: 600, density: 2.75 }), getConfiguration: () => ({ fontScale: 1.2 }) }) } });
  const ctx = module.read({ getWidth: () => 540, getHeight: () => 1200 });
  assert.equal(ctx.width, 1080);
  assert.equal(ctx.density, 2.75);
  assert.equal(ctx.contentBounds.top, 90);
  assert.equal(ctx.contentBounds.bottom, 1600);
  assert.equal(ctx.captureWidth, 540);
  assert.equal(ctx.canInteract, true);
  assert.equal(module.isUsablePoint({ x: 500, y: 1800 }, ctx), false);
});

test('runtime refreshes display rotation and dimensions at each read', () => {
  let landscape = false;
  const module = runtime({ android: { util: { DisplayMetrics: function () {} } }, context: { getSystemService: () => ({ getDefaultDisplay: () => ({ getRotation: () => landscape ? 1 : 0, getRealMetrics: m => Object.assign(m, { widthPixels: landscape ? 2400 : 1080, heightPixels: landscape ? 1080 : 2400, density: 3 }) }) }) } });
  const before = module.read();
  landscape = true;
  const after = module.read();
  assert.equal(after.width, 2400);
  assert.equal(after.height, 1080);
  assert.equal(after.rotation, 90);
  assert.notEqual(before.signature, after.signature);
});

test('runtime blocks a background target when another application is in front', () => {
  const module = runtime({ currentPackage: () => 'another.app', auto: { windows: [windowInfo('com.ss.android.ugc.aweme', 1, 1, { left: 0, top: 0, right: 1080, bottom: 2400 }, false), windowInfo('another.app', 1, 2, { left: 0, top: 0, right: 1080, bottom: 2400 }, true)] } });
  assert.equal(module.read().canInteract, false);
});
