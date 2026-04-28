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
   * 检查当前是否在活跃时间窗口内
   * @returns {boolean}
   */
  isActiveHour: function () {
    var hour = new Date().getHours();
    var hours = settings.activeHours;
    if (!hours) return true; // 未配置则不限制
    return hour >= hours.start && hour < hours.end;
  },

  /**
   * 获取当前时段的操作建议延迟倍率
   * 高峰时段延迟短、低谷时段延迟长
   * @returns {number} 倍率 (0.5 ~ 2.0)
   */
  getTimeMultiplier: function () {
    var hour = new Date().getHours();
    var hours = settings.activeHours;
    if (!hours || !hours.peaks) return 1.0;

    for (var i = 0; i < hours.peaks.length; i++) {
      var peak = hours.peaks[i];
      if (hour >= peak.start && hour < peak.end) {
        // 高峰时段：权重越高，延迟越短
        return Math.max(0.5, 1.0 - (peak.weight / 100));
      }
    }
    // 非高峰时段：延迟稍长
    return 1.5;
  },

  /**
   * 增强的拟人滑动 — 带速度变化和微抖动
   * @param {number} startX
   * @param {number} startY
   * @param {number} endX
   * @param {number} endY
   */
  humanSwipeEnhanced: function (startX, startY, endX, endY) {
    // 添加起点微抖动（手指按下时不完全静止）
    var jitterX = Math.floor(Math.random() * 6 - 3);
    var jitterY = Math.floor(Math.random() * 6 - 3);
    startX += jitterX;
    startY += jitterY;

    // 滑动距离越长，速度越快
    var distance = Math.sqrt(Math.pow(endX - startX, 2) + Math.pow(endY - startY, 2));
    var speedFactor = Math.min(1.5, distance / 500);

    var path = bezier.generateSwipePath(startX, startY, endX, endY);
    logger.debug(TAG, "Enhanced swipe: " + path.length + " points, speed=" + speedFactor.toFixed(2));

    var gesturePoints = path.map(function (p) {
      return [p.x, p.y];
    });

    var totalDuration = path.reduce(function (sum, p) {
      return sum + Math.round(p.duration / speedFactor);
    }, 0);

    var args = [totalDuration];
    for (var i = 0; i < gesturePoints.length; i++) {
      args.push(gesturePoints[i]);
    }
    gestures.apply(null, args);
  },

  /**
   * 模拟随机点击偏移 — 不总是精确点击控件中心
   * @param {number} centerX - 控件中心 X
   * @param {number} centerY - 控件中心 Y
   * @param {number} radius - 偏移半径（像素），默认 10
   * @returns {{x: number, y: number}}
   */
  randomClickOffset: function (centerX, centerY, radius) {
    radius = radius || 10;
    var angle = Math.random() * Math.PI * 2;
    var r = Math.random() * radius;
    return {
      x: Math.round(centerX + r * Math.cos(angle)),
      y: Math.round(centerY + r * Math.sin(angle)),
    };
  },

  /**
   * 从服务端配置更新反检测参数
   * @param {Object} serverConfig - 服务端下发的反检测配置
   */
  updateFromServer: function (serverConfig) {
    if (!serverConfig) return;

    if (serverConfig.delay_min !== undefined) settings.delayMin = serverConfig.delay_min;
    if (serverConfig.delay_max !== undefined) settings.delayMax = serverConfig.delay_max;
    if (serverConfig.rhythm_variation !== undefined) settings.rhythmVariation = serverConfig.rhythm_variation;
    if (serverConfig.pause_probability !== undefined) settings.pauseProbability = serverConfig.pause_probability;
    if (serverConfig.pause_min !== undefined) settings.pauseMin = serverConfig.pause_min;
    if (serverConfig.pause_max !== undefined) settings.pauseMax = serverConfig.pause_max;
    if (serverConfig.active_hours !== undefined) settings.activeHours = serverConfig.active_hours;

    logger.info(TAG, "Anti-detect config updated from server");
  },

  /**
   * 包装一个操作，自动添加反检测行为
   * @param {string} actionName
   * @param {Function} actionFn - 实际操作函数
   * @returns {*} 操作返回值
   */
  wrapAction: function (actionName, actionFn) {
    // 时间窗口检查
    if (!this.isActiveHour()) {
      logger.info(TAG, "Outside active hours, adding long delay");
      sleep(Math.floor(Math.random() * 60000 + 30000)); // 30-90秒
      return false;
    }

    var timeMultiplier = this.getTimeMultiplier();
    this.randomDelay(actionName);

    // 概率跳过（低谷时段偶尔跳过操作，更像真人）
    if (Math.random() < 0.05 * timeMultiplier) {
      logger.info(TAG, "Skipping action (rhythm variation)");
      return false;
    }

    this.maybePause();
    var result = actionFn();
    this.postActionDelay();
    return result;
  },
};

module.exports = antiDetect;
