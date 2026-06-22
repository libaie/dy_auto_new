// device/core/anti-detect.js
var config = global.__config || require("../config");
var logger = require("../utils/logger");
var bezier = require("../utils/bezier");

var TAG = "反检测";
var settings = config.antiDetect;
var MAX_SWIPE_DURATION = 1500;  // 单次手势耗时熔断上限，防止阻塞 Accessibility 线程

var antiDetect = {
  _skipDisabled: false,  // 序列发送期间禁用随机跳过
  /**
   * 操作前随机延迟
   * @param {string} actionName - 操作名称（用于日志）
   */
  // 入参：actionName 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 randomDelay 对应业务流程的处理结果。
  randomDelay: function (actionName) {
    var delay = Math.floor(
      Math.random() * (settings.delayMax - settings.delayMin) + settings.delayMin
    );
    logger.debug(TAG, "操作前延迟 " + delay + "ms: " + (actionName || "操作"));
    sleep(delay);
  },

  /**
   * 操作后随机延迟（比操作前稍短）
   */
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 postActionDelay 对应业务流程的处理结果。
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
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 maybePause 对应业务流程的处理结果。
  maybePause: function () {
    if (Math.random() < settings.pauseProbability) {
      var pauseDuration = Math.floor(
        Math.random() * (settings.pauseMax - settings.pauseMin) + settings.pauseMin
      );
      logger.info(TAG, "随机停顿 " + Math.round(pauseDuration / 1000) + "秒（模拟用户走神）");
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
  // 设备业务函数：处理 humanSwipe 对应的抖音自动化动作、状态或安全边界。
  // 入参：startX、startY、endX、endY 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 humanSwipe 对应业务流程的处理结果。
  humanSwipe: function (startX, startY, endX, endY) {
    var path = bezier.generateSwipePath(startX, startY, endX, endY);
    logger.debug(TAG, "拟人滑动 " + path.length + " 个轨迹点");

    // 使用 gestures 模拟多点触控轨迹
    var gesturePoints = path.map(function (p) {
      return [p.x, p.y];
    });

    var totalDuration = path.reduce(function (sum, p) {
      return sum + p.duration;
    }, 0);

    // 熔断保护: 总耗时不超过 MAX_SWIPE_DURATION，防止 Accessibility 线程僵死
    totalDuration = Math.min(totalDuration, MAX_SWIPE_DURATION);
    gestures([0, totalDuration].concat(gesturePoints));
  },

  /**
   * 拟人上滑（浏览下一条视频）
   * 比普通 swipe 更自然
   */
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 humanSwipeUp 对应业务流程的处理结果。
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
  // 入参：baseInterval 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 varyRhythm 对应业务流程的处理结果。
  varyRhythm: function (baseInterval) {
    var variation = baseInterval * settings.rhythmVariation;
    var offset = (Math.random() - 0.5) * 2 * variation;
    return Math.max(500, Math.round(baseInterval + offset));
  },

  /**
   * 检查当前是否在活跃时间窗口内
   * @returns {boolean}
   */
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 isActiveHour 对应业务流程的处理结果。
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
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 getTimeMultiplier 对应业务流程的处理结果。
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
  // 设备业务函数：处理 humanSwipeEnhanced 对应的抖音自动化动作、状态或安全边界。
  // 入参：startX、startY、endX、endY 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 humanSwipeEnhanced 对应业务流程的处理结果。
  humanSwipeEnhanced: function (startX, startY, endX, endY) {
    // 添加起点微抖动（手指按下时不完全静止）
    var jitterX = Math.floor(Math.random() * 6 - 3);
    var jitterY = Math.floor(Math.random() * 6 - 3);
    startX += jitterX;
    startY += jitterY;

    // 滑动距离越长，速度越快
    var distance = Math.sqrt(Math.pow(endX - startX, 2) + Math.pow(endY - startY, 2));
    var speedFactor = Math.max(0.5, Math.min(1.5, distance / 500));

    var path = bezier.generateSwipePath(startX, startY, endX, endY);
    logger.debug(TAG, "增强滑动: " + path.length + " 个轨迹点, 速度=" + speedFactor.toFixed(2));

    var gesturePoints = path.map(function (p) {
      return [p.x, p.y];
    });

    var totalDuration = path.reduce(function (sum, p) {
      return sum + Math.round(p.duration / speedFactor);
    }, 0);

    totalDuration = Math.min(totalDuration, MAX_SWIPE_DURATION);
    gestures([0, totalDuration].concat(gesturePoints));
  },

  /**
   * 模拟随机点击偏移 — 不总是精确点击控件中心
   * @param {number} centerX - 控件中心 X
   * @param {number} centerY - 控件中心 Y
   * @param {number} radius - 偏移半径（像素），默认 10
   * @returns {{x: number, y: number}}
   */
  // 入参：centerX、centerY、radius 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 randomClickOffset 对应业务流程的处理结果。
  randomClickOffset: function (centerX, centerY, radius) {
    radius = radius || 10;
    var angle = Math.random() * Math.PI * 2;
    var r = radius * Math.sqrt(Math.random());
    return {
      x: Math.round(centerX + r * Math.cos(angle)),
      y: Math.round(centerY + r * Math.sin(angle)),
    };
  },

  /**
   * 从服务端配置更新反检测参数
   * @param {Object} serverConfig - 服务端下发的反检测配置
   */
  // 入参：serverConfig 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 updateFromServer 对应业务流程的处理结果。
  updateFromServer: function (serverConfig) {
    if (!serverConfig) return;

    if (serverConfig.delay_min !== undefined) settings.delayMin = serverConfig.delay_min;
    if (serverConfig.delay_max !== undefined) settings.delayMax = serverConfig.delay_max;
    if (serverConfig.rhythm_variation !== undefined) settings.rhythmVariation = serverConfig.rhythm_variation;
    if (serverConfig.pause_probability !== undefined) settings.pauseProbability = serverConfig.pause_probability;
    if (serverConfig.pause_min !== undefined) settings.pauseMin = serverConfig.pause_min;
    if (serverConfig.pause_max !== undefined) settings.pauseMax = serverConfig.pause_max;
    if (serverConfig.active_hours !== undefined) settings.activeHours = serverConfig.active_hours;

    logger.info(TAG, "反检测配置已从服务端更新");
  },

  /**
   * 包装一个操作，自动添加反检测行为
   * @param {string} actionName
   * @param {Function} actionFn - 实际操作函数
   * @returns {*} 操作返回值
   */
  // 入参：actionName、actionFn 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 wrapAction 对应业务流程的处理结果。
  wrapAction: function (actionName, actionFn) {
    var timeMultiplier = this.getTimeMultiplier();
    this.randomDelay(actionName);

    // 概率跳过（低谷时段偶尔跳过操作，更像真人）
    if (!this._skipDisabled && Math.random() < 0.01 * timeMultiplier) {
      logger.info(TAG, "跳过操作（节奏波动）");
      return false;
    }

    var result = actionFn();
    this.postActionDelay();
    return result;
  },
};

module.exports = antiDetect;
