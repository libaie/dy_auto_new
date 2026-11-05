// AutoJS6 / Rhino ES5.1. Match capture pixels, then map to physical pixels.
var geometry = require("./screen-context");

function finite(value) { return typeof value === "number" && isFinite(value); }
function recycle(image) { if (image) { try { image.recycle(); } catch (e) {} } }

function candidates(template, ctx, absolute, profile) {
  if (!template || typeof template !== "string") return [];
  if (absolute || template.charAt(0) === "/") return [{ path: template, name: template, primary:true }];
  var root = "/sdcard/dy_auto/templates/";
  var resolution = ctx.width + "x" + ctx.height;
  var selected = profile === undefined || profile === null ? resolution : profile;
  if (typeof selected !== "string" || !/^(default|\d+x\d+)$/.test(selected)) return [];
  var dirs = [root + selected + "/"], result = [], seen = {};
  if (selected !== resolution) dirs.push(root + resolution + "/");
  try {
    if (files.isDir(root)) {
      var entries = files.listDir(root);
      for (var i = 0; i < entries.length; i++) {
        if (/^\d+x\d+$/.test(entries[i]) && entries[i] !== resolution && files.isDir(root + entries[i])) dirs.push(root + entries[i] + "/");
      }
    }
  } catch (e) {}
  dirs.push(root + "default/");
  var dot = template.lastIndexOf("."), base = dot > 0 ? template.substring(0, dot) : template;
  var extension = dot > 0 ? template.substring(dot) : "";
  function add(dir, name) {
    var path = dir + name;
    if (seen[path]) return;
    seen[path] = true;
    try { if (!files.exists(path)) return; } catch (e) {}
    result.push({ path: path, name: name, primary:name === template && dir === root + selected + "/" });
  }
  for (var d = 0; d < dirs.length; d++) {
    add(dirs[d], template);
    if (base.indexOf("@") < 0 && extension) add(dirs[d], base + "@" + resolution + extension);
    try {
      if (!files.isDir(dirs[d])) continue;
      var names = files.listDir(dirs[d]);
      for (var n = 0; n < names.length; n++) {
        if (/\.(png|jpe?g)$/i.test(names[n]) && (names[n].indexOf(base + "@") === 0 || names[n].indexOf(base + "_") === 0)) add(dirs[d], names[n]);
      }
    } catch (e2) {}
  }
  return result;
}

