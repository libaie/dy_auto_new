var selectorLoader = require("./selector-loader");
var apiClient = require("./api-client");
var logger = require("../utils/logger");
var geometry = require("./screen-context");
var imageLocator = require("./image-locator");

var TAG = "界面操作";

// Keep metadata outside Java UiObjects: callers still receive the native node.
// Values never retain their weak key. Rhino uses Java's synchronized weak map;
// runtimes with WeakMap may use it, without requiring ES6 syntax or APIs.
var nodeScopeMap = null, nodeScopeFallback = [], nodeScopeStoreFailed = false;
try {
  if (typeof java !== "undefined" && java.util && java.util.WeakHashMap && java.util.Collections) {
    nodeScopeMap = {javaMap:java.util.Collections.synchronizedMap(new java.util.WeakHashMap())};
  }
} catch (scopeStoreError) { nodeScopeStoreFailed = true; }
if (!nodeScopeMap && !nodeScopeStoreFailed && typeof WeakMap === "function") {
  try { nodeScopeMap = {jsMap:new WeakMap()}; } catch (weakMapError) { nodeScopeStoreFailed = true; }
}

function scopeStrategy(strategy) {
  var copy = {};
  if (strategy.anchor) copy.anchor = JSON.parse(JSON.stringify(strategy.anchor));
  if (strategy.region) copy.region = JSON.parse(JSON.stringify(strategy.region));
  return copy;
}


