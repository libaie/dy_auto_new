var selectorLoader = require("./selector-loader");
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
    logger.info(TAG, "正在关闭抖音...");
    app.stop("com.ss.android.ugc.aweme");
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
   * 使用选择器查找控件
   * 按策略优先级依次尝试：text -> id -> desc -> coordinate
   * @param {string} actionName - 操作名称
   * @param {number} timeout - 超时时间（毫秒），默认 5000
   * @returns {UiObject|null} 找到的控件，或 null
   */
  findElement: function (actionName, timeout) {
    timeout = timeout || 5000;
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
        if (element) {
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
   * 按策略类型查找单个控件
   * @param {Object} strategy - { type, value, x_percent, y_percent, template, threshold }
   * @returns {UiObject|null}
   */
  _findByStrategy: function (strategy) {
    switch (strategy.type) {
      case "text":
        return text(strategy.value).findOnce();
      case "id":
        return id(strategy.value).findOnce();
      case "desc":
        return desc(strategy.value).findOnce();
      case "className":
        return className(strategy.value).findOnce();
      case "package":
        if (currentPackage() === strategy.value) {
          return { isPackage: true, packageName: strategy.value };
        }
        return null;
      case "coordinate":
        // 坐标点击不返回控件对象，返回一个模拟对象
        var x = Math.round(strategy.x_percent * device.width);
        var y = Math.round(strategy.y_percent * device.height);
        return { isCoordinate: true, x: x, y: y };
      case "image":
        // 以图找图，返回模拟对象包含点击坐标
        return this._findByImage(strategy.template, strategy.threshold || 0.8);
      default:
        return null;
    }
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
   * 使用选择器查找多个控件（返回数组）
   * 按策略优先级依次尝试，返回第一个非空结果
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

    var startTime = Date.now();
    while (Date.now() - startTime < timeout) {
      for (var i = 0; i < strategies.length; i++) {
        var s = strategies[i];
        var results = this._findManyByStrategy(s);
        if (results && results.length > 0) {
          logger.debug(TAG, "通过 " + s.type + " 找到 " + results.length + " 个元素: '" + actionName + "'");
          return results;
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
    } else {
      // 控件不可点击，尝试坐标点击
      var bounds = element.bounds();
      if (bounds) {
        var cx = bounds.centerX();
        var cy = bounds.centerY();
        // 坐标必须在屏幕内
        if (cx < 0 || cy < 0 || cx >= device.width || cy >= device.height) {
          logger.warn(TAG, "坐标 (" + cx + "," + cy + ") 在屏幕外，跳过点击");
          return false;
        }
        return click(cx, cy);
      }
    }
    return false;
  },

  /**
   * 输入文本
   * @param {UiObject} element - 输入框控件
   * @param {string} text - 要输入的文本
   * @returns {boolean}
   */
  inputText: function (element, text) {
    if (!element) return false;
    element.setText(text);
    return true;
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
