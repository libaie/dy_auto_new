// 设备端基础配置 — 仅保留连接信息，其余配置由服务端下发
var config = {
  // 后端服务地址（配对后从本地存储加载）
  serverUrl: "",

  // 设备标识（首次运行自动生成并保存）
  deviceId: "",

  // 设备密钥（配对成功后从服务端获取，保存在本地存储）
  deviceSecret: "",

  // --- 以下配置均由服务端下发，设备端仅提供默认值 ---

  // 轮询间隔（毫秒）
  pollInterval: 10000,

  // 心跳间隔（毫秒）
  heartbeatInterval: 60000,

  // 日志级别: "debug", "info", "warn", "error"
  logLevel: "info",

  // 反检测配置（从服务端 register/poll 获取）
  antiDetect: {
    delayMin: 1000,
    delayMax: 5000,
    rhythmVariation: 0.3,
    pauseProbability: 0.1,
    pauseMin: 5000,
    pauseMax: 15000,
    activeHours: {
      start: 7,
      end: 23,
      peaks: [
        { start: 7, end: 9, weight: 20 },
        { start: 11, end: 13, weight: 25 },
        { start: 17, end: 20, weight: 30 },
        { start: 20, end: 23, weight: 25 },
      ],
    },
  },

  // 反检测配置版本（用于增量更新）
  antiDetectVersion: 0,

  // 代理配置（从服务端 poll 响应获取后动态设置）
  proxy: null,

  // AI 分析配置（通过服务端 poll 下发）
  ai: {
    apiUrl: "https://api.deepseek.com/v1/chat/completions",
    apiKey: "",
    model: "deepseek-chat",
    maxTokens: 256,
    temperature: 0.7,
  },
};

// 生成或读取设备 ID，加载已保存的密钥和服务端地址
(function () {
  var storage = storages.create("dy_auto");
  var savedId = storage.get("device_id", "");
  if (!savedId) {
    savedId = "dev-" + new Date().getTime() + "-" + Math.random().toString(36).substr(2, 6);
    storage.put("device_id", savedId);
  }
  config.deviceId = savedId;

  // 从本地存储加载配对信息
  var savedSecret = storage.get("device_secret", "");
  if (savedSecret) config.deviceSecret = savedSecret;
  var savedUrl = storage.get("server_url", "");
  if (savedUrl) config.serverUrl = savedUrl;
})();

// 通过 global 共享 config 引用，避免 require 路径不一致导致的多实例问题
// main.js: require("./config"), api-client.js: require("../config") 可能产生不同对象
global.__config = config;
module.exports = config;