var uiOperator = {
  /**
   * 启动抖音
   * @returns {boolean}
   */
  openApp: function () {
    var TARGET_PKG = "com.ss.android.ugc.aweme";
    logger.info(TAG, "正在打开抖音...");

    var pkg = currentPackage();
    if (pkg === TARGET_PKG) {
      logger.info(TAG, "抖音已在前台");
      return true;
    }

    // 键盘覆盖兜底：输入法弹出时 currentPackage() 返回键盘包名, 先关键盘
    if (pkg && (pkg.indexOf("inputmethod") !== -1 || pkg.indexOf("keyboard") !== -1)) {
      logger.info(TAG, "输入法覆盖(" + pkg + "), 关闭键盘后重试");
      // 多策略关闭键盘：back → home → 暴力杀键盘
      try { back(); sleep(800); } catch (e) {}
      if (currentPackage() === TARGET_PKG) {
        logger.info(TAG, "关闭键盘后抖音已在前台");
        return true;
      }
      // back() 不够，尝试 home() 退回桌面再启动
      try { home(); sleep(1000); } catch (e) {}
      pkg = currentPackage();
      if (pkg === TARGET_PKG) {
        logger.info(TAG, "home 后抖音已在前台");
        return true;
      }
      // 键盘仍然在前台，直接用包名启动抖音（绕过键盘拦截）
      if (pkg && (pkg.indexOf("inputmethod") !== -1 || pkg.indexOf("keyboard") !== -1)) {
        logger.info(TAG, "键盘顽固残留(" + pkg + ")，尝试强行启动抖音");
        try {
          app.startActivity({ packageName: TARGET_PKG, className: "com.ss.android.ugc.aweme.splash.SplashActivity" });
        } catch (e2) {
          app.launchPackage(TARGET_PKG);
        }
        sleep(2000);
        if (currentPackage() === TARGET_PKG) {
          logger.info(TAG, "强制启动抖音成功");
          return true;
        }
      }
    }

    app.launchApp("抖音");

    for (var i = 0; i < 3; i++) {
      sleep(3000);
      pkg = currentPackage();
      if (pkg === TARGET_PKG) {
        logger.info(TAG, "抖音打开成功");
        try { app.openUrl("snssdk1128://feed"); sleep(2000); } catch (e) {}
        return true;
      }
      logger.warn(TAG, "等待抖音启动 (" + (i + 1) + "/3), 当前包名: " + pkg);
    }

    var finalPkg = currentPackage();
    logger.error(TAG, "打开抖音失败, 当前包名: " + finalPkg + " (期望: " + TARGET_PKG + ")");
    return false;
  },

  /**
   * 关闭抖音
   */
  closeApp: function () {
    logger.info(TAG, "正在返回桌面...");
    try {
      home();
    } catch (e) {
      // home() 失败不阻塞
    }
    sleep(1000);
  },

  /**
   * 检查抖音是否在前台
   * @returns {boolean}
   */
  isAppActive: function () {
    var pkg = currentPackage();
    if (pkg === "com.ss.android.ugc.aweme") return true;
    // 部分场景下 currentPackage 返回系统 UI 或空，也视为抖音未在前台
    logger.debug(TAG, "抖音未在前台, 当前包名: " + pkg);
    return false;
  },

  /**
   * 判断元素是否在当前屏幕内
   */
  _sameNode: function (first, second) {
    if (first === second) return true;
    try { return !!first && typeof first.equals === "function" && first.equals(second) === true; } catch (e) { return false; }
  },

  _appendDistinctNode: function (list, node) {
    for (var i = 0; i < list.length; i++) if (this._sameNode(list[i],node)) return;
    list.push(node);
  },

  _nodeScopeRecord: function (node) {
    if (nodeScopeMap) return nodeScopeMap.javaMap ? nodeScopeMap.javaMap.get(node) : nodeScopeMap.jsMap.get(node);
    for (var i = 0; i < nodeScopeFallback.length; i++) if (this._sameNode(nodeScopeFallback[i].node,node)) return nodeScopeFallback[i].record;
    return null;
  },

  _rememberNodeScope: function (node, strategy) {
    if (nodeScopeStoreFailed) return false;
    try {
      var value = scopeStrategy(strategy);
      var anchor = value.anchor || {}, region = value.region || {};
      var key = JSON.stringify([anchor.type || null,anchor.value || null,anchor.match_mode || "exact",region.space || null,region.left,region.top,region.right,region.bottom]);
      var previous = this._nodeScopeRecord(node);
      // Raw aliases cannot encode which lookup a caller retained. Remember the
      // conflict rather than replacing or clearing either caller's restriction.
      var record = previous || {strategy:value,key:key,ambiguous:false};
      if (record.key !== key) record.ambiguous = true;
      if (nodeScopeMap) {
        if (nodeScopeMap.javaMap) nodeScopeMap.javaMap.put(node,record);
        else nodeScopeMap.jsMap.set(node,record);
        return true;
      }
      for (var i = 0; i < nodeScopeFallback.length; i++) {
        if (this._sameNode(nodeScopeFallback[i].node,node)) { nodeScopeFallback[i].record = record; return true; }
      }
      if (nodeScopeFallback.length >= 256) return false;
      nodeScopeFallback.push({node:node,record:record});
      return true;
    } catch (e) { nodeScopeStoreFailed = true; return false; }
  },

  _sameBounds: function (first, second) {
    if (!first || !second) return !first && !second;
    return first.left === second.left && first.top === second.top && first.right === second.right && first.bottom === second.bottom;
  },

  _liveScopeForElement: function (element, ctx, resolution) {
    if (!element || !ctx) return null;
    var isPoint = element.isCoordinate || element.isImage || element.isPress;
    if (isPoint && element.sourceNode && (!this._isOnScreen(element.sourceNode,ctx) || !this._sameBounds(element.observedNodeBounds,this._nodeBounds(element.sourceNode)))) return null;
    var strategy = isPoint ? element.scopeStrategy : (resolution ? resolution.strategy : null);
    try {
      if (!strategy && !isPoint) {
        var record = this._nodeScopeRecord(element);
        if (record && record.ambiguous) return null;
        strategy = record ? record.strategy : null;
      }
    } catch (e) { return null; }
    if (strategy) {
      var scope = this._strategyScope(strategy,ctx);
      if (!scope) return null;
      if (isPoint && strategy.anchor && !this._sameBounds(element.observedAnchorBounds,scope.anchorBounds)) return null;
      scope.strategy = strategy;
      return scope;
    }
    return {region:element.region || ctx.contentBounds,strategy:null};
  },

  _pointIsFresh: function (element, ctx) {
    return !!ctx && !!element.signature && element.signature === ctx.signature && typeof element.observedAt === "number" && Date.now()-element.observedAt <= 5000 && Date.now() >= element.observedAt;
  },

  _nodeBounds: function (element) {
    try { return geometry.rect(element.bounds()); } catch (e) { return null; }
  },

  _nodePoint: function (element) {
    var bounds = this._nodeBounds(element);
    if (!bounds) return null;
    return {x: Math.floor((bounds.left + bounds.right) / 2), y: Math.floor((bounds.top + bounds.bottom) / 2)};
  },

  _isOnScreen: function (element, ctx, region) {
    if (!element) return false;
    ctx = ctx || geometry.read();
    if (!ctx) return false;
    if (element.isPackage) return element.packageName === ctx.foregroundPackage;
    if (element.isImage || element.isCoordinate || element.isPress) {
      return (!element.signature || element.signature === ctx.signature) && geometry.isUsablePoint(element, ctx, region || element.region);
    }
    // AutoJS UiObject caches bounds; refresh() invalidates that cache. Reading
    // bounds twice without refreshing would miss movement of a retained node.
    try { if (typeof element.refresh === "function" && element.refresh() !== true) return false; } catch (refreshError) { return false; }
    try { if (typeof element.visibleToUser === "function" && !element.visibleToUser()) return false; } catch (e) { return false; }
    return geometry.isUsablePoint(this._nodePoint(element), ctx, region);
  },

  _anchorBounds: function (strategy, ctx) {
    if (!strategy.anchor) return null;
    var anchor = strategy.anchor;
    if (["text", "id", "desc", "className"].indexOf(anchor.type) < 0 || typeof anchor.value !== "string" || !anchor.value) return null;
    var all = this._findByCondition(anchor), selected = null;
    if (!all) return null;
    for (var i = 0; i < all.length; i++) {
      if (!this._isOnScreen(all[i], ctx)) continue;
      if (selected && !this._sameNode(selected,all[i])) return null;
      selected = all[i];
    }
    return selected ? this._nodeBounds(selected) : null;
  },

  _strategyScope: function (strategy, ctx) {
    if (!ctx || !ctx.canInteract) return null;
    var anchorBounds = this._anchorBounds(strategy, ctx);
    if (strategy.anchor && !anchorBounds) return null;
    var region = geometry.regionForStrategy(strategy, ctx, anchorBounds);
    return region ? {anchorBounds:anchorBounds,region:region} : null;
  },

  _targetForStrategy: function (element, strategy, ctx, region, anchorBounds) {
    if (!element || element.isPackage) return element;
    var pointType = element.isImage || element.isCoordinate || element.isPress;
    var hasOffset = !!strategy.offset || (strategy.type !== "coordinate" && (strategy.x_percent != null || strategy.y_percent != null));
    if (!pointType && !hasOffset && strategy.click_mode !== "press") return this._rememberNodeScope(element,strategy) ? element : null;
    var bounds = pointType ? (element.targetBounds || element.bounds || region) : this._nodeBounds(element);
    var point = pointType ? {x:element.x,y:element.y} : this._nodePoint(element);
    point = geometry.offsetPoint(point,strategy,bounds,ctx,element.isImage ? "image" : (pointType ? "coordinate" : "node"));
    if (!geometry.isUsablePoint(point,ctx,region)) return null;
    var result = {x:point.x,y:point.y,signature:ctx.signature,observedAt:ctx.observedAt,region:region,scopeStrategy:scopeStrategy(strategy),observedAnchorBounds:geometry.rect(anchorBounds)};
    if (!pointType) { result.sourceNode = element; result.observedNodeBounds = geometry.rect(bounds); }
    if (element.isImage) { result.isImage = true; result.bounds = element.bounds || element.targetBounds; result.targetBounds = result.bounds; }
    else result.isCoordinate = true;
    if (strategy.click_mode === "press") { result.isPress = true; result.duration = strategy.press_duration || 150; }
    return result;
  },

  _findElementResolution: function (actionName, timeout, quiet) {
    timeout = timeout == null ? 2000 : timeout;
    var selector = selectorLoader.get(actionName);
    if (!selector || !selector.strategies) { logger.error(TAG,"未找到选择器配置: " + actionName); return null; }
    var strategies = selector.strategies.slice().sort(function (a,b) { return a.priority - b.priority; });
    var startTime = Date.now();
    do {
      for (var i = 0; i < strategies.length; i++) {
        var resolution = {profile:selector.resolution_profile};
        var element = this._findByStrategy(strategies[i],selector.resolution_profile,resolution);
        if (element) { resolution.element = element; return resolution; }
      }
      if (Date.now() - startTime >= timeout) break;
      sleep(Math.min(300,Math.max(1,timeout-(Date.now()-startTime))));
    } while (Date.now() - startTime < timeout);
    if (!quiet) logger.warn(TAG,"未找到元素: " + actionName);
    return null;
  },

  findElement: function (actionName, timeout, quiet) {
    var resolution = this._findElementResolution(actionName,timeout,quiet);
    return resolution ? resolution.element : null;
  },

  clickAction: function (actionName, timeout, options) {
    var resolution = this._findElementResolution(actionName,timeout);
    if (!resolution) return false;
    var element = resolution.element;
    options = options || {};
    if (options.click_mode === "press" && !element.isPackage) {
      var ctx = geometry.read();
      var liveScope = this._liveScopeForElement(element,ctx,resolution);
      if (!liveScope || !this._isOnScreen(element,ctx,liveScope.region)) return false;
      var isPoint = element.isImage || element.isCoordinate || element.isPress;
      if (isPoint && !this._pointIsFresh(element,ctx)) return false;
      var point = isPoint ? element : this._nodePoint(element);
      if (!point) return false;
      element = {isPress:true,x:point.x,y:point.y,duration:options.press_duration || 150,signature:isPoint ? point.signature : ctx.signature,observedAt:isPoint ? point.observedAt : ctx.observedAt,region:liveScope.region,scopeStrategy:liveScope.strategy,observedAnchorBounds:isPoint ? point.observedAnchorBounds : geometry.rect(liveScope.anchorBounds),sourceNode:isPoint ? point.sourceNode : element,observedNodeBounds:isPoint ? point.observedNodeBounds : this._nodeBounds(element)};
    }
    return this._clickElementResolved(element,resolution);
  },

  /**
   * 显式等待元素出现（条件轮询，避免硬编码 sleep 赌页面加载）
   * 在超时时间内一旦元素显现立刻返回，超时未显现返回 null
   * @param {string} actionName - 选择器名称
   * @param {number} timeout - 超时时间（毫秒），默认 5000
   * @returns {Object|null} 找到的元素或 null
   */
  waitForElement: function (actionName, timeout) {
    timeout = timeout || 5000;
    var findTimeout = 1000;  // 单次 findElement 超时，短轮询保证总超时精度
    var startTime = Date.now();
    while (Date.now() - startTime < timeout) {
      var el = this.findElement(actionName, findTimeout, true);
      if (el) return el;
      sleep(300);  // 轮询间隔
    }
    logger.warn(TAG, "等待超时: " + actionName + " (" + timeout + "ms)");
    return null;
  },

  /**
   * 显式等待页面指纹匹配（条件轮询 isOnPage，避免硬编码 sleep 赌页面加载）
   * @param {string} pageKey - 页面指纹 key (如 "is_user_view", "is_comment_view")
   * @param {number} timeout - 超时时间（毫秒），默认 5000
   * @returns {boolean} 页面是否匹配
   */
  waitForPage: function (pageKey, timeout) {
    timeout = timeout || 5000;
    var startTime = Date.now();
    while (Date.now() - startTime < timeout) {
      if (this.isOnPage(pageKey)) return true;
      sleep(300);
    }
    logger.warn(TAG, "等待页面超时: " + pageKey + " (" + timeout + "ms)");
    return false;
  },

  /**
   * 按条件查找元素（支持 text/id/desc/className 类型 + match_mode）
   */
  _findByCondition: function (cond) {
    var matchMode = cond.match_mode || "exact";
    if (matchMode === "contains") {
      switch (cond.type) {
        case "text": return textContains(cond.value).find();
        case "desc": return descContains(cond.value).find();
        case "id": return idContains(cond.value).find();
        case "className": return classNameContains(cond.value).find();
        default: return null;
      }
    }
    switch (cond.type) {
      case "text": return text(cond.value).find();
      case "desc": return desc(cond.value).find();
      case "id": return id(cond.value).find();
      case "className": return className(cond.value).find();
      default: return null;
    }
  },

  /**
   * 检查单个元素是否匹配条件
   */
  _elementMatchesCondition: function (el, cond) {
    var matchMode = cond.match_mode || "exact";
    var actual;
    try {
      switch (cond.type) {
        case "text": actual = el.text(); break;
        case "desc": actual = el.desc(); break;
        case "id": actual = el.id(); break;
        case "className": actual = el.className(); break;
        default: return false;
      }
    } catch (e) { return false; }
    if (!actual) return false;
    if (matchMode === "contains") return actual.indexOf(cond.value) !== -1;
    return actual === cond.value;
  },

  /**
   * 多条件组合查找（AND/OR 逻辑）
   */
  _findByConditions: function (strategy) {
    var conditions = strategy.conditions;
    var logic = strategy.logic || "and";

    if (!conditions || conditions.length === 0) return null;

    // Single condition: short-circuit regardless of logic
    if (conditions.length === 1) {
      var single = this._findByCondition(conditions[0]);
      if (single) {
        for (var i = 0; i < single.length; i++) {
          if (this._isOnScreen(single[i])) return single[i];
        }
      }
      return null;
    }

    if (logic === "or") {
      // OR: return first on-screen element matching ANY condition (not just conditions[0])
      for (var j = 0; j < conditions.length; j++) {
        var condCandidates = this._findByCondition(conditions[j]);
        if (!condCandidates) continue;
        for (var k = 0; k < condCandidates.length; k++) {
          if (this._isOnScreen(condCandidates[k])) return condCandidates[k];
        }
      }
      return null;
    }

    // AND: all conditions must match the same element
    var candidates = this._findByCondition(conditions[0]);
    if (!candidates || candidates.length === 0) return null;

    for (var m = 0; m < candidates.length; m++) {
      var el = candidates[m];
      if (!this._isOnScreen(el)) continue;

      var allMatch = true;
      for (var n = 1; n < conditions.length; n++) {
        if (!this._elementMatchesCondition(el, conditions[n])) {
          allMatch = false;
          break;
        }
      }
      if (allMatch) return el;
    }
    return null;
  },

  /**
   * 按策略类型查找单个控件
   * @param {Object} strategy - { type, value, match_mode, conditions, logic, ... }
   * @returns {UiObject|null}
   */
  _findByStrategy: function (strategy, profile, resolution) {
    var ctx = geometry.read();
    var scope = this._strategyScope(strategy,ctx);
    if (!scope) return null;
    if (resolution) { resolution.strategy = scopeStrategy(strategy); resolution.anchorBounds = geometry.rect(scope.anchorBounds); }
    if (strategy.type === "package") return currentPackage() === strategy.value ? {isPackage:true,packageName:strategy.value} : null;
    if (strategy.type === "coordinate") {
      var screen = null;
      try {
        if (strategy.position && strategy.position.space === "capture_px") {
          screen = images.captureScreen();
          if (!screen) return null;
          var captureContext = geometry.read(screen);
          if (!captureContext || captureContext.signature !== ctx.signature) return null;
          ctx = captureContext;
        }
        var point = geometry.pointForStrategy(strategy,ctx,scope.anchorBounds);
        if (!geometry.isUsablePoint(point,ctx,scope.region)) return null;
        return this._targetForStrategy({isCoordinate:true,x:point.x,y:point.y},strategy,ctx,scope.region,scope.anchorBounds);
      } finally { if (screen) { try { screen.recycle(); } catch (e) {} } }
    }
    if (strategy.type === "image") {
      var image = this._findByImage(strategy.template,strategy.threshold === undefined ? 0.8 : strategy.threshold,strategy,ctx,scope.anchorBounds,profile);
      if (!image) return null;
      return this._targetForStrategy(image,strategy,ctx,scope.region,scope.anchorBounds);
    }
    var all = this._findManyByStrategy(strategy,ctx,scope);
    for (var i = 0; i < all.length; i++) {
      var target = this._targetForStrategy(all[i],strategy,ctx,scope.region,scope.anchorBounds);
      if (target) return target;
    }
    return null;
  },

  _findManyByStrategy: function (strategy, ctx, scope) {
    ctx = ctx || geometry.read();
    scope = scope || this._strategyScope(strategy,ctx);
    if (!scope) return [];
    var all;
    if (strategy.conditions && strategy.conditions.length) all = this._findManyByConditions(strategy);
    else if (strategy.type === "chain") all = this._findByChainAll(strategy.steps || []);
    else all = this._findByCondition(strategy);
    var visible = [];
    if (all) for (var i = 0; i < all.length; i++) if (this._isOnScreen(all[i],ctx,scope.region) && this._rememberNodeScope(all[i],strategy)) this._appendDistinctNode(visible,all[i]);
    return visible;
  },

  /**
   * 多条件组合查找多个控件（AND/OR）
   */
  _findManyByConditions: function (strategy) {
    var conditions = strategy.conditions;
    var logic = strategy.logic || "and";

    if (logic === "or") {
      var results = [];
      for (var j = 0; j < conditions.length; j++) {
        var candidates = this._findByCondition(conditions[j]);
        if (!candidates) continue;
        for (var k = 0; k < candidates.length; k++) {
          var el = candidates[k];
          this._appendDistinctNode(results,el);
        }
      }
      return results;
    }

    // AND: find all elements that match ALL conditions
    var candidates = this._findByCondition(conditions[0]);
    if (!candidates || candidates.length === 0) return [];

    var results = [];
    for (var m = 0; m < candidates.length; m++) {
      var el = candidates[m];
      var allMatch = true;
      for (var n = 1; n < conditions.length; n++) {
        if (!this._elementMatchesCondition(el, conditions[n])) {
          allMatch = false;
          break;
        }
      }
      if (allMatch) results.push(el);
    }
    return results;
  },

  _findByChainAll: function (steps) {
    if (!steps || !steps.length) return [];
    var selector = null, navStart = steps.length, i;
    for (i = 0; i < steps.length; i++) {
      if ((steps[i].nav || "filter") !== "filter") { navStart = i; break; }
      selector = selector ? this._chainSelector(selector,steps[i]) : this._makeSelector(steps[i]);
      if (!selector) return [];
    }
    var current = [], initial;
    try { initial = selector ? selector.find() : className("android.widget.FrameLayout").find(); } catch (e) { return []; }
    for (i = 0; initial && i < initial.length; i++) if (this._isOnScreen(initial[i])) current.push(initial[i]);
    for (var n = navStart; n < steps.length; n++) {
      var step = steps[n], nav = step.nav || "filter", next = [];
      for (var c = 0; c < current.length; c++) {
        var element = current[c], choices = [];
        try {
          if (nav === "filter") { if (this._elementMatchesStep(element,step)) choices = [element]; }
          else if (nav === "parent") { var parent = element.parent(); if (parent) choices = [parent]; }
          else if (nav === "child" || nav === "sibling") {
            var source = nav === "sibling" ? element.parent() : element;
            var childSelector = this._makeSelector(step);
            if (!source || !childSelector) continue;
            var children = source.find(childSelector), visible = [];
            for (var ch = 0; children && ch < children.length; ch++) {
              if (nav === "sibling" && children[ch] === element) continue;
              if (this._isOnScreen(children[ch])) visible.push(children[ch]);
            }
            choices = step.index == null ? visible : (visible[step.index] ? [visible[step.index]] : []);
          }
          for (var j = 0; j < choices.length; j++) {
            if (!this._isOnScreen(choices[j])) continue;
            this._appendDistinctNode(next,choices[j]);
          }
        } catch (navigationError) { /* stale nodes do not hide later candidates */ }
      }
      current = next;
      if (!current.length) break;
    }
    return current;
  },

  /**
   * 使用选择器查找多个控件（仅返回屏幕内的，避免 RecyclerView 离屏元素）
   * @param {string} actionName - 操作名称
   * @param {number} timeout - 超时时间（毫秒），默认 5000
   * @returns {Array} UiObject 数组，找不到返回空数组
   */
  findElements: function (actionName, timeout) {
    timeout = timeout || 5000;
    var selector = selectorLoader.get(actionName);
    if (!selector) {
      logger.error(TAG, "未找到选择器配置: " + actionName);
      return [];
    }

    var strategies = selector.strategies.slice().sort(function (a, b) {
      return a.priority - b.priority;
    });

    var self = this;
    var startTime = Date.now();
    while (Date.now() - startTime < timeout) {
      for (var i = 0; i < strategies.length; i++) {
        var s = strategies[i];
        var all = this._findManyByStrategy(s);
        if (all && all.length > 0) {
          // 只保留屏幕内的元素
          var visible = all.filter(function (el) { return self._isOnScreen(el); });
          if (visible.length > 0) {
            var label = s.conditions ? "conditions(" + (s.logic || "and") + ")" : (s.type || "unknown");
            logger.debug(TAG, "通过 " + label + " 找到 " + visible.length + "/" + all.length + " 个可见元素: '" + actionName + "'");
            return visible;
          }
        }
      }
      sleep(500);
    }

    logger.warn(TAG, "未找到元素列表: " + actionName);
    return [];
  },

  /**
   * 页面检测 — AND 逻辑，所有 strategies 必须同时命中才返回 true
   * 仅对 purpose="page_detect" 的选择器生效
   * @param {string} actionName
   * @param {number} timeout - 每个 strategy 的超时 ms，默认 300
   * @returns {boolean}
   */
  isOnPage: function (actionName, timeout) {
    timeout = timeout || 300;
    var config = selectorLoader.get(actionName);
    if (!config || config.purpose !== "page_detect") return false;
    var strategies = config.strategies;
    if (!strategies || strategies.length === 0) return false;
    var logic = config.strategy_logic || "and";
    var useOr = logic === "or";
    var startTime = Date.now();
    while (Date.now() - startTime < timeout) {
      if (useOr) {
        for (var i = 0; i < strategies.length; i++) {
          if (strategies[i].type !== "coordinate" && this._findByStrategy(strategies[i],config.resolution_profile)) return true;
        }
      } else {
        // AND — all strategies must match
        var allMatch = true;
        for (var j = 0; j < strategies.length; j++) {
          if (strategies[j].type === "coordinate" || !this._findByStrategy(strategies[j],config.resolution_profile)) { allMatch = false; break; }
        }
        if (allMatch) return true;
      }
      sleep(100);
    }
    return false;
  },

  /**
   * 检测当前页面 — 遍历所有 page_detect 选择器，按 priority 返回第一个匹配的 action_name
   * @returns {string|null} 页面名，无匹配返回 null
   */
  detectPage: function () {
    var all = selectorLoader._cache;
    var pages = [];
    for (var key in all) {
      if (all[key].purpose === "page_detect") {
        pages.push({ name: key, priority: all[key].priority || 99 });
      }
    }
    pages.sort(function (a, b) { return a.priority - b.priority; });
    for (var i = 0; i < pages.length; i++) {
      if (this.isOnPage(pages[i].name)) {
        return pages[i].name;
      }
    }
    return null;
  },

  /**
   * 通过模板图片在屏幕上查找
   * @param {string} templateFile - 模板文件名（存储在 /sdcard/dy_auto/templates/）
   * @param {number} threshold - 匹配阈值
   * @returns {Object|null} { isImage: true, x, y } 或 null
   */
  _findByImage: function (templateFile, threshold, strategy, ctx, anchorBounds, profile) {
    var config = {}, key;
    strategy = strategy || {};
    for (key in strategy) if (Object.prototype.hasOwnProperty.call(strategy,key)) config[key] = strategy[key];
    config.threshold = threshold === undefined ? 0.75 : threshold;
    return imageLocator.find(templateFile,config,ctx,anchorBounds,false,profile);
  },

  /**
   * 链式查找：按 steps 顺序构建 AutoJS 选择器链
   * 例如 steps: [{type:"className",value:"Button"},{type:"text",value:"视频"}]
   *   等价于 className("Button").text("视频").find()
   * @param {Array} steps
   * @returns {UiObject|null}
   */
  _findByChain: function (steps) {
    var all = this._findByChainAll(steps);
    return all.length ? all[0] : null;
  },

  _makeSelector: function (step) {
    var contains = step.match_mode === "contains";
    switch (step.type) {
      case "text":      return contains ? textContains(step.value) : text(step.value);
      case "id":        return contains ? idContains(step.value) : id(step.value);
      case "desc":      return contains ? descContains(step.value) : desc(step.value);
      case "className": return contains ? classNameContains(step.value) : className(step.value);
      case "textContains":      return textContains(step.value);
      case "descContains":      return descContains(step.value);
      case "idContains":        return idContains(step.value);
      case "classNameContains": return classNameContains(step.value);
      default: return null;
    }
  },

  _chainSelector: function (sel, step) {
    var contains = step.match_mode === "contains";
    switch (step.type) {
      case "text":      return contains ? sel.textContains(step.value) : sel.text(step.value);
      case "id":        return contains ? sel.idContains(step.value) : sel.id(step.value);
      case "desc":      return contains ? sel.descContains(step.value) : sel.desc(step.value);
      case "className": return contains ? sel.classNameContains(step.value) : sel.className(step.value);
      case "textContains":      return sel.textContains(step.value);
      case "descContains":      return sel.descContains(step.value);
      case "idContains":        return sel.idContains(step.value);
      case "classNameContains": return sel.classNameContains(step.value);
      default: return null;
    }
  },

  _elementMatchesStep: function (el, step) {
    var actual;
    try {
      switch (step.type) {
        case "text": case "textContains": actual = el.text(); break;
        case "desc": case "descContains": actual = el.desc(); break;
        case "id": case "idContains": actual = el.id(); break;
        case "className": case "classNameContains": actual = el.className(); break;
        default: return false;
      }
    } catch (e) { return false; }
    if (!actual) return false;
    var matchMode = step.match_mode || (/Contains$/.test(step.type) ? "contains" : "exact");
    if (matchMode === "contains") return actual.indexOf(step.value) !== -1;
    return actual === step.value;
  },

  /**
   * 点击元素（支持控件点击、坐标点击、图片匹配点击）
   * @param {UiObject} element
   * @returns {boolean}
   */
  clickElement: function (element) {
    return this._clickElementResolved(element,null);
  },

  _clickElementResolved: function (element, resolution) {
    if (!element || element.isPackage) return false;
    var ctx = geometry.read();
    var liveScope = this._liveScopeForElement(element,ctx,resolution);
    if (!liveScope || !this._isOnScreen(element,ctx,liveScope.region)) return false;
    var isPoint = element.isPress || element.isCoordinate || element.isImage;
    if (isPoint) {
      if (!this._pointIsFresh(element,ctx)) return false;
      try {
        if (element.isPress) return press(element.x,element.y,element.duration || 150) === true;
        return click(element.x,element.y) === true;
      } catch (e) { return false; }
    }
    try {
      if (element.clickable()) return element.click() === true;
      var point = this._nodePoint(element);
      var fresh = geometry.read(), freshScope = this._liveScopeForElement(element,fresh,resolution);
      if (!freshScope || !geometry.isUsablePoint(point,fresh,freshScope.region)) return false;
      return click(point.x,point.y) === true;
    } catch (e2) { return false; }
  },

  inputText: function (element, value) {
    if (!element || typeof value !== "string" || !value || !this.clickElement(element)) return false;
    sleep(500);
    var pointType = element.isImage || element.isCoordinate || element.isPress;
    var fresh = geometry.read(), freshScope = this._liveScopeForElement(element,fresh);
    if (!freshScope || !this._isOnScreen(element,fresh,freshScope.region)) return false;
    try {
      if (!pointType && this._isOnScreen(element) && element.setText(value) === true) return true;
    } catch (e) {}
    try {
      var candidates = className("EditText").find();
      for (var i = 0; candidates && i < candidates.length; i++) {
        var input = candidates[i];
        if (!this._isOnScreen(input)) continue;
        if (typeof input.focused === "function" && !input.focused()) continue;
        if (input.setText(value) === true) return true;
      }
    } catch (e2) {}
    try {
      if (!geometry.read().canInteract) return false;
      setClip(value);
      var result = shell("input keyevent 279",false);
      return !!result && Number(result.code) === 0;
    } catch (e3) { return false; }
  },

  /**
   * 通过键盘回车提交（多种方式尝试，回退点击提交按钮）
   * @param {string} submitActionName - 提交按钮的动作名（回退方案）
   * @returns {boolean}
   */
  submitViaKeyboard: function (submitActionName) {
    // 尝试键盘回车
    try { var dispatched = shell("input keyevent 66", false); if (dispatched && Number(dispatched.code) === 0) { sleep(300); return true; } } catch (e1) { /* ignore */ }

    // 回退: 点击提交按钮
    if (submitActionName) {
      try {
        var selectorLoader = require("./selector-loader");
        var selector = selectorLoader.get(submitActionName);
        if (selector) {
          var btn = this.findElement(submitActionName, 2000);
          if (btn && this.clickElement(btn)) { sleep(500); return true; }
        }
      } catch (e3) { /* ignore */ }
    }

    logger.warn(TAG, "回车提交和按钮提交均失败");
    return false;
  },

  /**
   * 执行上滑操作（浏览下一条视频）
   * @returns {boolean}
   */
  swipeUp: function () {
    var startX = device.width * (0.35 + Math.random() * 0.2);         // 35%-55% 屏宽
    var startY = device.height * (0.6 + Math.random() * 0.1);         // 60%-70% 屏高
    var endX = startX + Math.floor(Math.random() * 30 + 20);           // 微微右上 +20~50px
    var endY = device.height * (0.35 + Math.random() * 0.1);          // 35%-45% 屏高
    var duration = Math.floor(Math.random() * 200 + 300);              // 300-500ms
    gestures([0, duration, [startX, startY], [endX, endY]]);
  },

  /**
   * 通过模板图片在屏幕上查找并点击（以图找图）
   * 用于无障碍服务无法定位的自定义控件（如弹出框）
   * @param {string} templatePath - 模板图片路径
   * @param {Object} options - { threshold, region }
   * @returns {boolean} 是否找到并点击
   */
  findImageClick: function (templatePath, options) {
    options = options || {};
    var strategy = {}, key;
    for (key in options) if (Object.prototype.hasOwnProperty.call(options,key)) strategy[key] = options[key];
    if (Object.prototype.toString.call(options.region) === "[object Array]") { strategy.captureRegion = options.region; delete strategy.region; }
    var ctx = geometry.read(), scope = this._strategyScope(strategy,ctx);
    if (!scope) return false;
    var element = imageLocator.find(templatePath,strategy,ctx,scope.anchorBounds,true);
    element = this._targetForStrategy(element,strategy,ctx,scope.region,scope.anchorBounds);
    return this.clickElement(element);
  },

  /**
   * 从控件提取值（按选择器配置的 extract_field 读取属性）
   * @param {UiObject} element - 已找到的控件
   * @param {Object} selector - 选择器配置 (含 purpose, extract_field, clean_mode, clean_pattern, clean_prompt)
   * @returns {string|null} 提取并清洗后的值
   */
  extractValue: function (element, selector) {
    if (!element || !selector || selector.purpose !== "extract") return null;

    var field = selector.extract_field || "text";
    var rawValue = null;
    try {
      switch (field) {
        case "text": rawValue = element.text(); break;
        case "desc": rawValue = element.desc(); break;
        case "id": rawValue = element.id(); break;
        case "className": rawValue = element.className(); break;
        default: return null;
      }
    } catch (e) {
      logger.warn(TAG, "提取值失败: " + e.message);
      return null;
    }

    if (!rawValue) return "";

    var cleanMode = selector.clean_mode || "raw";
    if (cleanMode === "raw") return rawValue;

    // 正则清洗
    if (cleanMode === "regex" && selector.clean_pattern) {
      try {
        var re = new RegExp(selector.clean_pattern);
        var match = rawValue.match(re);
        return match ? (match[1] || match[0]) : rawValue;
      } catch (e) {
        logger.warn(TAG, "正则清洗失败: " + e.message);
        return rawValue;
      }
    }

    // AI 清洗
    if (cleanMode === "ai" && selector.clean_prompt) {
      try {
        var promptText = selector.clean_prompt + "\n\n原始数据：" + rawValue;
        var result = apiClient.post("/api/device/ai-proxy", {
          prompt: promptText,
          max_tokens: 128,
          temperature: 0.2,
        });
        if (result && result.content) {
          logger.debug(TAG, "AI 清洗: '" + rawValue.substring(0, 20) + "' -> '" + result.content.substring(0, 20) + "'");
          return result.content.trim();
        }
      } catch (e) {
        logger.warn(TAG, "AI 清洗失败: " + e.message);
      }
      return rawValue;
    }

    return rawValue;
  },

  /**
   * 截取当前页面控件树快照（用于选择器调试）

   * @returns {Object} 控件树摘要
   */
  captureUISnapshot: function () {
    var snapshot = { elements: [] };
    try {
      var allElements = className("android.widget.TextView").find();
      for (var i = 0; i < Math.min(allElements.length, 50); i++) {
        var el = allElements[i];
        snapshot.elements.push({
          text: el.text() || "",
          id: el.id() || "",
          desc: el.desc() || "",
          className: el.className() || "",
          bounds: el.bounds() ? {
            left: el.bounds().left,
            top: el.bounds().top,
            right: el.bounds().right,
            bottom: el.bounds().bottom,
          } : null,
        });
      }
    } catch (e) {
      logger.warn(TAG, "截取界面快照失败: " + e.message);
    }
    return snapshot;
  },
};

module.exports = uiOperator;
