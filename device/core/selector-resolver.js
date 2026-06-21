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

  // 设备业务函数：处理 findByStrategyInParent 对应的抖音自动化动作、状态或安全边界。
  findByStrategyInParent: function (parent, strategy) {
    if (strategy.conditions && strategy.conditions.length > 0) {
      return selectorResolver.findByConditionsInParent(parent, strategy);
    }
    if (strategy.type === "chain") {
      return selectorResolver.findByChainInParent(parent, strategy.steps || []);
    }
    return selectorResolver.findByCondInParent(parent, strategy);
  },

  // 设备业务函数：处理 findByCondInParent 对应的抖音自动化动作、状态或安全边界。
  findByCondInParent: function (parent, cond) {
    var matchMode = cond.match_mode || "exact";
    try {
      if (cond.type === "textContains") return parent.findOne(textContains(cond.value));

      if (matchMode === "contains") {
        switch (cond.type) {
          case "text": return parent.findOne(textContains(cond.value));
          case "desc": return parent.findOne(descContains(cond.value));
          case "id": return parent.findOne(idContains(cond.value));
          case "className": return parent.findOne(classNameContains(cond.value));
        }
      } else {
        switch (cond.type) {
          case "text": return parent.findOne(text(cond.value));
          case "desc": return parent.findOne(desc(cond.value));
          case "id": return parent.findOne(id(cond.value));
          case "className": return parent.findOne(className(cond.value));
        }
      }
    } catch (e) {}
    return null;
  },

  // 设备业务函数：处理 findAllByCondInParent 对应的抖音自动化动作、状态或安全边界。
  findAllByCondInParent: function (parent, cond) {
    var matchMode = cond.match_mode || "exact";
    try {
      if (cond.type === "textContains") return parent.find(textContains(cond.value));

      if (matchMode === "contains") {
        switch (cond.type) {
          case "text": return parent.find(textContains(cond.value));
          case "desc": return parent.find(descContains(cond.value));
          case "id": return parent.find(idContains(cond.value));
          case "className": return parent.find(classNameContains(cond.value));
        }
      } else {
        switch (cond.type) {
          case "text": return parent.find(text(cond.value));
          case "desc": return parent.find(desc(cond.value));
          case "id": return parent.find(id(cond.value));
          case "className": return parent.find(className(cond.value));
        }
      }
    } catch (e) {}
    return [];
  },

  // 设备业务函数：处理 findByConditionsInParent 对应的抖音自动化动作、状态或安全边界。
  findByConditionsInParent: function (parent, strategy) {
    var conditions = strategy.conditions;
    var logic = strategy.logic || "and";

    if (conditions.length === 1) {
      return selectorResolver.findByCondInParent(parent, conditions[0]);
    }

    if (logic === "or") {
      for (var j = 0; j < conditions.length; j++) {
        var el = selectorResolver.findByCondInParent(parent, conditions[j]);
        if (el) return el;
      }
      return null;
    }

    var candidates = selectorResolver.findAllByCondInParent(parent, conditions[0]);
    for (var m = 0; m < candidates.length; m++) {
      var allMatch = true;
      for (var n = 1; n < conditions.length; n++) {
        if (!uiOperator._elementMatchesCondition(candidates[m], conditions[n])) {
          allMatch = false;
          break;
        }
      }
      if (allMatch) return candidates[m];
    }
    return null;
  },

  // 设备业务函数：处理 findByChainInParent 对应的抖音自动化动作、状态或安全边界。
  findByChainInParent: function (parent, steps) {
    if (!steps || steps.length === 0) return null;

    // Phase 1: build selector chain from filter steps
    var sel = null;
    var navStartIdx = steps.length;
    for (var i = 0; i < steps.length; i++) {
      var nav = steps[i].nav || "filter";
      if (nav !== "filter") { navStartIdx = i; break; }
      if (!sel) { sel = uiOperator._makeSelector(steps[i]); }
      else { sel = uiOperator._chainSelector(sel, steps[i]); }
      if (!sel) return null;
    }

    // Phase 2: find first matching element within parent
    var el = null;
    if (sel) {
      var candidates = parent.find(sel);
      if (candidates && candidates.length > 0) {
        for (var k = 0; k < candidates.length; k++) {
          if (uiOperator._isOnScreen(candidates[k])) { el = candidates[k]; break; }
        }
      }
    } else {
      el = parent;
    }
    if (!el) return null;

    // Phase 3: walk the tree with nav steps
    for (var m = navStartIdx; m < steps.length; m++) {
      var navStep = steps[m];
      var navAction = navStep.nav || "filter";
      if (navAction === "parent") {
        try { el = el.parent(); } catch (e) { return null; }
        if (!el) return null;
      } else if (navAction === "child") {
        var childSel = uiOperator._makeSelector(navStep);
        if (!childSel) return null;
        try {
          var children = el.find(childSel);
          if (!children || children.length === 0) return null;
          var idx = navStep.index || 0;
          var found = 0; el = null;
          for (var c = 0; c < children.length; c++) {
            if (uiOperator._isOnScreen(children[c])) {
              if (found === idx) { el = children[c]; break; }
              found++;
            }
          }
          if (!el) return null;
        } catch (e) { return null; }
      } else if (navAction === "sibling") {
        var siblingSel = uiOperator._makeSelector(navStep);
        if (!siblingSel) return null;
        try {
          var p = el.parent();
          if (!p) return null;
          var siblings = p.find(siblingSel);
          if (!siblings || siblings.length === 0) return null;
          var sibIdx = navStep.index || 0;
          var sf = 0; el = null;
          for (var s = 0; s < siblings.length; s++) {
            if (uiOperator._isOnScreen(siblings[s])) {
              if (sf === sibIdx) { el = siblings[s]; break; }
              sf++;
            }
          }
          if (!el) return null;
        } catch (e) { return null; }
      } else {
        if (!uiOperator._elementMatchesStep(el, navStep)) return null;
      }
    }
    return el;
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
