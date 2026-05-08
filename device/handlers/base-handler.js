// device/handlers/base-handler.js
var uiOperator = require("../core/ui-operator");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");

var TAG = "处理器";

/**
 * Handler 基类 — 所有任务 handler 继承此对象
 */
var BaseHandler = {
  /**
   * 执行任务（子类必须实现）
   * @param {Object} params - 任务参数
   * @returns {Object} { success: boolean, result: Object, error?: string }
   */
  execute: function (params) {
    throw new Error("execute() not implemented");
  },

  /**
   * 确保抖音在前台，不在则启动
   * @returns {boolean}
   */
  ensureAppActive: function () {
    if (!uiOperator.isAppActive()) {
      return uiOperator.openApp();
    }
    return true;
  },

  /**
   * 安全地查找并点击元素（带重试）
   * @param {string} actionName
   * @param {number} retries
   * @returns {boolean}
   */
  safeClick: function (actionName, retries) {
    retries = retries || 3;
    for (var i = 0; i < retries; i++) {
      var element = uiOperator.findElement(actionName, 3000);
      if (element) {
        return antiDetect.wrapAction(actionName, function () {
          return uiOperator.clickElement(element);
        });
      }
      logger.warn(TAG, "重试 " + (i + 1) + "/" + retries + " 操作: " + actionName);
      sleep(2000 * Math.pow(2, i)); // 指数退避: 2s, 4s, 8s
    }
    logger.error(TAG, retries + " 次重试后仍失败: " + actionName);
    return false;
  },

  /**
   * 安全地输入文本
   * @param {string} actionName - 输入框选择器
   * @param {string} text
   * @returns {boolean}
   */
  safeInput: function (actionName, text) {
    var element = uiOperator.findElement(actionName, 5000);
    if (element) {
      return antiDetect.wrapAction("input_text", function () {
        return uiOperator.inputText(element, text);
      });
    }
    return false;
  },

  /**
   * 通过键盘回车提交（优先键盘，回退点击提交按钮）
   * @param {string} submitActionName - 提交按钮的动作名（回退方案）
   */
  submitViaKeyboard: function (submitActionName) {
    return uiOperator.submitViaKeyboard(submitActionName);
  },

  /**
   * 从当前屏幕提取视频相关文本（标题、描述、作者等）
   * @returns {string} 拼接的文本内容
   */
  _extractVideoText: function () {
    var parts = [];
    try {
      var desc = id("com.ss.android.ugc.aweme:id/desc").findOne(2000);
      if (desc && desc.text()) parts.push(desc.text());

      var author = id("com.ss.android.ugc.aweme:id/nickname").findOne(2000);
      if (author && author.text()) parts.push(author.text());

      var hashtags = className("android.widget.TextView").find();
      for (var i = 0; i < Math.min(hashtags.length, 10); i++) {
        var t = hashtags[i].text() || "";
        if (t.indexOf("#") !== -1 || t.indexOf("话题") !== -1) {
          parts.push(t);
        }
      }

      if (parts.length === 0) {
        var allTexts = className("android.widget.TextView").find();
        for (var j = 0; j < Math.min(allTexts.length, 15); j++) {
          var txt = allTexts[j].text() || "";
          if (txt.length >= 3 && !/^\d+$/.test(txt) && !/^[^一-龥a-zA-Z]+$/.test(txt)) {
            parts.push(txt);
          }
        }
      }
    } catch (e) {
      logger.debug(TAG, "提取视频文本失败: " + e.message);
    }
    return parts.join(" | ");
  },

  /**
   * 在父元素内按选择器策略查找子元素
   */
  _findChildBySelector: function (parent, actionName) {
    var selector = selectorLoader.get(actionName);
    if (!selector) return null;
    var strategies = selector.strategies.slice().sort(function (a, b) { return a.priority - b.priority; });
    for (var i = 0; i < strategies.length; i++) {
      var s = strategies[i];
      var element = null;
      switch (s.type) {
        case "id": element = parent.findOne(id(s.value)); break;
        case "text": element = parent.findOne(text(s.value)); break;
        case "desc": element = parent.findOne(desc(s.value)); break;
        case "className": element = parent.findOne(className(s.value)); break;
      }
      if (element) return element;
    }
    return null;
  },

  /**
   * 从子元素提取值（支持选择器的 purpose=extract 配置）
   */
  _extractChildValue: function (el, actionName, fallback) {
    var selector = selectorLoader.get(actionName);
    if (selector && selector.purpose === "extract") {
      var val = uiOperator.extractValue(el, selector);
      if (val != null) return val;
    }
    try { return el.text() || fallback; } catch (e) { return fallback; }
  },
};

module.exports = BaseHandler;
