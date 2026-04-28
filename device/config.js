var config = {
  // 后端服务地址
  serverUrl: "http://192.168.1.100:8000",

  // 设备标识（首次运行自动生成并保存）
  deviceId: "",

  // 设备密钥（与后端 DEVICE_SECRET 一致）
  deviceSecret: "change-me-to-a-random-string",

  // 轮询间隔（毫秒）
  pollInterval: 10000,

  // 心跳间隔（毫秒）
  heartbeatInterval: 60000,

  // 反检测配置
  antiDetect: {
    // 操作前随机延迟范围（毫秒）
    delayMin: 1000,
    delayMax: 5000,
    // 操作节奏波动（±百分比）
    rhythmVariation: 0.3,
    // 随机停顿概率（0-1）
    pauseProbability: 0.1,
    // 随机停顿时长范围（毫秒）
    pauseMin: 5000,
    pauseMax: 15000,
    // 操作时间窗口（24小时制，模拟真实用户活跃时段）
    activeHours: {
      start: 7,    // 早上7点开始
      end: 23,     // 晚上11点结束
      // 各时段权重（模拟早中晚高峰）
      peaks: [
        { start: 7, end: 9, weight: 20 },    // 早高峰
        { start: 11, end: 13, weight: 25 },   // 午间
        { start: 17, end: 20, weight: 30 },   // 晚高峰
        { start: 20, end: 23, weight: 25 },   // 晚间
      ],
    },
  },

  // 代理配置（从服务端 poll 响应获取后动态设置）
  proxy: null,  // { type: "http", host: "...", port: 8080, username: "...", password: "..." }

  // 反检测配置版本（用于增量更新）
  antiDetectVersion: 0,

  // 日志级别: "debug", "info", "warn", "error"
  logLevel: "info",

  // 网络配置
  network: {
    requestTimeout: 10000,
    maxRetries: 3,
    retryBaseDelay: 2000,
    retryMaxDelay: 30000,
    offlineQueueMax: 100,
  },
};

// 生成或读取设备 ID
(function () {
  var storage = storages.create("dy_auto");
  var savedId = storage.get("device_id", "");
  if (!savedId) {
    savedId = "dev-" + new Date().getTime() + "-" + Math.random().toString(36).substr(2, 6);
    storage.put("device_id", savedId);
  }
  config.deviceId = savedId;
})();

module.exports = config;
