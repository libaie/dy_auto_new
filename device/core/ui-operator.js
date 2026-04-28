var selectorLoader = require("./selector-loader");
var logger = require("../utils/logger");

var TAG = "UI";

var uiOperator = {
  /**
   * 启动抖音
   * @returns {boolean}
   */
  openApp: function () {
    logger.info(TAG, "Opening Douyin...");
    app.launchApp("抖音");
    sleep(3000); // 等待 App 启动
    if (currentPackage() === "com.ss.android.ugc.aweme") {
      logger.info(TAG, "Douyin opened successfully");
      return true;
    }
    logger.error(TAG, "Failed to open Douyin");
    return false;
  },

  /**
   * 关闭抖音
   */
  closeApp: function () {
    logger.info(TAG, "Closing Douyin...");
    app.stop("com.ss.android.ugc.aweme");
    sleep(1000);
  },

  /**
   * 检查抖音是否在前台
   * @returns {boolean}
   */
  isAppActive: function () {
    return currentPackage() === "com.ss.android.ugc.aweme";
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
      logger.error(TAG, "No selector config for action: " + actionName);
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
          logger.debug(TAG, "Found element for '" + actionName + "' via " + s.type);
          return element;
        }
      }
      sleep(500);
    }

    logger.warn(TAG, "Element not found for action: " + actionName);
    return null;
  },

  /**
   * 按策略类型查找控件
   * @param {Object} strategy - { type, value, x_percent, y_percent }
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
      default:
        return null;
    }
  },

  /**
   * 点击元素（支持控件点击和坐标点击）
   * @param {UiObject} element
   * @returns {boolean}
   */
  clickElement: function (element) {
    if (!element) return false;

    if (element.isCoordinate) {
      logger.debug(TAG, "Clicking coordinate: (" + element.x + ", " + element.y + ")");
      return click(element.x, element.y);
    }

    if (element.clickable()) {
      return element.click();
    } else {
      // 控件不可点击，尝试点击其父元素或坐标
      var bounds = element.bounds();
      if (bounds) {
        return click(bounds.centerX(), bounds.centerY());
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
      logger.warn(TAG, "Failed to capture UI snapshot: " + e.message);
    }
    return snapshot;
  },
};

module.exports = uiOperator;
