var logger = require("../utils/logger");

var TAG = "RECOVERY";

var crashRecovery = {
  _consecutiveFailures: 0,
  _maxConsecutiveFailures: 5,

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

  handleDialogs: function () {
    var dialogButtons = [
      "知道了", "确定", "关闭", "取消", "重试",
      "允许", "暂不", "稍后再说", "下次再说",
    ];

    for (var i = 0; i < dialogButtons.length; i++) {
      try {
        var btn = text(dialogButtons[i]).findOnce();
        if (btn) {
          logger.info(TAG, "Found dialog button: " + dialogButtons[i]);
          btn.click();
          sleep(1000);
          return true;
        }
      } catch (e) { /* ignore */ }
    }

    var riskKeywords = ["验证", "风控", "异常", "安全检查", "滑动"];
    for (var j = 0; j < riskKeywords.length; j++) {
      try {
        var riskEl = textContains(riskKeywords[j]).findOnce();
        if (riskEl) {
          logger.warn(TAG, "Detected risk control dialog: " + riskKeywords[j]);
          return "risk_controlled";
        }
      } catch (e) { /* ignore */ }
    }

    return false;
  },

  checkANR: function () {
    try {
      var anrBtn = text("等待").findOnce();
      if (anrBtn) {
        logger.warn(TAG, "ANR detected, clicking 'Wait'");
        anrBtn.click();
        sleep(2000);
        return true;
      }
    } catch (e) { /* ignore */ }
    return false;
  },

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
