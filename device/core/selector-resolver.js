// device/core/selector-resolver.js
// 策略驱动的子元素查找 — 从 BaseHandler 和 comment-utils 抽离的公共逻辑
// 供 base-handler.js 和 comment-utils.js 共同使用

var uiOperator = require("./ui-operator");
var selectorLoader = require("./selector-loader");

var selectorResolver = {

  /**
   * 在父元素内按选择器策略查找子元素
   */
  findChildBySelector: function (parent, actionName) {
    var selector = selectorLoader.get(actionName);
    if (!selector) return null;
    var strategies = selector.strategies.slice().sort(function (a, b) { return a.priority - b.priority; });
    for (var i = 0; i < strategies.length; i++) {
      var el = selectorResolver.findByStrategyInParent(parent, strategies[i]);
      if (el) return el;
    }
    return null;
  },

  findByStrategyInParent: function (parent, strategy) {
    if (!parent || !strategy) return null;
    try {
      // Reuse the same live region/anchor checks as top-level semantic lookups.
      // Keep native nodes so extraction and image calibration remain compatible.
      var candidates = uiOperator._findManyByStrategy(strategy, null, null, parent);
      return candidates.length ? candidates[0] : null;
    } catch (e) { return null; }
  },

  findByCondInParent: function (parent, cond) {
    return selectorResolver.findByStrategyInParent(parent, cond);
  },

  findAllByCondInParent: function (parent, cond) {
    if (!parent || !cond) return [];
    try { return uiOperator._findManyByStrategy(cond, null, null, parent); }
    catch (e) { return []; }
  },

  findByConditionsInParent: function (parent, strategy) {
    return selectorResolver.findByStrategyInParent(parent, strategy);
  },

  findByChainInParent: function (parent, steps) {
    return selectorResolver.findByStrategyInParent(parent, { type: "chain", steps: steps || [] });
  },

  /**
   * 从子元素提取值
   */
  extractChildValue: function (el, actionName, fallback) {
    try {
      var selector = selectorLoader.get(actionName);
      if (selector && selector.purpose === "extract") {
        var val = uiOperator.extractValue(el, selector);
        if (val != null) return val;
      }
      if (el.text && typeof el.text === "function") {
        return el.text() || fallback;
      }
      try { return el.desc() || fallback; } catch (e) { return fallback; }
    } catch (e) { return fallback; }
  },
};

module.exports = selectorResolver;
