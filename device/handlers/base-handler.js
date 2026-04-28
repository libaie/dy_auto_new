// device/handlers/base-handler.js
var uiOperator = require("../core/ui-operator");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");

var TAG = "HANDLER";

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
      logger.warn(TAG, "Retry " + (i + 1) + "/" + retries + " for action: " + actionName);
      sleep(2000 * Math.pow(2, i)); // 指数退避: 2s, 4s, 8s
    }
    logger.error(TAG, "Failed to click after " + retries + " retries: " + actionName);
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
};

module.exports = BaseHandler;
