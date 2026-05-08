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

    // 如果已在前台，直接返回
    if (currentPackage() === TARGET_PKG) {
      logger.info(TAG, "抖音已在前台");
      return true;
    }

    app.launchApp("抖音");

    // 最多重试 3 次，每次等待 3 秒
    for (var i = 0; i < 3; i++) {
      sleep(3000);
      var pkg = currentPackage();
      if (pkg === TARGET_PKG) {
        logger.info(TAG, "抖音打开成功");
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
          // UiObject 是 Java 对象不能挂 JS 属性，偏移直接算坐标返回
          if ((s.x_percent != null || s.y_percent != null) && !element.isCoordinate && !element.isImage && !element.isPackage) {
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
          logger.debug(TAG, "通过 " + s.type + " 找到元素: '" + actionName + "'");
          return element;
        }
      }
      sleep(500);
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
        default:
          return null;
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
    switch (strategy.type) {
      case "text": return text(strategy.value).find();
      case "id": return id(strategy.value).find();
      case "desc": return desc(strategy.value).find();
      case "className": return className(strategy.value).find();
      default: return [];
    }
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
            logger.debug(TAG, "通过 " + s.type + " 找到 " + visible.length + "/" + all.length + " 个可见元素: '" + actionName + "'");
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
   * 通过模板图片在屏幕上查找
   * @param {string} templateFile - 模板文件名（存储在 /sdcard/dy_auto/templates/）
   * @param {number} threshold - 匹配阈值
   * @returns {Object|null} { isImage: true, x, y } 或 null
   */
  _findByImage: function (templateFile, threshold) {
    var templatePath = "/sdcard/dy_auto/templates/" + templateFile;
    var tpl = images.read(templatePath);
    if (!tpl) {
      logger.warn(TAG, "模板图片未找到: " + templatePath);
      return null;
    }

    var screen = images.captureScreen();
    if (!screen) {
      tpl.recycle();
      return null;
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
        if (!sel) return null;
      } else {
        sel = this._chainSelector(sel, step);
        if (!sel) return null;
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
      if (candidates && candidates.length > 0) {
        for (var k = 0; k < candidates.length; k++) {
          if (this._isOnScreen(candidates[k])) { el = candidates[k]; break; }
        }
      }
    } else {
      // First step is a nav step with no prior filter: start from root
      try { el = className("android.widget.FrameLayout").findOne(1000); } catch (e) {}
    }
    if (!el) return null;

    // Phase 3: walk the tree
    for (var m = navStartIdx; m < steps.length; m++) {
      var navStep = steps[m];
      var navAction = navStep.nav || "filter";
      if (navAction === "parent") {
        try { el = el.parent(); } catch (e) { return null; }
        if (!el) return null;
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

    return this._isOnScreen(el) ? el : null;
  },

  _makeSelector: function (step) {
    switch (step.type) {
      case "text":      return text(step.value);
      case "id":        return id(step.value);
      case "desc":      return desc(step.value);
      case "className": return className(step.value);
      case "textContains":      return textContains(step.value);
      case "descContains":      return descContains(step.value);
      case "idContains":        return idContains(step.value);
      case "classNameContains": return classNameContains(step.value);
      default: return null;
    }
  },

  _chainSelector: function (sel, step) {
    switch (step.type) {
      case "text":      return sel.text(step.value);
      case "id":        return sel.id(step.value);
      case "desc":      return sel.desc(step.value);
      case "className": return sel.className(step.value);
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
        case "text": actual = el.text(); break;
        case "desc": actual = el.desc(); break;
        case "id": actual = el.id(); break;
        case "className": actual = el.className(); break;
        default: return false;
      }
    } catch (e) { return false; }
    return actual && actual.indexOf(step.value) !== -1;
  },

  /**
   * 点击元素（支持控件点击、坐标点击、图片匹配点击）
   * @param {UiObject} element
   * @returns {boolean}
   */
  clickElement: function (element) {
    if (!element) return false;

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
      try { shell("input keyevent 279", true); } catch (e3) { /* ignore */ }
      try { keyCode(279); } catch (e4) { /* ignore */ }
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
    try { shell("input keyevent 66", true); sleep(300); return true; } catch (e1) { /* ignore */ }
    try { keyCode(66); sleep(300); return true; } catch (e2) { /* ignore */ }

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
    var startX = device.width / 2 + Math.floor(Math.random() * 50 - 25);
    var startY = device.height * 0.7;
    var endX = device.width / 2 + Math.floor(Math.random() * 50 - 25);
    var endY = device.height * 0.3;
    return swipe(startX, startY, endX, endY, Math.floor(Math.random() * 200 + 300));
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
