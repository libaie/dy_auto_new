// 设备崩溃恢复模块，负责记录运行现场并在异常后恢复任务状态。
var logger = require("../utils/logger");

var TAG = "RECOVERY";

var crashRecovery = {
  _consecutiveFailures: 0,
  _maxConsecutiveFailures: 5,

  /**
   * 设置当前执行的账号 ID（由 task-executor 调用）
   */
  // 入参：accountId 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 setAccountId 对应业务流程的处理结果。
  setAccountId: function (accountId) {
    this._currentAccountId = accountId;
  },

  // 设备业务函数：处理 ensureAppRunning 对应的抖音自动化动作、状态或安全边界。
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 ensureAppRunning 对应业务流程的处理结果。
  ensureAppRunning: function () {
    if (currentPackage() === "com.ss.android.ugc.aweme") {
      this._consecutiveFailures = 0;
      return true;
    }

    logger.warn(TAG, "Douyin not in foreground, attempting recovery...");
    this._consecutiveFailures++;

    if (this._consecutiveFailures > this._maxConsecutiveFailures) {
      logger.error(TAG, "Too many consecutive failures (" + this._consecutiveFailures +
        "), pausing for 5 minutes");
      sleep(300000);
      this._consecutiveFailures = 0;
    }

    try {
      app.stop("com.ss.android.ugc.aweme");
      sleep(2000);
    } catch (e) {
      logger.warn(TAG, "Failed to stop app: " + e.message);
    }

    try {
      app.launchApp("抖音");
      sleep(5000);
      if (currentPackage() === "com.ss.android.ugc.aweme") {
        logger.info(TAG, "Douyin recovered successfully");
        sleep(3000);
        try { back(); } catch (e) { /* ignore */ }
        return true;
      }
    } catch (e) {
      logger.error(TAG, "Failed to restart app: " + e.message);
    }

    logger.error(TAG, "Recovery failed");
    return false;
  },

  // 设备业务函数：处理 handleDialogs 对应的抖音自动化动作、状态或安全边界。
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 handleDialogs 对应业务流程的处理结果。
  handleDialogs: function () {
    var dialogButtons = [
      "知道了", "确定", "关闭", "重试",
      "允许", "暂不", "稍后再说", "下次再说",
    ];

    for (var i = 0; i < dialogButtons.length; i++) {
      try {
        var btn = text(dialogButtons[i]).findOne(2000);
        if (btn) {
          logger.info(TAG, "Found dialog button: " + dialogButtons[i]);
          // 只点击已识别的系统弹窗按钮，避免恢复流程误触业务页面。
          btn.click();
          sleep(1000);
          return true;
        }
      } catch (e) { /* ignore */ }
    }

    // 风控关键词检测
    var riskPatterns = [
      { keywords: ["验证", "安全验证", "滑动验证"], type: "captcha" },
      { keywords: ["风控", "操作频繁", "请稍后再试"], type: "rate_limit" },
      { keywords: ["异常", "账号异常", "登录异常"], type: "account_risk" },
      { keywords: ["安全检查", "身份验证"], type: "security_check" },
    ];

    for (var j = 0; j < riskPatterns.length; j++) {
      var pattern = riskPatterns[j];
      for (var k = 0; k < pattern.keywords.length; k++) {
        try {
          var riskEl = textContains(pattern.keywords[k]).findOne(2000);
          if (riskEl) {
            logger.warn(TAG, "Risk detected: " + pattern.type + " (" + pattern.keywords[k] + ")");
            // 上报服务端
            if (this._currentAccountId) {
              try {
                var apiClient = require("./api-client");
                apiClient.reportRiskControl(
                  this._currentAccountId,
                  pattern.type,
                  { keyword: pattern.keywords[k] }
                );
              } catch (e) {
                logger.warn(TAG, "Failed to report risk: " + e.message);
              }
            }
            return "risk_controlled";
          }
        } catch (e) { /* ignore */ }
      }
    }

    return false;
  },

  // 设备业务函数：处理 checkANR 对应的抖音自动化动作、状态或安全边界。
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 checkANR 对应业务流程的处理结果。
  checkANR: function () {
    try {
      var anrBtn = text("等待").findOne(2000);
      if (anrBtn) {
        logger.warn(TAG, "ANR detected, clicking 'Wait'");
        anrBtn.click();
        sleep(2000);
        return true;
      }
    } catch (e) { /* ignore */ }
    return false;
  },

  // 设备业务函数：处理 healthCheck 对应的抖音自动化动作、状态或安全边界。
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 healthCheck 对应业务流程的处理结果。
  healthCheck: function () {
    if (this.checkANR()) {
      logger.warn(TAG, "ANR handled, waiting for recovery...");
      sleep(5000);
    }

    var dialogResult = this.handleDialogs();
    if (dialogResult === "risk_controlled") {
      logger.error(TAG, "Risk control detected, stopping current task");
      return false;
    }

    if (!this.ensureAppRunning()) {
      return false;
    }

    return true;
  },
};

module.exports = crashRecovery;