function scaleFactors(strategy, candidate, ctx) {
  var supplied = strategy.scales;
  if (supplied !== undefined) {
    if (!(supplied instanceof Array) && Object.prototype.toString.call(supplied) !== "[object Array]") return null;
    if (!supplied.length || supplied.length > 5) return null;
    for (var i = 0; i < supplied.length; i++) if (!finite(supplied[i]) || supplied[i] < 0.25 || supplied[i] > 4) return null;
    return supplied;
  }
  var bounds = ctx.captureBounds;
  var rotated = ctx.captureRotation === 90 || ctx.captureRotation === 270;
  var captureScale = ctx.captureWidth / (rotated ? bounds.bottom - bounds.top : bounds.right - bounds.left);
  var factor = captureScale;
  var source = candidate.path.match(/@(\d+x\d+)/) || candidate.path.match(/\/(\d+x\d+)\//);
  var assetResolution = source ? source[1] : null;
  // Metadata belongs to the referenced asset, never to similarly named files
  // in another resolution directory or a filename variant. Known fallback
  // provenance wins; unknown fallback provenance cannot use another file's data.
  var metadataApplies = candidate.primary;
  if (!metadataApplies && !assetResolution && (strategy.source_density !== undefined || strategy.source_resolution !== undefined)) return null;
  if (metadataApplies && strategy.source_density !== undefined) {
    if (!finite(strategy.source_density) || strategy.source_density <= 0) return null;
    factor *= ctx.density / strategy.source_density;
  } else {
    var resolution = metadataApplies && strategy.source_resolution ? strategy.source_resolution : assetResolution;
    if (resolution) {
      var parts = /^(\d+)x(\d+)$/.exec(resolution);
      if (!parts || Number(parts[1]) < 1 || Number(parts[2]) < 1) return null;
      factor *= Math.min(ctx.width / Number(parts[1]), ctx.height / Number(parts[2]));
    }
  }
  var result = [], attempts = [factor, factor * 0.95, factor * 1.05];
  for (var a = 0; a < attempts.length; a++) {
    if (finite(attempts[a]) && attempts[a] >= 0.25 && attempts[a] <= 4) result.push(attempts[a]);
  }
  return result;
}

function captureRegion(region, ctx) {
  var clipped = geometry.intersect(region, ctx.captureBounds);
  if (!clipped) return null;
  var corners = [
    { x: Math.ceil(clipped.left), y: Math.ceil(clipped.top) },
    { x: Math.ceil(clipped.right) - 1, y: Math.ceil(clipped.top) },
    { x: Math.ceil(clipped.left), y: Math.ceil(clipped.bottom) - 1 },
    { x: Math.ceil(clipped.right) - 1, y: Math.ceil(clipped.bottom) - 1 }
  ];
  var left = ctx.captureWidth, top = ctx.captureHeight, right = 0, bottom = 0;
  for (var i = 0; i < corners.length; i++) {
    var point = geometry.screenToCapture(corners[i], ctx);
    if (!point) return null;
    left = Math.min(left, point.x); top = Math.min(top, point.y);
    right = Math.max(right, point.x + 1); bottom = Math.max(bottom, point.y + 1);
  }
  left = Math.max(0, Math.ceil(left)); top = Math.max(0, Math.ceil(top));
  right = Math.min(ctx.captureWidth, Math.floor(right)); bottom = Math.min(ctx.captureHeight, Math.floor(bottom));
  return right > left && bottom > top ? [left, top, right - left, bottom - top] : null;
}

// Keep overlapping maximal free rectangles rather than a disjoint partition:
// a fully visible icon crossing an artificial split must fit one search ROI.
// Prune redundant contained rectangles and bound the remaining search work.
function unblockedRegions(region, ctx) {
  var regions = [region], blocks = ctx.blockedBounds || [];
  for (var b = 0; b < blocks.length; b++) {
    var next = [];
    for (var r = 0; r < regions.length; r++) {
      var current = regions[r], overlap = geometry.intersect(current,blocks[b]);
      if (!overlap) { next.push(current); continue; }
      var pieces = [
        {left:current.left,top:current.top,right:current.right,bottom:overlap.top},
        {left:current.left,top:overlap.bottom,right:current.right,bottom:current.bottom},
        {left:current.left,top:current.top,right:overlap.left,bottom:current.bottom},
        {left:overlap.right,top:current.top,right:current.right,bottom:current.bottom}
      ];
      for (var p = 0; p < pieces.length; p++) {
        if (pieces[p].left < pieces[p].right && pieces[p].top < pieces[p].bottom) next.push(pieces[p]);
      }
    }
    var maximal = [];
    for (var i = 0; i < next.length; i++) {
      var contained = false;
      for (var j = 0; j < next.length; j++) {
        if (i === j) continue;
        var a = next[i], other = next[j];
        if (a.left >= other.left && a.top >= other.top && a.right <= other.right && a.bottom <= other.bottom && (a.left > other.left || a.top > other.top || a.right < other.right || a.bottom < other.bottom || j < i)) { contained = true; break; }
      }
      if (!contained) maximal.push(next[i]);
    }
    if (maximal.length > 32) return null;
    regions = maximal;
    if (!regions.length) break;
  }
  return regions;
}

function find(template, strategy, initialContext, anchorBounds, absolute, profile) {
  strategy = strategy || {};
  var threshold = strategy.threshold === undefined ? 0.8 : strategy.threshold;
  if (!finite(threshold) || threshold < 0 || threshold > 1) return null;
  var screen = null;
  try {
    screen = images.captureScreen();
    if (!screen) return null;
    var ctx = geometry.read(screen);
    if (!ctx || !ctx.captureValid || !ctx.canInteract || (initialContext && initialContext.signature !== ctx.signature)) return null;
    var region = geometry.regionForStrategy(strategy, ctx, anchorBounds);
    if (!region) return null;
    var visibleRegions = unblockedRegions(region,ctx);
    if (!visibleRegions) return null;
    var searchRegions = [];
    for (var vr = 0; vr < visibleRegions.length; vr++) {
      var searchRegion = captureRegion(visibleRegions[vr],ctx);
      if (!searchRegion) continue;
      // Historical findImageClick region is [capture-x, capture-y, width, height].
      if (strategy.captureRegion) {
        var legacy = strategy.captureRegion;
        if (legacy.length !== 4 || !finite(legacy[0]) || !finite(legacy[1]) || !finite(legacy[2]) || !finite(legacy[3]) || legacy[2] <= 0 || legacy[3] <= 0) return null;
        var clipped = geometry.intersect({left:searchRegion[0],top:searchRegion[1],right:searchRegion[0]+searchRegion[2],bottom:searchRegion[1]+searchRegion[3]}, {left:legacy[0],top:legacy[1],right:legacy[0]+legacy[2],bottom:legacy[1]+legacy[3]});
        if (!clipped) continue;
        searchRegion = [Math.ceil(clipped.left),Math.ceil(clipped.top),Math.floor(clipped.right)-Math.ceil(clipped.left),Math.floor(clipped.bottom)-Math.ceil(clipped.top)];
      }
      if (searchRegion[2] > 0 && searchRegion[3] > 0) searchRegions.push(searchRegion);
    }
    if (!searchRegions.length) return null;
    var list = candidates(template, ctx, absolute, profile);
    for (var c = 0; c < list.length; c++) {
      var factors = scaleFactors(strategy, list[c], ctx);
      if (!factors || !factors.length) continue;
      var tpl = null;
      try {
        tpl = images.read(list[c].path);
        if (!tpl) continue;
        for (var f = 0; f < factors.length; f++) {
          var predictedWidth = Math.max(1,Math.ceil(tpl.getWidth()*factors[f]));
          var predictedHeight = Math.max(1,Math.ceil(tpl.getHeight()*factors[f]));
          var fits = false;
          for (var fit = 0; fit < searchRegions.length; fit++) {
            if (predictedWidth <= searchRegions[fit][2] && predictedHeight <= searchRegions[fit][3]) { fits = true; break; }
          }
          if (!fits) continue;
          var scaled = null;
          try {
            var candidate = tpl;
            if (Math.abs(factors[f] - 1) > 0.000001) {
              scaled = images.scale(tpl, factors[f], factors[f]);
              if (!scaled) continue;
              candidate = scaled;
            }
            for (var sr = 0; sr < searchRegions.length; sr++) {
              var attemptRegion = searchRegions[sr];
              if (candidate.getWidth() > attemptRegion[2] || candidate.getHeight() > attemptRegion[3]) continue;
              var match = images.findImage(screen,candidate,{threshold:threshold,region:attemptRegion});
              if (!match) continue;
              var center = geometry.captureToScreen({x:match.x+candidate.getWidth()/2,y:match.y+candidate.getHeight()/2},ctx);
              var first = geometry.captureToScreen({x:match.x,y:match.y},ctx);
              var last = geometry.captureToScreen({x:match.x+candidate.getWidth()-1,y:match.y+candidate.getHeight()-1},ctx);
              if (!geometry.isUsablePoint(center,ctx,region) || !first || !last) continue;
              var targetBounds = {left:Math.min(first.x,last.x),top:Math.min(first.y,last.y),right:Math.max(first.x,last.x)+1,bottom:Math.max(first.y,last.y)+1};
              return {bounds:targetBounds,isImage:true,x:center.x,y:center.y,signature:ctx.signature,observedAt:ctx.observedAt,region:region,targetBounds:targetBounds};
            }
          } finally { if (scaled && scaled !== tpl) recycle(scaled); }
        }
      } finally { recycle(tpl); }
    }
    return null;
  } catch (e) { return null; }
  finally { recycle(screen); }
}

module.exports = {find:find};
