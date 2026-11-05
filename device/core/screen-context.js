// AutoJS6 / Rhino ES5.1. All public points are physical screen pixels unless
// explicitly named capture pixels. Do not combine this module with setScreenMetrics.
var TARGET_PACKAGE = "com.ss.android.ugc.aweme";

function finite(value) {
  return typeof value === "number" && isFinite(value);
}

function field(value, key) {
  try {
    var result = value[key];
    if (typeof result === "function") result = result.call(value);
    if (result == null) return null;
    result = Number(result);
    return finite(result) ? result : null;
  } catch (e) { return null; }
}

function rect(value) {
  if (!value) return null;
  var left = field(value, "left"), top = field(value, "top");
  var right = field(value, "right"), bottom = field(value, "bottom");
  if (left === null || top === null || right === null || bottom === null || right <= left || bottom <= top) return null;
  return { left: left, top: top, right: right, bottom: bottom };
}

function intersect(a, b) {
  a = rect(a); b = rect(b);
  if (!a || !b) return null;
  return rect({ left: Math.max(a.left, b.left), top: Math.max(a.top, b.top), right: Math.min(a.right, b.right), bottom: Math.min(a.bottom, b.bottom) });
}

function contains(bounds, x, y) {
  bounds = rect(bounds);
  return !!bounds && finite(x) && finite(y) && x >= bounds.left && x < bounds.right && y >= bounds.top && y < bounds.bottom;
}

function validPoint(point) {
  return !!point && finite(point.x) && finite(point.y);
}

function rectKey(bounds) {
  return bounds ? [bounds.left, bounds.top, bounds.right, bounds.bottom].join(",") : "unknown";
}

function create(options) {
  options = options || {};
  if (!finite(options.width) || !finite(options.height) || options.width < 1 || options.height < 1) return null;
  var width = Math.floor(options.width), height = Math.floor(options.height);
  var screenBounds = { left: 0, top: 0, right: width, bottom: height };
  var contentBounds = options.contentBounds === undefined ? screenBounds : intersect(options.contentBounds, screenBounds);
  var captureBounds = options.captureBounds === undefined ? screenBounds : intersect(options.captureBounds, screenBounds);
  var captureWidth = options.captureWidth === undefined ? width : options.captureWidth;
  var captureHeight = options.captureHeight === undefined ? height : options.captureHeight;
  var captureRotation = options.captureRotation === undefined ? 0 : options.captureRotation;
  var validRotation = captureRotation === 0 || captureRotation === 90 || captureRotation === 180 || captureRotation === 270;
  var captureValid = options.captureValid !== false && !!captureBounds && validRotation && finite(captureWidth) && captureWidth >= 1 && finite(captureHeight) && captureHeight >= 1;
  if (captureValid) {
    var sourceWidth = captureBounds.right - captureBounds.left;
    var sourceHeight = captureBounds.bottom - captureBounds.top;
    var sourceRatio = captureRotation === 90 || captureRotation === 270 ? sourceHeight / sourceWidth : sourceWidth / sourceHeight;
    // An unexplained aspect change could be a crop or rotation, not a resize.
    // Allow only rounding differences; callers must identify a crop/rotation.
    captureValid = Math.abs((captureWidth / captureHeight) / sourceRatio - 1) <= 0.02;
  }
  var blocked = [], blockedKeys = [];
  var suppliedBlocks = options.blockedBounds || [];
  for (var i = 0; i < suppliedBlocks.length; i++) {
    var block = intersect(suppliedBlocks[i], screenBounds);
    if (block) { blocked.push(block); blockedKeys.push(rectKey(block)); }
  }
  var targetPackage = options.targetPackage || TARGET_PACKAGE;
  var foregroundPackage = options.foregroundPackage || "";
  var canInteract = typeof options.canInteract === "boolean" ? options.canInteract : (!foregroundPackage || foregroundPackage === targetPackage);
  canInteract = canInteract && !!contentBounds;
  var density = finite(options.density) && options.density > 0 ? options.density : 1;
  var fontScale = finite(options.fontScale) && options.fontScale > 0 ? options.fontScale : 1;
  var rotation = finite(options.rotation) ? options.rotation : 0;
  // Capture size and time must not invalidate a point when read() is called
  // immediately before clicking without another screenshot.
  var signature = [width, height, density, fontScale, rotation, rectKey(contentBounds), blockedKeys.sort().join(";"), targetPackage, foregroundPackage, canInteract ? 1 : 0].join("|");
  return {
    width: width, height: height, density: density, fontScale: fontScale,
    rotation: rotation, contentBounds: contentBounds, blockedBounds: blocked,
    contentKnown: options.contentKnown === true || options.contentBounds !== undefined,
    captureWidth: captureWidth, captureHeight: captureHeight, captureBounds: captureBounds,
    captureRotation: captureRotation, captureValid: captureValid,
    targetPackage: targetPackage, foregroundPackage: foregroundPackage,
    canInteract: canInteract, signature: signature,
    observedAt: finite(options.observedAt) ? options.observedAt : Date.now()
  };
}

