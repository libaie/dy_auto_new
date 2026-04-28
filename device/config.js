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
  },

  // 日志级别: "debug", "info", "warn", "error"
  logLevel: "info",
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
