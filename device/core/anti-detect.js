// device/core/anti-detect.js
var config = require("../config");
var logger = require("../utils/logger");
var bezier = require("../utils/bezier");

var TAG = "ANTI_DETECT";
var settings = config.antiDetect;

var antiDetect = {
  /**
   * 操作前随机延迟
   * @param {string} actionName - 操作名称（用于日志）
   */
  randomDelay: function (actionName) {
    var delay = Math.floor(
      Math.random() * (settings.delayMax - settings.delayMin) + settings.delayMin
    );
    logger.debug(TAG, "Delay " + delay + "ms before " + (actionName || "action"));
    sleep(delay);
  },

  /**
   * 操作后随机延迟（比操作前稍短）
   */
  postActionDelay: function () {
    var delay = Math.floor(
      Math.random() * (settings.delayMax - settings.delayMin) * 0.5 + settings.delayMin * 0.5
    );
    sleep(delay);
  },

  /**
   * 随机停顿 — 模拟用户走神
   * @returns {boolean} 是否执行了停顿
   */
  maybePause: function () {
    if (Math.random() < settings.pauseProbability) {
      var pauseDuration = Math.floor(
        Math.random() * (settings.pauseMax - settings.pauseMin) + settings.pauseMin
      );
      logger.info(TAG, "Random pause for " + Math.round(pauseDuration / 1000) + "s (simulating user distraction)");
      sleep(pauseDuration);
      return true;
    }
    return false;
  },

  /**
   * 拟人滑动 — 使用贝塞尔曲线
   * @param {number} startX
   * @param {number} startY
   * @param {number} endX
   * @param {number} endY
   */
  humanSwipe: function (startX, startY, endX, endY) {
    var path = bezier.generateSwipePath(startX, startY, endX, endY);
    logger.debug(TAG, "Human swipe with " + path.length + " points");

    // 使用 gestures 模拟多点触控轨迹
    var gesturePoints = path.map(function (p) {
      return [p.x, p.y];
    });

    var totalDuration = path.reduce(function (sum, p) {
      return sum + p.duration;
    }, 0);

    // AutoJS6 gestures API: gestures(duration, [x, y], [x, y], ...)
    var args = [totalDuration];
    for (var i = 0; i < gesturePoints.length; i++) {
      args.push(gesturePoints[i]);
    }
    gestures.apply(null, args);
  },

  /**
   * 拟人上滑（浏览下一条视频）
   * 比普通 swipe 更自然
   */
  humanSwipeUp: function () {
    var startX = device.width / 2 + Math.floor(Math.random() * 60 - 30);
    var startY = device.height * (0.65 + Math.random() * 0.1);
    var endX = device.width / 2 + Math.floor(Math.random() * 60 - 30);
    var endY = device.height * (0.25 + Math.random() * 0.1);

    this.humanSwipe(startX, startY, endX, endY);
  },

  /**
   * 操作节奏波动 — 基于基础间隔添加随机偏移
   * @param {number} baseInterval - 基础间隔（毫秒）
   * @returns {number} 波动后的间隔
   */
  varyRhythm: function (baseInterval) {
    var variation = baseInterval * settings.rhythmVariation;
    var offset = (Math.random() - 0.5) * 2 * variation;
    return Math.max(500, Math.round(baseInterval + offset));
  },

  /**
   * 包装一个操作，自动添加反检测行为
   * @param {string} actionName
   * @param {Function} actionFn - 实际操作函数
   * @returns {*} 操作返回值
   */
  wrapAction: function (actionName, actionFn) {
    this.randomDelay(actionName);
    this.maybePause();

    var result = actionFn();

    this.postActionDelay();
    return result;
  },
};

module.exports = antiDetect;