function packageOf(node) {
  try {
    if (!node) return "";
    var name = typeof node.packageName === "function" ? node.packageName() : node.getPackageName();
    return name == null ? "" : String(name);
  } catch (e) { return ""; }
}

function boundsOf(value) {
  if (!value) return null;
  try {
    if (typeof value.bounds === "function") return rect(value.bounds());
    if (typeof value.getBoundsInScreen === "function") {
      var bounds;
      if (typeof android !== "undefined" && android.graphics && android.graphics.Rect) bounds = new android.graphics.Rect();
      else bounds = { left: 0, top: 0, right: 0, bottom: 0 };
      value.getBoundsInScreen(bounds);
      return rect(bounds);
    }
  } catch (e) { /* window may disappear while enumerating */ }
  return null;
}

function read(image, options) {
  options = options || {};
  var state = { targetPackage: options.targetPackage || TARGET_PACKAGE };
  try { state.width = Number(device.width); state.height = Number(device.height); } catch (e) {}
  try {
    var resources = context.getResources();
    state.density = Number(resources.getDisplayMetrics().density);
    state.fontScale = Number(resources.getConfiguration().fontScale);
  } catch (e2) {}
  try {
    var display = context.getSystemService("window").getDefaultDisplay();
    state.rotation = Number(display.getRotation()) * 90;
    var metrics = new android.util.DisplayMetrics();
    if (typeof display.getRealMetrics === "function") display.getRealMetrics(metrics);
    else display.getMetrics(metrics);
    if (Number(metrics.widthPixels) > 0 && Number(metrics.heightPixels) > 0) {
      state.width = Number(metrics.widthPixels); state.height = Number(metrics.heightPixels);
      if (Number(metrics.density) > 0) state.density = Number(metrics.density);
    }
  } catch (e3) {}
  var hasForegroundApi = typeof currentPackage === "function";
  try { state.foregroundPackage = String(currentPackage() || ""); } catch (e4) {}

  var windows = [], selected = null;
  try {
    var source = auto.windows;
    var count = source && typeof source.size === "function" ? source.size() : (source ? source.length : 0);
    for (var i = 0; i < count; i++) {
      var win = typeof source.get === "function" ? source.get(i) : source[i];
      try {
        var item = {
          bounds: boundsOf(win), packageName: packageOf(win.getRoot()),
          type: Number(win.getType()), layer: Number(win.getLayer()),
          active: !!win.isActive(), focused: !!win.isFocused()
        };
        if (!item.bounds) continue;
        windows.push(item);
        if (item.type === 1 && item.packageName === state.targetPackage && (!selected || item.layer > selected.layer)) selected = item;
      } catch (windowError) { /* continue other windows */ }
    }
  } catch (e5) {}

  // Fallback remains target-specific: never use AutoJS's own app window insets.
  var activeRoot = null;
  if (!selected) {
    try { activeRoot = auto.rootInActiveWindow || auto.root; } catch (e6) {}
    if (packageOf(activeRoot) === state.targetPackage) {
      var rootBounds = boundsOf(activeRoot);
      if (rootBounds) selected = { bounds: rootBounds, packageName: state.targetPackage, type: 1, layer: -1, active: true, focused: true };
    }
  }
  state.blockedBounds = [];
  var foregroundIsIme = false, otherAppAbove = false;
  for (var wi = 0; wi < windows.length; wi++) {
    var entry = windows[wi];
    if (selected && entry.layer <= selected.layer) continue;
    if (entry.type === 2 && entry.packageName === state.foregroundPackage) foregroundIsIme = true;
    if (entry.type === 1 && entry.packageName !== state.targetPackage && (entry.active || entry.focused || entry.packageName === state.foregroundPackage)) otherAppAbove = true;
    // Accessibility overlays may be non-touchable full-screen containers.
    // Only active/focused overlays establish an obstruction; IME/system windows
    // have concrete screen regions and always exclude those regions.
    if (entry.type === 2 || entry.type === 3 || (entry.type === 4 && (entry.active || entry.focused)) || (entry.type === 1 && entry.packageName !== state.targetPackage)) state.blockedBounds.push(entry.bounds);
  }
  if (selected) { state.contentBounds = selected.bounds; state.contentKnown = true; }
  state.canInteract = !otherAppAbove && (state.foregroundPackage === state.targetPackage || (!!selected && foregroundIsIme) || (!state.foregroundPackage && !!selected) || !hasForegroundApi);

  for (var key in options) {
    if (Object.prototype.hasOwnProperty.call(options, key)) state[key] = options[key];
  }
  if (image) {
    try { state.captureWidth = Number(image.getWidth()); state.captureHeight = Number(image.getHeight()); }
    catch (captureError) { state.captureValid = false; }
  }
  return create(state);
}

