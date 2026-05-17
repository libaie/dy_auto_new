var selectorLoader = require("./selector-loader");
var apiClient = require("./api-client");
var logger = require("../utils/logger");

var TAG = "界面操作";

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
  _isOnScreen: function (el) {
    if (!el) return false;
    // 坐标类型（图片匹配、坐标策略）视为在屏幕内
    if (el.isImage || el.isCoordinate || el.isPackage) return true;
    try {
      var b = el.bounds();
      if (!b) return false;
      var cx = b.centerX();
      var cy = b.centerY();
      return cx >= 0 && cy >= 0 && cx < device.width && cy < device.height;
    } catch (e) { return false; }
  },

  /**
   * 使用选择器查找控件（仅返回屏幕内的元素，避免 RecyclerView 复用导致的离屏匹配）
   * @param {string} actionName - 操作名称
   * @param {number} timeout - 超时时间（毫秒），默认 5000
   * @returns {UiObject|null} 找到的控件，或 null
   */
  findElement: function (actionName, timeout) {
    timeout = timeout || 2000;
    var selector = selectorLoader.get(actionName);
    if (!selector) {
      logger.error(TAG, "未找到选择器配置: " + actionName);
      return null;
    }

    var strategies = selector.strategies.slice().sort(function (a, b) {
      return a.priority - b.priority;
    });

    var startTime = Date.now();
    while (Date.now() - startTime < timeout) {
      for (var i = 0; i < strategies.length; i++) {
        var s = strategies[i];
        var element = this._findByStrategy(s);
        if (element && this._isOnScreen(element)) {
          // press 模式：找到元素后用真实触摸按压代替点击
          if (s.click_mode === "press") {
            if (element.isImage || element.isCoordinate) {
              if (s.x_percent != null) element.x += s.x_percent;
              if (s.y_percent != null) element.y += s.y_percent;
              return { isPress: true, x: element.x, y: element.y, duration: s.press_duration || 150 };
            }
            if (!element.isPackage) {
              var pb = element.bounds();
              if (pb) {
                var pcx = pb.centerX();
                var pcy = pb.centerY();
                if (s.x_percent != null) pcx += Math.round((pb.right - pb.left) * s.x_percent / 100);
                if (s.y_percent != null) pcy += Math.round((pb.bottom - pb.top) * s.y_percent / 100);
                logger.debug(TAG, "通过 " + s.type + " +press 找到: '" + actionName + "'");
                return { isPress: true, x: pcx, y: pcy, duration: s.press_duration || 150 };
              }
            }
          }

          // 偏移处理：image 用像素偏移，coordinate 已在 _findByStrategy 处理跳过，控件按比例
          if (s.x_percent != null || s.y_percent != null) {
            if (element.isImage) {
              if (s.x_percent != null) element.x += s.x_percent;
              if (s.y_percent != null) element.y += s.y_percent;
              logger.debug(TAG, "通过 " + s.type + " +偏移 找到: '" + actionName + "'");
              return element;
            }
            if (!element.isCoordinate && !element.isPackage) {
              var b = element.bounds();
              if (b) {
                var cx = b.centerX();
                var cy = b.centerY();
                var elW = b.right - b.left;
                var elH = b.bottom - b.top;
                if (s.x_percent != null) cx += Math.round(elW * s.x_percent / 100);
                if (s.y_percent != null) cy += Math.round(elH * s.y_percent / 100);
                logger.debug(TAG, "通过 " + s.type + " +偏移 找到: '" + actionName + "'");
                return { isCoordinate: true, x: cx, y: cy };
              }
            }
          }
          logger.debug(TAG, "通过 " + s.type + " 找到元素: '" + actionName + "'");
          return element;
        }
      }
      sleep(700);
    }

    logger.warn(TAG, "未找到元素: " + actionName);
    return null;
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
  _findByStrategy: function (strategy) {
    // Multi-condition mode
    if (strategy.conditions && strategy.conditions.length > 0) {
      return this._findByConditions(strategy);
    }

    var all, j;
    // Non-text types: match_mode is meaningless, handle directly
    switch (strategy.type) {
      case "package":
        if (currentPackage() === strategy.value) {
          return { isPackage: true, packageName: strategy.value };
        }
        return null;
      case "coordinate":
        var x = Math.round(strategy.x_percent * device.width);
        var y = Math.round(strategy.y_percent * device.height);
        return { isCoordinate: true, x: x, y: y };
      case "image":
        return this._findByImage(strategy.template, strategy.threshold || 0.8);
      case "chain":
        return this._findByChain(strategy.steps || []);
    }
    // Text-based types: use match_mode
    var matchMode = strategy.match_mode || "exact";
    if (matchMode === "contains") {
      switch (strategy.type) {
        case "text": all = textContains(strategy.value).find(); break;
        case "id": all = idContains(strategy.value).find(); break;
        case "desc": all = descContains(strategy.value).find(); break;
        case "className": all = classNameContains(strategy.value).find(); break;
        default: return null;
      }
    } else {
      switch (strategy.type) {
        case "text": all = text(strategy.value).find(); break;
        case "id": all = id(strategy.value).find(); break;
        case "desc": all = desc(strategy.value).find(); break;
        case "className": all = className(strategy.value).find(); break;
        default: return null;
      }
    }
    if (all && all.length > 0) {
      for (j = 0; j < all.length; j++) {
        if (this._isOnScreen(all[j])) return all[j];
      }
    }
    return null;
  },

  /**
   * 按策略类型查找多个控件（返回数组）
   * @param {Object} strategy - { type, value }
   * @returns {Array} UiObject 数组
   */
  _findManyByStrategy: function (strategy) {
    // Multi-condition mode
    if (strategy.conditions && strategy.conditions.length > 0) {
      return this._findManyByConditions(strategy);
    }

    // Non-text types: match_mode is meaningless, handle directly
    if (strategy.type === "chain") {
      return this._findByChainAll(strategy.steps || []);
    }

    // Text-based types: use match_mode
    var matchMode = strategy.match_mode || "exact";
    if (matchMode === "contains") {
      switch (strategy.type) {
        case "text": return textContains(strategy.value).find();
        case "id": return idContains(strategy.value).find();
        case "desc": return descContains(strategy.value).find();
        case "className": return classNameContains(strategy.value).find();
        default: return [];
      }
    }
    switch (strategy.type) {
      case "text": return text(strategy.value).find();
      case "id": return id(strategy.value).find();
      case "desc": return desc(strategy.value).find();
      case "className": return className(strategy.value).find();
      default: return [];
    }
  },

  /**
   * 多条件组合查找多个控件（AND/OR）
   */
  _findManyByConditions: function (strategy) {
    var conditions = strategy.conditions;
    var logic = strategy.logic || "and";

    if (logic === "or") {
      var results = [];
      var seen = {};
      for (var j = 0; j < conditions.length; j++) {
        var candidates = this._findByCondition(conditions[j]);
        if (!candidates) continue;
        for (var k = 0; k < candidates.length; k++) {
          var el = candidates[k];
          var key = this._elKey(el);
          if (!seen[key]) {
            seen[key] = true;
            results.push(el);
          }
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

  /** 生成元素去重 key（bounds 中心 + className） */
  _elKey: function (el) {
    try {
      var b = el.bounds();
      return (el.className() || "") + "@" + (b ? (b.centerX() + "," + b.centerY()) : "?");
    } catch (e) { return String(Math.random()); }
  },

  _findByChainAll: function (steps) {
    if (!steps || steps.length === 0) return [];
    // Build selector chain from filter steps (same as _findByChain)
    var sel = null;
    for (var i = 0; i < steps.length; i++) {
      var nav = steps[i].nav || "filter";
      if (nav !== "filter") break;  // only filter steps can build selectors
      if (!sel) { sel = this._makeSelector(steps[i]); }
      else { sel = this._chainSelector(sel, steps[i]); }
      if (!sel) return [];
    }
    return sel ? sel.find() : [];
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
          if (this._findByStrategy(strategies[i])) return true;
        }
      } else {
        // AND — all strategies must match
        var allMatch = true;
        for (var j = 0; j < strategies.length; j++) {
          if (!this._findByStrategy(strategies[j])) { allMatch = false; break; }
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
  _findByImage: function (templateFile, threshold) {
    var res = device.width + "x" + device.height;
    threshold = threshold || 0.8;

    // Try resolution-specific template first, then "default" fallback
    var candidates = [
      "/sdcard/dy_auto/templates/" + res + "/" + templateFile,
      "/sdcard/dy_auto/templates/default/" + templateFile,
    ];

    var screen = images.captureScreen();
    if (!screen) return null;

    for (var ci = 0; ci < candidates.length; ci++) {
      var tpl = images.read(candidates[ci]);
      if (!tpl) continue;

      // If template is from a different resolution, scale before matching
      // Template filename format: name@1080x2400.png — extract original res
      var scaleMatch = templateFile.match(/@(\d+x\d+)/);
      if (scaleMatch) {
        var origRes = scaleMatch[1];
        if (origRes !== res) {
          var origParts = origRes.split("x");
          var origW = parseInt(origParts[0]) || 1;
          var scaleX = device.width / origW;
          // Scale within reasonable bounds
          if (Math.abs(1 - scaleX) > 0.05) {
            var newW = Math.round(tpl.getWidth() * scaleX);
            var newH = Math.round(tpl.getHeight() * scaleX);
            try {
              var scaled = images.scale(tpl, newW, newH);
              if (scaled) { tpl.recycle(); tpl = scaled; }
            } catch (e) {
              logger.warn(TAG, "模板缩放失败: " + e.message);
            }
          }
        }
      }

      var p = images.findImage(screen, tpl, { threshold: threshold });
      if (p) {
        var cx = Math.round(p.x + tpl.getWidth() / 2);
        var cy = Math.round(p.y + tpl.getHeight() / 2);
        tpl.recycle();
        screen.recycle();
        logger.debug(TAG, "图片匹配: (" + p.x + "," + p.y + ") 中心: (" + cx + "," + cy + ")");
        return { isImage: true, x: cx, y: cy };
      }

      tpl.recycle();
    }

    screen.recycle();
    return null;
  },

  /**
   * 链式查找：按 steps 顺序构建 AutoJS 选择器链
   * 例如 steps: [{type:"className",value:"Button"},{type:"text",value:"视频"}]
   *   等价于 className("Button").text("视频").find()
   * @param {Array} steps
   * @returns {UiObject|null}
   */
  _findByChain: function (steps) {
    if (!steps || steps.length === 0) return null;

    // Phase 1: build selector chain for initial filter steps (nav="filter" or default)
    var sel = null;
    var navStartIdx = steps.length;  // index of first nav step
    for (var i = 0; i < steps.length; i++) {
      var nav = steps[i].nav || "filter";
      if (nav !== "filter") { navStartIdx = i; break; }
      var step = steps[i];
      if (!sel) {
        sel = this._makeSelector(step);
        if (!sel) { logger.debug(TAG, "链式 Phase1: _makeSelector 返回 null, step=" + JSON.stringify(step)); return null; }
      } else {
        sel = this._chainSelector(sel, step);
        if (!sel) { logger.debug(TAG, "链式 Phase1: _chainSelector 返回 null"); return null; }
      }
    }

    // If all steps are filter, just find from selector
    if (navStartIdx >= steps.length) {
      if (!sel) return null;
      var all = sel.find();
      if (all && all.length > 0) {
        for (var j = 0; j < all.length; j++) {
          if (this._isOnScreen(all[j])) return all[j];
        }
      }
      return null;
    }

    // Phase 2: find first matching element from filter chain, then navigate
    var el = null;
    if (sel) {
      var candidates = sel.find();
      logger.debug(TAG, "链式 Phase2: 候选=" + (candidates ? candidates.length : 0) + " 个");
      if (candidates && candidates.length > 0) {
        for (var k = 0; k < candidates.length; k++) {
          if (this._isOnScreen(candidates[k])) { el = candidates[k]; break; }
        }
      }
    } else {
      // First step is a nav step with no prior filter: start from root
      try { el = className("android.widget.FrameLayout").findOne(1000); } catch (e) {}
    }
    if (!el) { logger.debug(TAG, "链式 Phase2: 未找到可见元素 (sel=" + (sel ? "ok" : "null") + ")"); return null; }

    // Phase 3: walk the tree
    for (var m = navStartIdx; m < steps.length; m++) {
      var navStep = steps[m];
      var navAction = navStep.nav || "filter";
      if (navAction === "parent") {
        try { el = el.parent(); } catch (e) { logger.debug(TAG, "链式 Phase3: parent() 异常"); return null; }
        if (!el) { logger.debug(TAG, "链式 Phase3: parent() 返回 null"); return null; }
      } else if (navAction === "child") {
        var childSel = this._makeSelector(navStep);
        if (!childSel) return null;
        try {
          var children = el.find(childSel);
          if (!children || children.length === 0) return null;
          var idx = navStep.index || 0;
          el = null;
          var found = 0;
          for (var c = 0; c < children.length; c++) {
            if (this._isOnScreen(children[c])) {
              if (found === idx) { el = children[c]; break; }
              found++;
            }
          }
          if (!el) return null;
        } catch (e) { return null; }
      } else if (navAction === "sibling") {
        // Go to parent, then find a different child matching the step
        try {
          var parentEl = el.parent();
          if (!parentEl) return null;
          var siblingSel = this._makeSelector(navStep);
          if (!siblingSel) return null;
          var siblings = parentEl.find(siblingSel);
          el = null;
          if (siblings && siblings.length > 0) {
            var sibIdx = navStep.index || 0;
            var sibFound = 0;
            for (var s = 0; s < siblings.length; s++) {
              if (this._isOnScreen(siblings[s])) {
                if (sibFound === sibIdx) { el = siblings[s]; break; }
                sibFound++;
              }
            }
          }
          if (!el) return null;
        } catch (e) { return null; }
      } else if (navAction === "filter") {
        // filter at current element level: check if this element matches
        if (!this._elementMatchesStep(el, navStep)) return null;
      }
    }

    var result = this._isOnScreen(el) ? el : null;
    logger.debug(TAG, "链式 完成: _isOnScreen=" + (result ? "true" : "false"));
    return result;
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
    var matchMode = step.match_mode || "exact";
    if (matchMode === "contains") return actual.indexOf(step.value) !== -1;
    return actual === step.value;
  },

  /**
   * 点击元素（支持控件点击、坐标点击、图片匹配点击）
   * @param {UiObject} element
   * @returns {boolean}
   */
  clickElement: function (element) {
    if (!element) return false;

    // 按压触摸（press 模式）
    if (element.isPress) {
      logger.debug(TAG, "按压: (" + element.x + ", " + element.y + "), " + (element.duration || 150) + "ms");
      return press(element.x, element.y, element.duration || 150);
    }

    // 坐标点击
    if (element.isCoordinate) {
      logger.debug(TAG, "点击坐标: (" + element.x + ", " + element.y + ")");
      return click(element.x, element.y);
    }

    // 图片匹配点击
    if (element.isImage) {
      logger.debug(TAG, "点击图片匹配: (" + element.x + ", " + element.y + ")");
      return click(element.x, element.y);
    }

    // package 类型 — 仅验证包名，无需点击
    if (element.isPackage) {
      logger.debug(TAG, "package 验证通过: " + element.packageName);
      return true;
    }

    // 控件点击
    if (element.clickable()) {
      return element.click();
    }
    // 控件不可点击，坐标点击
    try {
      var bounds = element.bounds();
      if (bounds) {
        var cx = bounds.centerX();
        var cy = bounds.centerY();
        if (cx >= 0 && cy >= 0 && cx < device.width && cy < device.height) {
          return click(cx, cy);
        }
      }
    } catch (e) {}
    return false;
  },

  /**
   * 输入文本
   * @param {UiObject} element - 输入框控件
   * @param {string} text - 要输入的文本
   * @returns {boolean}
   */
  inputText: function (element, text) {
    if (!element || !text) return false;

    // 点击输入框获取焦点
    if (element.isImage || element.isCoordinate) {
      var x = element.x || Math.round(element.x_percent * device.width);
      var y = element.y || Math.round(element.y_percent * device.height);
      click(x, y);
    } else {
      try { element.click(); } catch (e) { /* ignore */ }
    }
    sleep(500);

    // 优先 setText（最可靠）
    try {
      if (!element.isImage && !element.isCoordinate) {
        element.setText(text);
        logger.debug(TAG, "setText: '" + text.substring(0, 20) + "'");
        return true;
      }
    } catch (e1) { /* ignore */ }

    // 找 EditText 控件 setText
    try {
      var editText = className("EditText").findOne(2000);
      if (editText) {
        editText.setText(text);
        logger.debug(TAG, "EditText.setText: '" + text.substring(0, 20) + "'");
        return true;
      }
    } catch (e2) { /* ignore */ }

    // 最后兜底: 剪贴板粘贴
    try {
      setClip(text);
      sleep(200);
      try { shell("input keyevent 279", false); } catch (e3) { /* ignore */ }
      sleep(200);
      logger.debug(TAG, "剪贴板粘贴: '" + text.substring(0, 20) + "'");
      return true;
    } catch (e5) {
      logger.warn(TAG, "所有输入方式均失败");
    }
    return false;
  },

  /**
   * 通过键盘回车提交（多种方式尝试，回退点击提交按钮）
   * @param {string} submitActionName - 提交按钮的动作名（回退方案）
   * @returns {boolean}
   */
  submitViaKeyboard: function (submitActionName) {
    // 尝试键盘回车
    try { shell("input keyevent 66", false); sleep(300); return true; } catch (e1) { /* ignore */ }

    // 回退: 点击提交按钮
    if (submitActionName) {
      try {
        var selectorLoader = require("./selector-loader");
        var selector = selectorLoader.get(submitActionName);
        if (selector) {
          var btn = this.findElement(submitActionName, 2000);
          if (btn) { this.clickElement(btn); sleep(500); return true; }
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
    var threshold = options.threshold || 0.8;

    var tpl = images.read(templatePath);
    if (!tpl) {
      logger.error(TAG, "模板图片未找到: " + templatePath);
      return false;
    }

    var screen = images.captureScreen();
    if (!screen) {
      tpl.recycle();
      logger.error(TAG, "截屏失败");
      return false;
    }

    var findOptions = { threshold: threshold };
    if (options.region) {
      findOptions.region = options.region;
    }

    var p = images.findImage(screen, tpl, findOptions);

    if (p) {
      var cx = p.x + tpl.getWidth() / 2;
      var cy = p.y + tpl.getHeight() / 2;
      logger.info(TAG, "图片匹配: (" + p.x + "," + p.y + ") 点击: (" + cx + "," + cy + ")");
      click(cx, cy);
      tpl.recycle();
      screen.recycle();
      return true;
    }

    logger.warn(TAG, "图片未匹配: " + templatePath);
    tpl.recycle();
    screen.recycle();
    return false;
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
