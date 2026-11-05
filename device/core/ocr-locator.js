// OCR locations are capture pixels. Text alone is never a click target.
var screenContext = require("./screen-context");

function locateUnique(result, keywords, ctx, region) {
  if (!Array.isArray(result) || !ctx) return null;
  var matches = [];
  for (var i = 0; i < result.length; i++) {
    var item = result[i];
    if (!item || typeof item.text !== "string") continue;
    var clean = item.text.replace(/\s/g, "");
    var matched = false;
    for (var k = 0; k < keywords.length; k++) {
      if (clean.indexOf(keywords[k]) !== -1) { matched = true; break; }
    }
    if (!matched) continue;
    var bounds = screenContext.rect(item.bounds);
    var point = bounds ? { x: (bounds.left + bounds.right) / 2, y: (bounds.top + bounds.bottom) / 2 }
      : { x: item.x, y: item.y };
    if (typeof point.x !== "number" || !isFinite(point.x) || typeof point.y !== "number" || !isFinite(point.y)) continue;
    var mapped = screenContext.captureToScreen(point, ctx);
    if (!mapped || !screenContext.isUsablePoint(mapped, ctx, region)) continue;
    matches.push({ isCoordinate: true, x: mapped.x, y: mapped.y,
      signature: ctx.signature, observedAt: ctx.observedAt });
  }
  return matches.length === 1 ? matches[0] : null;
}

module.exports = { locateUnique: locateUnique };