function normalizedPoint(x, y, bounds) {
  bounds = rect(bounds);
  if (!bounds || !finite(x) || !finite(y) || x < 0 || x > 1 || y < 0 || y > 1) return null;
  return {
    x: Math.max(Math.ceil(bounds.left), Math.min(Math.ceil(bounds.right) - 1, Math.round(bounds.left + x * (bounds.right - bounds.left)))),
    y: Math.max(Math.ceil(bounds.top), Math.min(Math.ceil(bounds.bottom) - 1, Math.round(bounds.top + y * (bounds.bottom - bounds.top))))
  };
}

function captureToScreen(point, ctx) {
  if (!ctx || !ctx.captureValid || !validPoint(point) || point.x < 0 || point.y < 0 || point.x >= ctx.captureWidth || point.y >= ctx.captureHeight) return null;
  var u = point.x / Math.max(1, ctx.captureWidth - 1), v = point.y / Math.max(1, ctx.captureHeight - 1);
  var x = u, y = v;
  if (ctx.captureRotation === 90) { x = v; y = 1 - u; }
  else if (ctx.captureRotation === 180) { x = 1 - u; y = 1 - v; }
  else if (ctx.captureRotation === 270) { x = 1 - v; y = u; }
  var b = ctx.captureBounds;
  return { x: Math.round(b.left + x * Math.max(0, b.right - b.left - 1)), y: Math.round(b.top + y * Math.max(0, b.bottom - b.top - 1)) };
}

function screenToCapture(point, ctx) {
  if (!ctx || !ctx.captureValid || !validPoint(point) || !contains(ctx.captureBounds, point.x, point.y)) return null;
  var b = ctx.captureBounds;
  var u = (point.x - b.left) / Math.max(1, b.right - b.left - 1), v = (point.y - b.top) / Math.max(1, b.bottom - b.top - 1);
  var x = u, y = v;
  if (ctx.captureRotation === 90) { x = 1 - v; y = u; }
  else if (ctx.captureRotation === 180) { x = 1 - u; y = 1 - v; }
  else if (ctx.captureRotation === 270) { x = v; y = 1 - u; }
  return { x: Math.max(0, Math.min(ctx.captureWidth - 1, Math.round(x * (ctx.captureWidth - 1)))), y: Math.max(0, Math.min(ctx.captureHeight - 1, Math.round(y * (ctx.captureHeight - 1)))) };
}

function spaceBounds(space, ctx, anchorBounds) {
  if (!ctx) return null;
  if (space === "screen_normalized") return { left: 0, top: 0, right: ctx.width, bottom: ctx.height };
  if (space === "content_normalized") return ctx.contentBounds;
  if (space === "anchor_normalized") return rect(anchorBounds);
  return null;
}

function regionForStrategy(strategy, ctx, anchorBounds) {
  if (!ctx || !ctx.contentBounds) return null;
  strategy = strategy || {};
  if (strategy.anchor && !rect(anchorBounds)) return null;
  if (!strategy.region) return intersect(strategy.anchor ? anchorBounds : ctx.contentBounds, ctx.contentBounds);
  var region = strategy.region;
  var base = spaceBounds(region.space, ctx, anchorBounds);
  if (!base || !finite(region.left) || !finite(region.top) || !finite(region.right) || !finite(region.bottom) || region.left < 0 || region.top < 0 || region.right > 1 || region.bottom > 1 || region.left >= region.right || region.top >= region.bottom) return null;
  var width = base.right - base.left, height = base.bottom - base.top;
  return intersect({ left: base.left + region.left * width, top: base.top + region.top * height, right: base.left + region.right * width, bottom: base.top + region.bottom * height }, ctx.contentBounds);
}

function pointForStrategy(strategy, ctx, anchorBounds) {
  if (!strategy || !ctx) return null;
  var position = strategy.position;
  if (!position) return normalizedPoint(strategy.x_percent, strategy.y_percent, spaceBounds("screen_normalized", ctx));
  if (!validPoint(position)) return null;
  if (position.space === "screen_px") return { x: Math.round(position.x), y: Math.round(position.y) };
  if (position.space === "capture_px") return captureToScreen(position, ctx);
  return normalizedPoint(position.x, position.y, spaceBounds(position.space, ctx, anchorBounds));
}

function dp(value, ctx) {
  if (!finite(value) || !ctx || !finite(ctx.density) || ctx.density <= 0) return null;
  return value * ctx.density;
}

function offsetPoint(point, strategy, targetBounds, ctx, kind) {
  if (!validPoint(point) || !ctx) return null;
  strategy = strategy || {};
  var x = 0, y = 0, unit = "px";
  if (strategy.offset) {
    x = strategy.offset.x === undefined ? 0 : strategy.offset.x;
    y = strategy.offset.y === undefined ? 0 : strategy.offset.y;
    unit = strategy.offset.unit;
  } else if (kind !== "coordinate") {
    x = strategy.x_percent == null ? 0 : strategy.x_percent;
    y = strategy.y_percent == null ? 0 : strategy.y_percent;
    if (!finite(x) || !finite(y)) return null;
    if (kind === "node") { x = x / 100; y = y / 100; unit = "target_fraction"; }
  }
  if (!finite(x) || !finite(y)) return null;
  if (unit === "dp") { x = dp(x, ctx); y = dp(y, ctx); }
  else if (unit === "target_fraction") {
    var bounds = rect(targetBounds);
    if (!bounds) return null;
    x *= bounds.right - bounds.left; y *= bounds.bottom - bounds.top;
  } else if (unit !== "px") return null;
  if (!finite(x) || !finite(y)) return null;
  return { x: Math.round(point.x + x), y: Math.round(point.y + y) };
}

function isUsablePoint(point, ctx, region) {
  if (!ctx || !ctx.canInteract || !validPoint(point) || !contains({ left: 0, top: 0, right: ctx.width, bottom: ctx.height }, point.x, point.y) || !contains(ctx.contentBounds, point.x, point.y)) return false;
  if (region && !contains(region, point.x, point.y)) return false;
  for (var i = 0; i < ctx.blockedBounds.length; i++) {
    if (contains(ctx.blockedBounds[i], point.x, point.y)) return false;
  }
  return true;
}

module.exports = {
  create: create, read: read, rect: rect, intersect: intersect, contains: contains,
  normalizedPoint: normalizedPoint, captureToScreen: captureToScreen, screenToCapture: screenToCapture,
  regionForStrategy: regionForStrategy, pointForStrategy: pointForStrategy,
  offsetPoint: offsetPoint, isUsablePoint: isUsablePoint, dp: dp
};
