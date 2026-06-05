# Device Project — Complete Source

Total files: 31

---

## config.js

```javascript
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
```

## main.js

```javascript
// device/main.js
var config = require("./config");
var apiClient = require("./core/api-client");
var selectorLoader = require("./core/selector-loader");
var promptTemplateLoader = require("./core/prompt-template-loader");
var taskExecutor = require("./core/task-executor");
var logger = require("./utils/logger");
var updateChecker = require("./core/update-checker");
var crashRecovery = require("./core/crash-recovery");
var antiDetect = require("./core/anti-detect");
var floatingWindow = require("./core/floating-window");
var pairing = require("./core/pairing");
var deviceWs = require("./core/device-ws");
var SearchBaseHandler = require("./handlers/search-base");

var TAG = "主程序";

/**
 * 收集设备硬件信息（通过 AutoJS6 device API）
 */
function collectDeviceInfo() {
  var info = {};
  try {
    info.screen_resolution = device.width + "x" + device.height;
  } catch (e) { /* ignore */ }
  try {
    info.sdk_version = String(device.buildId || "");
  } catch (e) { /* ignore */ }
  try {
    // device.totalMem returns bytes
    if (device.totalMem) {
      info.total_memory = device.totalMem;
    }
  } catch (e) { /* ignore */ }
  try {
    info.manufacturer = device.brand || "";
  } catch (e) { /* ignore */ }
  try {
    info.product = device.product || "";
  } catch (e) { /* ignore */ }
  try {
    info.device_model = device.model || "";
  } catch (e) { /* ignore */ }
  try {
    info.hardware = device.hardware || "";
  } catch (e) { /* ignore */ }
  try {
    info.display = device.display || "";
  } catch (e) { /* ignore */ }
  return info;
}

// 脚本退出时通知服务端断开，避免服务端等待 TCP 超时
events.on("exit", function () {
  try {
    deviceWs.sendDisconnect();
  } catch (e) { /* ignore */ }
});

/**
 * 配对流程 — 未配对时显示配对界面，配对完成后启动主循环
 */
function startPairingFlow() {
  logger.info(TAG, "设备未配对，进入配对流程");

  floatingWindow.showPairingUI(function (serverIp) {
    // 用户点击"连接"后的回调
    var deviceName = device.model + " (" + device.brand + ")";
    var result = pairing.request(serverIp, config.deviceId, deviceName, device.release, "1.0.0", collectDeviceInfo());

    if (!result) {
      floatingWindow.updatePairStatus("连接失败，请检查 IP 地址");
      return;
    }

    if (result.status === "approved") {
      // 已批准（重复配对），直接启动
      logger.info(TAG, "配对已批准，启动主循环");
      var url = pairing.getSavedServerUrl();
      var sec = pairing.getSavedSecret();
      floatingWindow.showMainUI();
      global.__paired = true;
      startMainLoop(url, sec);
      return;
    }

    // pending — 切换到等待界面，通过 WS 实时等待审批
    floatingWindow.showWaitingUI();
    startPairingWait();
  });
}

/**
 * WS 实时等待审批 — 优先使用 WebSocket，失败时 fallback 到轮询
 */
function startPairingWait() {
  threads.start(function () {
    var result = pairing.waitForApproval(function (status, data) {
      // WS 回调仅更新文本，不操作窗口生命周期
      logger.info(TAG, "配对状态: " + status);
    });

    if (result && result.status === "approved") {
      logger.info(TAG, "配对已批准，启动主循环");
      var url = pairing.getSavedServerUrl();
      var sec = pairing.getSavedSecret();
      floatingWindow.showMainUI();
      global.__paired = true;
      startMainLoop(url, sec);
    } else if (result && result.status === "rejected") {
      logger.warn(TAG, "配对被拒绝，2 秒后重新显示配对界面");
      floatingWindow.updatePairStatus("配对已被拒绝");
      setTimeout(function () {
        startPairingFlow();
      }, 2000);
    } else {
      // WS 超时或连接失败，fallback 到 HTTP 轮询
      logger.warn(TAG, "WS 等待失败，回退到轮询模式");
      startPairingPoll();
    }
  });
}

/**
 * 配对轮询 — 定期检查审批结果
 */
function startPairingPoll() {
  var pollInterval = 5000; // 5秒轮询一次
  var maxWait = 300000;    // 最长等待5分钟
  var startTime = Date.now();

  var pollTimer = setInterval(function () {
    // 超时检查
    if (Date.now() - startTime > maxWait) {
      clearInterval(pollTimer);
      floatingWindow.updatePairStatus("配对超时，请重新连接");
      logger.warn(TAG, "配对超时");
      setTimeout(function () {
        floatingWindow.showPairingUI(function (ip) {
          // 重新发起配对
          var devName = device.model + " (" + device.brand + ")";
          var res = pairing.request(ip, config.deviceId, devName, device.release, "1.0.0", collectDeviceInfo());
          if (res && res.status === "pending") {
            floatingWindow.showWaitingUI();
            startPairingPoll();
          } else if (res && res.status === "approved") {
            floatingWindow.showMainUI();
            global.__paired = true;
            startMainLoop(pairing.getSavedServerUrl(), pairing.getSavedSecret());
          }
        });
      }, 2000);
      return;
    }

    var status = pairing.checkStatus();
    if (!status) return;

    if (status.status === "approved") {
      clearInterval(pollTimer);
      logger.info(TAG, "配对已批准，启动主循环");
      floatingWindow.showMainUI();
      global.__paired = true;
      startMainLoop(pairing.getSavedServerUrl(), pairing.getSavedSecret());
    } else if (status.status === "rejected") {
      clearInterval(pollTimer);
      logger.warn(TAG, "配对被拒绝，2 秒后重新显示配对界面");
      floatingWindow.updatePairStatus("配对已被拒绝");
      setTimeout(function () {
        startPairingFlow();
      }, 2000);
    }
    // pending — 继续等待
  }, pollInterval);
}

/**
 * 主循环 — 事件驱动，通过 WS 推送接收任务
 * @param {string} [serverUrl] - 服务端地址（配对成功时显式传入）
 * @param {string} [secret] - 设备密钥（配对成功时显式传入）
 */
function startMainLoop(serverUrl, secret) {
  // 使用显式参数或从 storage 读取
  config.serverUrl = serverUrl || pairing.getSavedServerUrl();
  config.deviceSecret = secret || pairing.getSavedSecret();

  if (!config.serverUrl || !config.deviceSecret) {
    logger.error(TAG, "服务端地址或密钥为空，无法启动");
    return;
  }

  logger.info(TAG, "Device ID: " + config.deviceId);
  logger.info(TAG, "Server: " + config.serverUrl);
  logger.info(TAG, "Secret: " + config.deviceSecret.substring(0, 8) + "...");

  var heartbeatTimer = null;

  // 任务队列 — WS 推送的任务排队执行
  var _taskBusy = false;
  var _taskQueue = [];
  _mainLoopRuntime.isIdle = function () { return !_taskBusy && _taskQueue.length === 0; };
  _mainLoopRuntime.catchUpPoll = function () { catchUpPoll(); };

  function handleTask(task) {
    _taskQueue.push(task);
    processTaskQueue();
  }

  function processTaskQueue() {
    if (_taskBusy || _taskQueue.length === 0) return;
    _taskBusy = true;
    _idleTicks = 0;
    var task = _taskQueue.shift();

    // Watchdog: 10min 超时 → 取消任务，不释放 busy 锁
    // 旧线程检查 isCancelled() 后退出 → finally 块释放锁 → 防止并发执行
    var TASK_TIMEOUT_MS = 600000;
    var GRACE_PERIOD_MS = 120000;  // 2min 兜底——线程完全无响应时强制释放
    var _completed = false;
    var _watchdogFired = false;
    var _watchdog = setTimeout(function () {
      if (!_completed) {
        logger.error(TAG, "任务超时 (" + (TASK_TIMEOUT_MS / 60000) + "min): " + task.id + "，取消任务");
        _watchdogFired = true;
        taskExecutor.cancel(task.id);
        // 2min 兜底: 如果线程仍不退出，强制释放锁（避免设备永久不可用）
        setTimeout(function () {
          if (!_completed) {
            logger.error(TAG, "任务 " + task.id + " 取消后2min仍未退出，强制释放 busy 锁(需重启设备)");
            _taskBusy = false;
            _completed = true;
          }
        }, GRACE_PERIOD_MS);
      }
    }, TASK_TIMEOUT_MS);

    threads.start(function () {
      try {
        logger.info(TAG, "执行任务: " + task.id + " (" + task.type + ")");
        floatingWindow.setStatus("running");

        var flowContext = require("./core/flow-context");
        flowContext.reset();

        var result = taskExecutor.execute(task);

        // 上报结果
        var uiSnapshot = null;
        if (result.status === "failed") {
          try {
            var uiOperator = require("./core/ui-operator");
            uiSnapshot = uiOperator.captureUISnapshot();
          } catch (e) {
            logger.warn(TAG, "截取界面快照失败: " + e.message);
          }
        }

        var reportResult = apiClient.report(task.id, result.status, result.result, uiSnapshot);
        if (reportResult) {
          logger.info(TAG, "任务结果已上报: " + result.status);
        } else {
          logger.warn(TAG, "任务结果上报失败，已加入离线队列重试: " + result.status);
        }
        floatingWindow.setStatus(result.status === "completed" ? "success" : "error");
      } catch (e) {
        logger.error(TAG, "任务执行异常: " + e.message);
      } finally {
        if (_watchdog) clearTimeout(_watchdog);
        if (!_completed) {
          _completed = true;
          _taskBusy = false;
          processTaskQueue();

          if (_taskQueue.length === 0 && !_taskBusy) {
            catchUpPoll();
          }
        }
        // 如果 _completed 已被 watchdog 设为 true，跳过重复的 unlock
      }
    });
  }

  function applyDMSequences(dmSequences) {
    var dmCache = {};
    dmSequences = dmSequences || [];
    for (var dsi = 0; dsi < dmSequences.length; dsi++) {
      var ds = dmSequences[dsi];
      if (ds && ds.id) dmCache[ds.id] = ds;
    }
    SearchBaseHandler._dmSeqCache = dmCache;
    logger.debug(TAG, "DM序列缓存已同步: " + dmSequences.length);
  }

  function applyPollSideData(response) {
    if (!response) return;
    if (response.proxy) apiClient.setProxy(response.proxy);
    if (response.device_config) applyServerConfig(response.device_config);
    if (response.anti_detect_config) antiDetect.updateFromServer(response.anti_detect_config);
    if (response.selectors_version) selectorLoader.checkAndUpdate(response.selectors_version);
    if (response.prompt_templates_version) promptTemplateLoader.checkAndUpdate(response.prompt_templates_version);
    if (response.dm_sequences !== undefined) applyDMSequences(response.dm_sequences);
    if (response.server_date) SearchBaseHandler._serverDate = response.server_date;
  }

  function syncDMSequences() {
    try {
      var response = apiClient.fetchDMSequences();
      if (response && response.dm_sequences !== undefined) applyDMSequences(response.dm_sequences);
    } catch (e) {
      logger.warn(TAG, "DM序列同步失败: " + e.message);
    }
  }

  // 认证失败处理
  var authFailed = false;
  function handleAuthFailure() {
    if (authFailed) return;
    authFailed = true;
    logger.error(TAG, "设备认证失败，清除配对信息，重新配对");

    config.deviceSecret = "";
    config.serverUrl = "";

    deviceWs.stop();
    if (heartbeatTimer) clearInterval(heartbeatTimer);
    pairing.clear();

    global.__paired = false;
    floatingWindow.showPairingUI(function (serverIp) {
      var deviceName = device.model + " (" + device.brand + ")";
      var result = pairing.request(serverIp, config.deviceId, deviceName, device.release, "1.0.0", collectDeviceInfo());
      if (!result) {
        floatingWindow.updatePairStatus("连接失败，请检查 IP 地址");
        return;
      }
      if (result.status === "approved") {
        floatingWindow.showMainUI();
        global.__paired = true;
        startMainLoop(pairing.getSavedServerUrl(), pairing.getSavedSecret());
        return;
      }
      floatingWindow.showWaitingUI();
      startPairingWait();
    });
  }
  apiClient.setAuthFailureHandler(handleAuthFailure);
  deviceWs.setAuthFailureHandler(handleAuthFailure);

  // WS 重连后重新 poll 捕获离线期间的任务
  deviceWs.setOnConnectedHandler(function () {
    if (authFailed) return;
    logger.info(TAG, "WS 重连，执行 catch-up poll...");
    catchUpPoll();
  });

  // 注册 WS 推送回调
  deviceWs.setCallbacks({
    onTask: function (task) {
      syncDMSequences();
      handleTask(task);
    },
    onCancelTask: function (taskId) {
      logger.info(TAG, "收到取消任务: " + taskId);
      taskExecutor.cancel(taskId);
    },
    onSelectorsUpdated: function (version) {
      logger.info(TAG, "选择器更新: v" + version);
      selectorLoader.checkAndUpdate(version);
    },
    onPromptTemplatesUpdated: function (version) {
      logger.info(TAG, "提示词模板更新: v" + version);
      promptTemplateLoader.checkAndUpdate(version);
    },
    onConfigUpdated: function (serverConfig, proxy) {
      if (serverConfig) applyServerConfig(serverConfig);
      if (proxy) apiClient.setProxy(proxy);
    },
    onNewTaskAvailable: function () {
      catchUpPoll();
    },
    onDeviceRemoved: function () {
      logger.error(TAG, "设备已被服务端移除，返回配对界面");
      deviceWs.stop();
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      pairing.clear();
      config.deviceSecret = "";
      config.serverUrl = "";
      global.__paired = false;
      floatingWindow.showPairingUI(function (serverIp) {
        var deviceName = device.model + " (" + device.brand + ")";
        var result = pairing.request(serverIp, config.deviceId, deviceName, device.release, "1.0.0", collectDeviceInfo());
        if (!result) {
          floatingWindow.updatePairStatus("连接失败，请检查 IP 地址");
          return;
        }
        if (result.status === "approved") {
          floatingWindow.showMainUI();
          global.__paired = true;
          startMainLoop(pairing.getSavedServerUrl(), pairing.getSavedSecret());
          return;
        }
        floatingWindow.showWaitingUI();
        startPairingWait();
      });
    },
  });

  // 启动 WS
  // 初始化选择器（必须在 WS 连接前完成，否则 catch-up 任务找不到选择器）
  selectorLoader.init();
  promptTemplateLoader.init();

  try {
    deviceWs.start();
  } catch (e) {
    logger.warn(TAG, "设备 WS 启动失败: " + e.message);
  }

  // 检查脚本更新
  try {
    var updated = updateChecker.checkAndUpdate();
    if (updated) {
      logger.info(TAG, "脚本已更新，请重启以使用新版本");
    }
  } catch (e) {
    logger.warn(TAG, "更新检查失败: " + e.message);
  }

  // 设备注册，获取完整配置
  try {
    var extraInfo = collectDeviceInfo();
    var deviceInfo = {
      device_id: config.deviceId,
      name: device.model + " (" + device.brand + ")",
      os_version: device.release,
      app_version: "1.0.0",
    };
    for (var k in extraInfo) {
      if (extraInfo.hasOwnProperty(k)) {
        deviceInfo[k] = extraInfo[k];
      }
    }
    var regResult = apiClient.register(deviceInfo);
    if (regResult) {
      logger.info(TAG, "设备已注册: " + regResult.device_id);
      applyServerConfig(regResult.config);
    } else {
      logger.warn(TAG, "设备注册失败，继续运行");
    }
  } catch (e) {
    logger.warn(TAG, "注册出错: " + e.message);
  }

  // 一次性 poll 捕获离线期间的任务
  catchUpPoll();

  // 心跳定时器
  heartbeatTimer = setInterval(function () {
    try {
      apiClient.heartbeat();
    } catch (e) {
      logger.warn(TAG, "心跳失败: " + e.message);
    }
  }, config.heartbeatInterval);

  /**
   * catch-up poll — 捕获离线期间积累的任务
   */
  function catchUpPoll() {
    try {
      var response = apiClient.poll();
      if (!response) return;

      applyPollSideData(response);

      if (response.cancelled_task_id) {
        logger.info(TAG, "catch-up: 服务端取消任务: " + response.cancelled_task_id);
        taskExecutor.cancel(response.cancelled_task_id);
      }

      if (response.task) {
        logger.info(TAG, "catch-up: 发现待执行任务: " + response.task.id);
        handleTask(response.task);
      }
    } catch (e) {
      logger.warn(TAG, "catch-up poll 失败: " + e.message);
    }
  }

  logger.info(TAG, "等待任务推送...");
  _startIdlePoll();
}

// 空闲时定时 poll — 即使 WS 通知丢失也能发现待执行任务
// 轮询间隔使用服务端配置，首次默认 30s
// 放在全局作用域，applyServerConfig 可调 _startIdlePoll() 重启轮询
var _mainLoopRuntime = global.__mainLoopRuntime || { isIdle: null, catchUpPoll: null };
global.__mainLoopRuntime = _mainLoopRuntime;
var _idleTicks = 0;
var _idlePollTimer = null;

function _startIdlePoll() {
  if (_idlePollTimer) clearInterval(_idlePollTimer);
  _idlePollTimer = setInterval(function () {
    if (!_mainLoopRuntime.isIdle || !_mainLoopRuntime.catchUpPoll) return;
    if (_mainLoopRuntime.isIdle()) {
      _mainLoopRuntime.catchUpPoll();
      if (_mainLoopRuntime.isIdle()) {
        _idleTicks++;
        // 连续 6 轮空闲才关抖音（避免短暂空闲反复开关）
        if (_idleTicks >= 6) {
          logger.info(TAG, "空闲超过 " + _idleTicks + " 轮，关闭抖音");
          try { require("./core/ui-operator").closeApp(); } catch (e) {}
          _idleTicks = 0;
        }
      } else {
        _idleTicks = 0;
      }
    }
  }, config.pollInterval || 30000);
}

/**
 * 应用服务端下发的配置
 * @param {Object} serverConfig - 服务端返回的 config 对象
 */
function applyServerConfig(serverConfig) {
  if (!serverConfig) return;

  if (serverConfig.poll_interval !== undefined) {
    var changed = config.pollInterval !== serverConfig.poll_interval;
    config.pollInterval = serverConfig.poll_interval;
    if (changed) _startIdlePoll();  // 重启空闲轮询以使用新间隔
  }
  if (serverConfig.heartbeat_interval !== undefined) config.heartbeatInterval = serverConfig.heartbeat_interval;
  if (serverConfig.log_level !== undefined) config.logLevel = serverConfig.log_level;

  if (serverConfig.anti_detect_config) {
    antiDetect.updateFromServer(serverConfig.anti_detect_config);
  }
  if (serverConfig.anti_detect_config_version !== undefined) {
    config.antiDetectVersion = serverConfig.anti_detect_config_version;
  }

  if (serverConfig.ai_config) {
    config.ai.apiKey = serverConfig.ai_config.api_key || config.ai.apiKey;
    config.ai.apiUrl = serverConfig.ai_config.api_url || config.ai.apiUrl;
    config.ai.model = serverConfig.ai_config.model || config.ai.model;
  }

  logger.info(TAG, "服务端配置已应用: 轮询=" + config.pollInterval +
    "ms, 心跳=" + config.heartbeatInterval + "ms, 日志=" + config.logLevel);
}

// 启动
(function () {
  try {
    logger.info(TAG, "=== 抖音自动化助手启动 ===");

    // 初始化悬浮窗
    try {
      floatingWindow.init();
    } catch (e) {
      logger.warn(TAG, "悬浮窗初始化失败: " + e.message);
    }

    // 前置申请截图权限（图找图需要）
    try {
      // 并行线程自动点击权限弹窗的"立即开始"按钮
      var permThread = threads.start(function () {
        for (var i = 0; i < 10; i++) {
          sleep(500);
          try {
            var btn = text("立即开始").findOne(2000);
            if (btn) { btn.click(); break; }
          } catch (e) {}
          try {
            var btn2 = text("允许").findOne(2000);
            if (btn2) { btn2.click(); break; }
          } catch (e) {}
          try {
            var btn3 = text("START NOW").findOne(2000);
            if (btn3) { btn3.click(); break; }
          } catch (e) {}
        }
      });

      var granted = images.requestScreenCapture();
      permThread.interrupt();

      if (!granted) {
        logger.warn(TAG, "截图权限被拒绝，图找图功能将不可用");
      } else {
        logger.info(TAG, "截图权限已获取");
      }
    } catch (e) {
      logger.warn(TAG, "截图权限申请异常: " + e.message);
    }

    // 检查是否已配对
    if (pairing.isConfigured()) {
      logger.info(TAG, "设备已配对，直接启动");
      floatingWindow.setStatus("idle");
      global.__paired = true;
      startMainLoop();
    } else {
      logger.info(TAG, "设备未配对，显示配对界面");
      startPairingFlow();
      // 阻塞等待配对完成
      global.__paired = false;
      while (!global.__paired) {
        sleep(500);
      }
    }

    // 保持脚本存活（定时器和 WS 在后台运行）
    while (true) {
      sleep(30000);
    }
  } catch (e) {
    console.error("启动失败: " + e.message + "\n" + e.stack);
    toast("启动失败: " + e.message);
  }
})();
```

## project.json

```json
{
  "name": "抖音自动化助手",
  "packageName": "com.dy.auto",
  "versionName": "1.0.0",
  "versionCode": 1,
  "main": "main.js",
  "ignore": [
    "node_modules",
    ".git",
    "test-*.js",
    "spike/",
    "*.log"
  ]
}
```

## utils\logger.js

```javascript
var config = global.__config || require("../config");

var LOG_LEVELS = { debug: 0, info: 1, warn: 2, error: 3 };
var LOG_LEVEL_NAMES = { debug: "调试", info: "信息", warn: "警告", error: "错误" };

var logger = {
  _level: LOG_LEVELS[config.logLevel] || 0,
  _history: [],       // 日志历史（供悬浮窗显示）
  _maxHistory: 200,   // 最大历史条数
  _listeners: [],     // 日志更新监听器

  _log: function (level, tag, msg) {
    if (LOG_LEVELS[level] >= this._level) {
      var now = new Date();
      var timestamp = now.toLocaleTimeString();
      var levelName = LOG_LEVEL_NAMES[level] || level;
      var prefix = "[" + timestamp + "] [" + levelName + "] [" + tag + "]";
      var fullMsg = prefix + " " + msg;

      console.log(fullMsg);

      // 保存到历史
      this._history.push({
        time: timestamp,
        level: level,
        levelName: levelName,
        tag: tag,
        message: msg,
        full: fullMsg,
      });

      // 限制历史长度
      if (this._history.length > this._maxHistory) {
        this._history.shift();
      }

      // 通知监听器
      for (var i = 0; i < this._listeners.length; i++) {
        try {
          this._listeners[i](level, tag, msg);
        } catch (e) {
          // 忽略监听器错误
        }
      }
    }
  },

  debug: function (tag, msg) { this._log("debug", tag, msg); },
  info: function (tag, msg) { this._log("info", tag, msg); },
  warn: function (tag, msg) { this._log("warn", tag, msg); },
  error: function (tag, msg) { this._log("error", tag, msg); },

  /**
   * 获取日志历史
   * @param {number} count - 获取最近 N 条
   * @returns {Array}
   */
  getHistory: function (count) {
    count = count || 50;
    return this._history.slice(-count);
  },

  /**
   * 添加日志监听器
   * @param {Function} callback - function(level, tag, msg)
   */
  addListener: function (callback) {
    this._listeners.push(callback);
  },

  /**
   * 移除日志监听器
   * @param {Function} callback
   */
  removeListener: function (callback) {
    var idx = this._listeners.indexOf(callback);
    if (idx !== -1) {
      this._listeners.splice(idx, 1);
    }
  },

  /**
   * 清空日志历史
   */
  clearHistory: function () {
    this._history = [];
  },
};

module.exports = logger;
```

## utils\bezier.js

```javascript
/**
 * 贝塞尔曲线计算 — 用于生成拟人滑动轨迹
 */

function factorial(n) {
  var result = 1;
  for (var i = 2; i <= n; i++) result *= i;
  return result;
}

function bernstein(t, i, n) {
  return (
    (factorial(n) / (factorial(i) * factorial(n - i))) *
    Math.pow(t, i) *
    Math.pow(1 - t, n - i)
  );
}

/**
 * 计算贝塞尔曲线上的点
 * @param {Array} controlPoints - 控制点数组 [{x, y}, ...]
 * @param {number} t - 参数 (0-1)
 * @returns {{x: number, y: number}}
 */
function bezierPoint(controlPoints, t) {
  var n = controlPoints.length - 1;
  var x = 0, y = 0;
  for (var i = 0; i <= n; i++) {
    var b = bernstein(t, i, n);
    x += controlPoints[i].x * b;
    y += controlPoints[i].y * b;
  }
  return { x: Math.round(x), y: Math.round(y) };
}

/**
 * 生成拟人滑动轨迹
 * @param {number} startX - 起点 X
 * @param {number} startY - 起点 Y
 * @param {number} endX - 终点 X
 * @param {number} endY - 终点 Y
 * @param {number} steps - 轨迹点数 (默认 10-20 之间的随机值)
 * @returns {Array} 轨迹点数组 [{x, y, duration}, ...]
 */
function generateSwipePath(startX, startY, endX, endY, steps) {
  steps = steps || (Math.floor(Math.random() * 11) + 10); // 10-20

  // 生成 2 个随机中间控制点，模拟手指不走直线
  var midX1 = startX + (endX - startX) * 0.3 + (Math.random() - 0.5) * 50;
  var midY1 = startY + (endY - startY) * 0.3 + (Math.random() - 0.5) * 50;
  var midX2 = startX + (endX - startX) * 0.7 + (Math.random() - 0.5) * 50;
  var midY2 = startY + (endY - startY) * 0.7 + (Math.random() - 0.5) * 50;

  var controlPoints = [
    { x: startX, y: startY },
    { x: midX1, y: midY1 },
    { x: midX2, y: midY2 },
    { x: endX, y: endY },
  ];

  var path = [];
  for (var i = 0; i <= steps; i++) {
    var t = i / steps;
    var point = bezierPoint(controlPoints, t);
    // 变速：中间快两头慢
    var duration = Math.round(10 + 20 * Math.sin(t * Math.PI));
    path.push({ x: point.x, y: point.y, duration: duration });
  }
  return path;
}

module.exports = {
  generateSwipePath: generateSwipePath,
  bezierPoint: bezierPoint,
};
```

## core\crash-recovery.js

```javascript
var logger = require("../utils/logger");

var TAG = "RECOVERY";

var crashRecovery = {
  _consecutiveFailures: 0,
  _maxConsecutiveFailures: 5,

  /**
   * 设置当前执行的账号 ID（由 task-executor 调用）
   */
  setAccountId: function (accountId) {
    this._currentAccountId = accountId;
  },

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
      "知道了", "确定", "关闭", "重试",
      "允许", "暂不", "稍后再说", "下次再说",
    ];

    for (var i = 0; i < dialogButtons.length; i++) {
      try {
        var btn = text(dialogButtons[i]).findOne(2000);
        if (btn) {
          logger.info(TAG, "Found dialog button: " + dialogButtons[i]);
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
```

## core\floating-window.js

```javascript
// device/core/floating-window.js
// 悬浮窗模块 — 提供日志查看、配对界面和快捷操作入口 (极光美化版)

var logger = require("../utils/logger");

var TAG = "悬浮窗";

var _classesImported = false;
function ensureClasses() {
  if (_classesImported) return;
  importClass(android.animation.ValueAnimator);
  importClass(android.animation.ObjectAnimator);
  importClass(android.animation.AnimatorSet);
  importClass(android.view.animation.BounceInterpolator);
  importClass(android.view.animation.DecelerateInterpolator);
  importClass(android.graphics.drawable.GradientDrawable);
  importClass(android.graphics.Color);
  _classesImported = true;
}

// dp → px
function dpToPx(dp) {
  return Math.round(dp * device.density / 160);
}

// 尺寸配置（微调了尺寸比例，留出阴影空间）
var ROOT_DP = 64;       // 悬浮窗根容器大小（透明，用于装载阴影）
var BALL_DP = 46;       // 悬浮球实体直径
var MARGIN_DP = 8;      // 距屏幕边缘距离

var floatingWindow = {
  _window: null,
  _logWindow: null,
  _pairWindow: null,
  _isLogVisible: false,
  _onPairConnect: null,
  _mode: "main",
  _screenW: 0,
  _screenH: 0,
  _rootPx: 0,
  _ballPx: 0,

  init: function () {
    var self = this;
    ensureClasses();
    this._screenW = device.width;
    this._screenH = device.height;

    this._rootPx = dpToPx(ROOT_DP);
    this._ballPx = dpToPx(BALL_DP);
    var marginPx = dpToPx(MARGIN_DP);

    try {
      if (!floaty.checkPermission()) {
        logger.info(TAG, "请求悬浮窗权限...");
        floaty.requestPermission();
        sleep(1000);
      }
    } catch (e) {
      logger.info(TAG, "跳过权限检查: " + e.message);
    }

    // ==========================================
    // 美化重点 1：采用 CardView 打造真实物理阴影
    // ==========================================
    this._window = floaty.rawWindow(
      '<frame id="root" w="' + this._rootPx + 'px" h="' + this._rootPx + 'px" gravity="center" background="#00000000" margin="0" padding="0">' +
        '<card id="ballCard" w="' + this._ballPx + 'px" h="' + this._ballPx + 'px" ' +
          'cardCornerRadius="' + (this._ballPx / 2) + 'px" ' +
          'cardElevation="' + dpToPx(6) + 'px" ' + // 柔和的 6dp 外阴影
          'layout_gravity="center" cardBackgroundColor="#ffffff">' +
          '<frame id="bgFrame" w="*" h="*">' +
            // 使用科技感符号 ✦ 替代普通 emoji
            '<text id="iconText" text="✦" textColor="#FFFFFF" textSize="22sp" textStyle="bold" gravity="center"/>' +
          '</frame>' +
        '</card>' +
      '</frame>'
    );

    // ==========================================
    // 美化重点 2：极光渐变背景色
    // ==========================================
    ui.run(function() {
      try {
        var gd = new GradientDrawable();
        gd.setOrientation(GradientDrawable.Orientation.TL_BR); // 左上到右下
        gd.setShape(GradientDrawable.OVAL);

        // 配色方案：深邃紫罗兰过渡到明亮科技蓝
        var colorArray = util.java.array("int", 2);
        colorArray[0] = Color.parseColor("#8E2DE2");
        colorArray[1] = Color.parseColor("#4A00E0");
        gd.setColors(colorArray);

        self._window.bgFrame.setBackground(gd);
      } catch(e) {
        // 异常降级兜底
        self._window.bgFrame.setBackgroundColor(Color.parseColor("#6366f1"));
      }
    });

    // 初始位置
    this._window.setPosition(
      this._screenW - this._rootPx,
      Math.round(this._screenH * 0.3)
    );

    var downX, downY, windowX, windowY;
    var isMoving = false;

    // 将触摸事件绑定在 root 上，扩大点按判定区
    this._window.root.setOnTouchListener(function (view, event) {
      switch (event.getAction()) {
        case event.ACTION_DOWN:
          downX = event.getRawX();
          downY = event.getRawY();
          windowX = self._window.getX();
          windowY = self._window.getY();
          isMoving = false;
          self._playPressAnimation(true);
          return true;

        case event.ACTION_MOVE:
          var dx = event.getRawX() - downX;
          var dy = event.getRawY() - downY;
          if (!isMoving && Math.abs(dx) < dpToPx(5) && Math.abs(dy) < dpToPx(5)) {
            return true;
          }
          isMoving = true;
          self._window.setPosition(windowX + dx, windowY + dy);
          return true;

        case event.ACTION_UP:
          self._playPressAnimation(false);
          if (!isMoving) {
            self._playClickAnimation();
            self._onButtonClick();
          } else {
            self._handleAdsorption();
          }
          return true;
      }
      return true;
    });

    ui.run(function () {
      setTimeout(function () { self._playEnterAnimation(); }, 100);
    });

    logger.info(TAG, "悬浮窗(美化版)已创建");
  },

  _handleAdsorption: function () {
    var currentX = this._window.getX();
    var currentY = this._window.getY();
    var marginPx = dpToPx(MARGIN_DP);
    // 抵消阴影容器带来的位置偏移，让悬浮球实体贴边
    var shadowOffset = (this._rootPx - this._ballPx) / 2;
    var midX = currentX + this._rootPx / 2;

    var targetX;
    if (midX < this._screenW / 2) {
      targetX = -shadowOffset + marginPx;
    } else {
      targetX = this._screenW - this._rootPx + shadowOffset - marginPx;
    }

    var targetY = currentY;
    var maxY = this._screenH - this._rootPx;
    if (targetY < marginPx) targetY = marginPx;
    if (targetY > maxY - marginPx) targetY = maxY - marginPx;

    this._playEdgeBounce(currentX, currentY, targetX, targetY);
  },

  _playEdgeBounce: function (startX, startY, endX, endY) {
    var win = this._window;
    var animator = ValueAnimator.ofFloat(0, 1);
    animator.setDuration(700); // 略微加快回弹，显得更轻盈
    animator.setInterpolator(new BounceInterpolator());
    animator.addUpdateListener(function (animation) {
      var f = animation.getAnimatedValue();
      var cx = startX + (endX - startX) * f;
      var cy = startY + (endY - startY) * f;
      ui.run(function () {
        try { win.setPosition(cx, cy); } catch (e) { }
      });
    });
    ui.run(function () { animator.start(); });
  },

  _playPressAnimation: function (isPressed) {
    if (!this._window) return;
    var scale = isPressed ? 0.88 : 1.0;
    var card = this._window.ballCard; // 仅缩放球体，不缩放 root
    var ax = ObjectAnimator.ofFloat(card, "scaleX", scale);
    var ay = ObjectAnimator.ofFloat(card, "scaleY", scale);
    var set = new AnimatorSet();
    set.playTogether(ax, ay);
    set.setDuration(120);
    set.setInterpolator(new DecelerateInterpolator());
    ui.run(function () { set.start(); });
  },

  _playEnterAnimation: function () {
    if (!this._window) return;
    var card = this._window.ballCard;
    var sx = ObjectAnimator.ofFloat(card, "scaleX", 0, 1.15, 1);
    var sy = ObjectAnimator.ofFloat(card, "scaleY", 0, 1.15, 1);
    var alpha = ObjectAnimator.ofFloat(card, "alpha", 0, 1);
    var set = new AnimatorSet();
    set.playTogether(sx, sy, alpha);
    set.setDuration(600);
    set.start();
  },

  _playClickAnimation: function () {
    if (!this._window) return;
    var card = this._window.ballCard;
    var sx = ObjectAnimator.ofFloat(card, "scaleX", 1, 0.8, 1);
    var sy = ObjectAnimator.ofFloat(card, "scaleY", 1, 0.8, 1);
    var set = new AnimatorSet();
    set.playTogether(sx, sy);
    set.setDuration(250);
    set.start();
  },

  _onButtonClick: function () {
    if (this._isLogVisible) {
      this._hideLogWindow();
    } else {
      this._showLogWindow();
    }
  },

  /* ------------ 往下为日志及配对窗口逻辑，保持你的原样 ------------ */

  _showLogWindow: function () {
    var self = this;
    if (this._logWindow) {
      var logMargin = dpToPx(12);
      this._logWindow.setPosition(logMargin, dpToPx(120));
      this._logWindow.setSize(device.width - logMargin * 2, Math.round(device.height * 0.5));
      return;
    }

    this._logWindow = floaty.window(
      '<vertical bg="#ee000000" padding="8" cornerRadius="8">' +
        '<horizontal marginBottom="4">' +
          '<text text="运行日志" textSize="16" textColor="#00ff00" layout_weight="1"/>' +
          '<text id="btnClear" text="清除" textSize="12" textColor="#ffff00" padding="4" margin="4"/>' +
          '<text id="btnStop" text="停止" textSize="12" textColor="#ff4444" padding="4" margin="4"/>' +
          '<text id="btnClose" text="关闭" textSize="12" textColor="#ff6666" padding="4" margin="4"/>' +
        '</horizontal>' +
        '<list id="logList" layout_weight="1" h="*">' +
          '<vertical padding="2">' +
            '<text text="{{this.full}}" textSize="11" textColor="{{this.color}}" maxLines="2" ellipsize="end"/>' +
          '</vertical>' +
        '</list>' +
      '</vertical>'
    );

    var logMargin = dpToPx(12);
    var logTop = dpToPx(120);
    this._logWindow.setPosition(logMargin, logTop);
    this._logWindow.setSize(device.width - logMargin * 2, Math.round(device.height * 0.5));

    var logData = [];
    this._logWindow.logList.setDataSource(logData);

    var history = logger.getHistory(100);
    for (var i = 0; i < history.length; i++) {
      logData.push({
        full: history[i].full,
        color: this._getLogColor(history[i].level),
      });
    }

    this._logListener = function (level, tag, msg) {
      if (self._logWindow) {
        var now = new Date().toLocaleTimeString();
        var levelName = { debug: "调试", info: "信息", warn: "警告", error: "错误" }[level] || level;
        var full = "[" + now + "] [" + levelName + "] [" + tag + "] " + msg;

        ui.run(function () {
          try {
            if (!self._logWindow) return;
            logData.push({
              full: full,
              color: self._getLogColor(level),
            });
            if (logData.length > 100) {
              logData.shift();
            }
            self._logWindow.logList.scrollToPosition(logData.length - 1);
          } catch (e) { }
        });
      }
    };
    logger.addListener(this._logListener);

    this._logWindow.btnStop.on("click", function () {
      dialogs.confirm("确认", "确定要停止进程吗？", function (ok) {
        if (ok) {
          logger.info(TAG, "用户手动停止进程");
          self.destroy();
          exit();
        }
      });
    });

    this._logWindow.btnClose.on("click", function () {
      self._hideLogWindow();
    });

    this._logWindow.btnClear.on("click", function () {
      logger.clearHistory();
      logData.length = 0;
      self._logWindow.logList.setDataSource(logData);
    });

    this._isLogVisible = true;
  },

  _hideLogWindow: function () {
    if (this._logWindow) {
      if (this._logListener) {
        logger.removeListener(this._logListener);
        this._logListener = null;
      }
      this._logWindow.close();
      this._logWindow = null;
      this._isLogVisible = false;
    }
  },

  _getLogColor: function (level) {
    switch (level) {
      case "error": return "#ff4444";
      case "warn": return "#ffaa00";
      case "info": return "#44ff44";
      case "debug": return "#888888";
      default: return "#ffffff";
    }
  },

  setStatus: function (status) {
    if (!this._window) return;
    // 美化版的图标指示器
    var icons = {
      idle: "✦",      // 待机魔法星
      running: "◎",   // 运行中的动感圆环
      error: "✕",     // 清爽的叉号
      success: "✓",   // 清爽的勾号
    };
    var icon = icons[status] || icons.idle;
    var self = this;
    ui.run(function () {
      try {
        if (self._window) self._window.iconText.setText(icon);
      } catch (e) { }
    });
  },

  showToast: function (msg, duration) {
    duration = duration || 3000;
    toast(msg);
  },

  showPairingUI: function (callback) {
    var self = this;
    this._mode = "pair";
    this._onPairConnect = callback;
    this._hideLogWindow();

    if (this._window) {
      this._window.setPosition(dpToPx(MARGIN_DP), this._screenH - this._rootPx - dpToPx(80));
    }

    if (this._pairWindow) {
      this._pairWindow.close();
      this._pairWindow = null;
    }

    this._pairWindow = floaty.window(
      '<card w="280" cardCornerRadius="20" cardBackgroundColor="#ffffff" cardElevation="16" margin="0">' +
        '<vertical>' +
          '<vertical bg="#6366f1" padding="20 24 20 20">' +
            '<text text="📱" textSize="28" gravity="center"/>' +
            '<text text="设备配对" textSize="18" textColor="#ffffff" gravity="center" textStyle="bold" marginTop="8"/>' +
            '<text text="连接到自动化控制台" textSize="12" textColor="#c7d2fe" gravity="center" marginTop="4"/>' +
          '</vertical>' +
          '<vertical padding="24 20 20 20">' +
            '<text text="输入服务端 IP 地址以完成配对" textSize="13" textColor="#6b7280" gravity="center" marginBottom="16"/>' +
            '<button id="btnConnect" text="🔗  输入服务端 IP" textSize="15" textColor="#ffffff" ' +
              'bg="#6366f1" h="48" w="*" cornerRadius="12"/>' +
            '<text id="statusText" text="" textSize="12" textColor="#f59e0b" gravity="center" marginTop="14"/>' +
          '</vertical>' +
        '</vertical>' +
      '</card>'
    );

    var pairW = dpToPx(280);
    this._pairWindow.setPosition(
      this._screenW - pairW - dpToPx(5),
      dpToPx(20)
    );

    this._pairWindow.btnConnect.on("click", function () {
      threads.start(function () {
        var ip = dialogs.rawInput("请输入服务端 IP 地址", "192.168.0.112");
        if (!ip) return;
        ip = ip.trim();
        if (!ip) return;
        ui.run(function () {
          self._pairWindow.statusText.setText("正在连接...");
        });
        if (self._onPairConnect) {
          self._onPairConnect(ip);
        }
      });
    });
  },

  updatePairStatus: function (text) {
    if (this._pairWindow && this._pairWindow.statusText) {
      var self = this;
      ui.run(function () {
        try {
          if (self._pairWindow && self._pairWindow.statusText) {
            self._pairWindow.statusText.setText(text);
          }
        } catch (e) { }
      });
    }
  },

  showWaitingUI: function () {
    var self = this;
    this._mode = "waiting";

    if (this._pairWindow) {
      this._pairWindow.close();
      this._pairWindow = null;
    }

    this._pairWindow = floaty.window(
      '<card w="280" cardCornerRadius="20" cardBackgroundColor="#ffffff" cardElevation="16">' +
        '<vertical>' +
          '<frame>' +
            '<vertical bg="#f59e0b" padding="20 24 20 20">' +
              '<text text="⏳" textSize="28" gravity="center"/>' +
              '<text text="等待审批" textSize="18" textColor="#ffffff" gravity="center" textStyle="bold" marginTop="8"/>' +
              '<text text="配令人求已发送" textSize="12" textColor="#fef3c7" gravity="center" marginTop="4"/>' +
            '</vertical>' +
            '<text id="btnWaitingClose" text="✕" textSize="14" textColor="#ffffff" ' +
              'padding="4 8 4 8" layout_gravity="right|top" margin="6"/>' +
          '</frame>' +
          '<vertical padding="24 20 20 20" gravity="center">' +
            '<text text="请在电脑管理端批准此设备" textSize="14" textColor="#374151" gravity="center"/>' +
            '<text text="配对请求等待中..." textSize="13" textColor="#9ca3af" gravity="center" marginTop="6"/>' +
            '<text text="·  ·  ·" textSize="20" textColor="#f59e0b" gravity="center" marginTop="16"/>' +
          '</vertical>' +
        '</vertical>' +
      '</card>'
    );

    this._pairWindow.btnWaitingClose.on("click", function () {
      self.showMainUI();
    });

    var waitW = dpToPx(280);
    this._pairWindow.setPosition(
      this._screenW - waitW - dpToPx(20),
      dpToPx(80)
    );

    this.setStatus("running");
  },

  showMainUI: function () {
    this._mode = "main";
    if (this._pairWindow) {
      this._pairWindow.close();
      this._pairWindow = null;
    }
    if (this._window) {
      this._window.setPosition(
        this._screenW - this._rootPx - dpToPx(MARGIN_DP),
        Math.round(this._screenH * 0.3)
      );
    }
    this.setStatus("idle");
  },

  destroy: function () {
    if (this._logListener) {
      logger.removeListener(this._logListener);
    }
    if (this._logWindow) {
      this._logWindow.close();
      this._logWindow = null;
    }
    if (this._pairWindow) {
      this._pairWindow.close();
      this._pairWindow = null;
    }
    if (this._window) {
      this._window.close();
      this._window = null;
    }
  },
};

module.exports = floatingWindow;
```

## core\api-client.js

```javascript
// 使用 global.__config 确保与 main.js 共享同一 config 对象
// 避免 require("./config") vs require("../config") 路径不一致导致多实例
var config = global.__config || require("../config");
var logger = require("../utils/logger");

var TAG = "网络";
var netConfig = config.network || {
  requestTimeout: 10000,
  maxRetries: 3,
  retryBaseDelay: 2000,
  retryMaxDelay: 30000,
  offlineQueueMax: 100,
};

// 离线队列 — 网络失败时缓存待上报数据
var offlineQueue = [];
var isOnline = true;
var _lastRequestWas4xx = false;  // 4xx = 客户端错误，不应重试

function _ensureDirPath(dir) {
  if (!dir) return false;
  try {
    var f = new java.io.File(String(dir));
    if (!f.exists()) f.mkdirs();
    return f.exists() && f.isDirectory();
  } catch (e) {
    logger.warn(TAG, "目录创建失败: " + dir + " - " + e.message);
    return false;
  }
}

var apiClient = {
  _onAuthFailure: null,
  _lastRequestWas4xx: function () { return _lastRequestWas4xx; },

  /**
   * 设置认证失败回调（401 时触发）
   */
  setAuthFailureHandler: function (callback) {
    this._onAuthFailure = callback;
  },

  /**
   * 应用代理配置到 HTTP 请求
   * @param {Object} proxyConfig - { type, host, port, username, password }
   */
  setProxy: function (proxyConfig) {
    if (!proxyConfig || !proxyConfig.host) {
      logger.info(TAG, "未配置代理");
      config.proxy = null;
      return;
    }

    config.proxy = proxyConfig;
    logger.info(TAG, "代理已配置: " + proxyConfig.type + "://" +
      proxyConfig.host + ":" + proxyConfig.port + " (认证=" + (proxyConfig.username ? "是" : "否") + ")");
  },

  /**
   * 获取当前代理配置的 HTTP 选项
   * @returns {Object} 适合 http.get/http.post 的选项
   */
  _getProxyOptions: function () {
    if (!config.proxy) return {};

    var proxy = config.proxy;
    var proxyUrl = proxy.type + "://" + proxy.host + ":" + proxy.port;
    if (proxy.username) {
      var encUser = encodeURIComponent(proxy.username);
      var encPass = encodeURIComponent(proxy.password || "");
      proxyUrl = proxy.type + "://" + encUser + ":" + encPass +
        "@" + proxy.host + ":" + proxy.port;
    }
    return { proxy: proxyUrl };
  },

  /**
   * 计算重试延迟（指数退避 + 抖动）
   */
  _retryDelay: function (attempt) {
    var base = netConfig.retryBaseDelay * Math.pow(2, attempt);
    var jitter = Math.random() * base * 0.3;
    return Math.min(base + jitter, netConfig.retryMaxDelay);
  },

  /**
   * 通用重试请求
   * @param {string} method - "GET" 或 "POST"
   * @param {string} url - 完整 URL
   * @param {Object} opts - { body, timeout, parseJson, label }
   * @returns {*} 解析后的 JSON 或原始 body，失败返回 null
   */
  /**
   * 读取响应体为字符串（兼容 AutoJS6 的 Java ResponseBody 对象）
   */
  _readBody: function (response) {
    var body = response.body;
    if (typeof body === "string") return body;
    try {
      return body.string();
    } catch (e) {
      return String(body);
    }
  },

  /**
   * 读取响应体为字节数组（用于二进制下载）
   */
  _readBodyBytes: function (response) {
    var body = response.body;
    if (body instanceof Array) return body;
    try {
      return body.bytes();
    } catch (e) {
      try {
        return body.string();
      } catch (e2) {
        return String(body);
      }
    }
  },

  _requestWithRetry: function (method, url, opts) {
    var body = opts.body || null;
    var timeout = opts.timeout || netConfig.requestTimeout;
    var parseJson = opts.parseJson !== false;
    var label = opts.label || method;

    for (var attempt = 0; attempt <= netConfig.maxRetries; attempt++) {
      try {
        var reqOpts = {
          headers: { "X-Device-Secret": config.deviceSecret },
          timeout: timeout,
        };
        // 合并代理配置
        var proxyOpts = this._getProxyOptions();
        for (var pk in proxyOpts) {
          reqOpts[pk] = proxyOpts[pk];
        }

        var response;
        if (method === "POST") {
          response = http.postJson(url, body, reqOpts);
        } else {
          response = http.get(url, reqOpts);
        }

        if (response.statusCode === 200) {
          this._markOnline();
          if (parseJson) {
            return JSON.parse(this._readBody(response));
          }
          return this._readBodyBytes(response);
        }

        if (response.statusCode === 401) {
          logger.error(TAG, label + " 认证失败(401)，设备可能已被删除");
          if (this._onAuthFailure) {
            this._onAuthFailure();
          }
          return null;
        }

        if (response.statusCode >= 400 && response.statusCode < 500) {
          _lastRequestWas4xx = true;
          var respBody = "";
          try { respBody = this._readBody(response); } catch (e2) {}
          logger.error(TAG, label + " 客户端错误: " + response.statusCode +
            (respBody ? " body=" + respBody.substring(0, 200) : ""));
          return null;
        }

        logger.warn(TAG, label + " 服务端错误: " + response.statusCode +
          " (第 " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + " 次尝试)");
      } catch (e) {
        logger.warn(TAG, label + " 网络错误: " + e.message +
          " (第 " + (attempt + 1) + "/" + (netConfig.maxRetries + 1) + " 次尝试)");
      }

      if (attempt < netConfig.maxRetries) {
        var delay = this._retryDelay(attempt);
        logger.debug(TAG, "将在 " + Math.round(delay) + "ms 后重试...");
        sleep(delay);
      }
    }

    this._markOffline();
    logger.error(TAG, label + " 所有重试均失败");
    return null;
  },

  /**
   * 带重试的 HTTP GET
   */
  get: function (path, params) {
    if (!config.serverUrl) {
      logger.error(TAG, "serverUrl 未设置，无法请求: " + path);
      return null;
    }
    var url = config.serverUrl + path;
    if (params) {
      var queryParts = [];
      for (var key in params) {
        queryParts.push(encodeURIComponent(key) + "=" + encodeURIComponent(params[key]));
      }
      url += "?" + queryParts.join("&");
    }
    return this._requestWithRetry("GET", url, { label: "GET " + path });
  },

  /**
   * 带重试的 HTTP POST
   */
  post: function (path, body, timeout) {
    if (!config.serverUrl) {
      logger.error(TAG, "serverUrl 未设置，无法请求: " + path);
      return null;
    }
    var url = config.serverUrl + path;
    return this._requestWithRetry("POST", url, { body: body, label: "POST " + path, timeout: timeout });
  },

  /**
   * 带重试的二进制下载
   */
  _downloadWithRetry: function (url) {
    return this._requestWithRetry("GET", url, {
      timeout: 60000,
      parseJson: false,
      label: "Download",
    });
  },

  /**
   * 标记网络恢复，刷新离线队列
   */
  _markOnline: function () {
    if (!isOnline) {
      logger.info(TAG, "网络已恢复，刷新离线队列 (" +
        offlineQueue.length + " 条)");
      isOnline = true;
      this._flushOfflineQueue();
    }
  },

  /**
   * 标记网络离线
   */
  _markOffline: function () {
    if (isOnline) {
      logger.warn(TAG, "网络已离线");
      isOnline = false;
    }
  },

  /**
   * 刷新离线队列
   */
  _flushOfflineQueue: function () {
    var MAX_FLUSH_RETRIES = 3;
    while (offlineQueue.length > 0) {
      var item = offlineQueue.shift();
      logger.info(TAG, "刷新离线项: " + item.path);
      var result = this.post(item.path, item.body);
      if (!result) {
        item.retries = (item.retries || 0) + 1;
        if (item.retries >= MAX_FLUSH_RETRIES) {
          logger.error(TAG, "离线项 " + MAX_FLUSH_RETRIES + " 次重试后丢弃: " + item.path);
        } else {
          offlineQueue.unshift(item);
        }
        break;
      }
    }
  },

  // --- 业务方法 ---

  poll: function () {
    return this.get("/api/device/poll", { device_id: config.deviceId });
  },

  fetchDMSequences: function () {
    return this.get("/api/dm-sequences/device/sync");
  },

  fetchTemplateList: function (resolution) {
    var path = "/api/device/templates";
    if (resolution) path += "?resolution=" + encodeURIComponent(resolution);
    return this.get(path);
  },

  uploadCalibration: function (templates, resolution) {
    var body = {
      templates: templates.map(function (t) {
        return {
          action_name: t.action_name,
          filename: t.filename,
          data: android.util.Base64.encodeToString(t.data, 0),  // base64 for JSON
          resolution: resolution,
        };
      }),
      resolution: resolution,
    };
    return this.post("/api/device/calibrate", body);
  },

  downloadTemplate: function (filename) {
    var url = config.serverUrl + "/api/device/templates/" + encodeURIComponent(filename);
    return this._downloadWithRetry(url);
  },

  _pushToOfflineQueue: function (path, body, label) {
    if (offlineQueue.length >= netConfig.offlineQueueMax) {
      logger.warn(TAG, "离线队列已满，丢弃最旧项");
      offlineQueue.shift();
    }
    logger.info(TAG, label + "加入离线队列");
    offlineQueue.push({ path: path, body: body, retries: 0 });
  },

  report: function (taskId, status, result, uiSnapshot) {
    _lastRequestWas4xx = false;
    var body = {
      task_id: taskId,
      status: status,
      result: result || {},
      ui_snapshot: uiSnapshot || null,
    };
    var response = this.post("/api/device/report", body);
    if (!response && !_lastRequestWas4xx) {
      logger.warn(TAG, "任务结果上报失败(status=" + status + ")，加入离线队列重试");
      this._pushToOfflineQueue("/api/device/report", body, "任务结果");
    }
    return response;
  },

  collectReport: function (payload) {
    _lastRequestWas4xx = false;
    var response = this.post("/api/device/collect-report", payload);
    if (!response && !_lastRequestWas4xx) this._pushToOfflineQueue("/api/device/collect-report", payload, "采集数据");
    return response;
  },

  heartbeat: function () {
    return this.post("/api/device/heartbeat", { device_id: config.deviceId });
  },

  reportProgress: function (taskId, step, detail, progress) {
    return this.post("/api/device/progress", {
      task_id: taskId,
      step: step || "",
      detail: detail || "",
      progress: progress || 0,
    });
  },

  fetchSelectors: function (currentVersion) {
    return this.get("/api/device/selectors", { version: currentVersion || 0 });
  },

  fetchPromptTemplates: function (currentVersion) {
    return this.get("/api/device/prompt-templates", { version: currentVersion || 0 });
  },

  getScriptVersion: function () {
    var result = this.get("/api/device/script-version");
    return result ? result.version : null;
  },

  downloadScript: function () {
    var url = config.serverUrl + "/api/device/script-download";
    var body = this._downloadWithRetry(url);
    if (!body) {
      logger.error(TAG, "脚本下载所有重试均失败");
      return false;
    }
    logger.info(TAG, "脚本下载成功, size=" + body.length);
    // 用 Java FileOutputStream 直接写，绕过 AutoJS files API 的 byte array bug
    var baseDir = null;
    try { baseDir = context.getFilesDir().getAbsolutePath(); } catch (e) {}
    if (!baseDir) { try { baseDir = context.getExternalFilesDir(null).getAbsolutePath(); } catch (e2) {} }
    if (!baseDir) { baseDir = files.cwd(); }
    var updateDir = baseDir + "/update";
    var zipPath = updateDir + "/device-script.zip";
    var wrote = false;
    for (var attempt = 0; attempt < 3; attempt++) {
      var fos = null;
      try {
        if (!_ensureDirPath(updateDir)) { sleep(300); continue; }
        fos = new java.io.FileOutputStream(zipPath);
        fos.write(body);
        fos.close();
        fos = null;
        if (files.exists(zipPath)) { wrote = true; break; }
        sleep(200);
      } catch (e) {
        logger.warn(TAG, "写入更新包失败(尝试" + (attempt + 1) + "/3): " + e.message);
        sleep(500);
      } finally {
        try { if (fos) fos.close(); } catch (e2) {}
      }
    }
    if (!wrote) {
      logger.error(TAG, "无法写入更新包到: " + zipPath);
      return false;
    }
    logger.info(TAG, "脚本已下载: " + zipPath + " (" + body.length + " bytes)");
    return true;
  },

  register: function (deviceInfo) {
    return this.post("/api/device/register", deviceInfo);
  },

  /**
   * 上报风控检测结果
   * @param {string} accountId - 账号 ID
   * @param {string} riskType - 风控类型 (captcha, risk_control, verify)
   * @param {Object} detail - 风控详情
   */
  claimCommentReply: function (author, text) {
    return this.post("/api/device/comment-claim-reply", {
      author: author,
      text: text,
    });
  },

  releaseCommentReply: function (author, text) {
    return this.post("/api/device/comment-claim-release", {
      author: author,
      text: text,
    });
  },

  reportRiskControl: function (accountId, riskType, detail) {
    return this.post("/api/device/risk-report", {
      account_id: accountId,
      risk_type: riskType,
      detail: detail || {},
      device_id: config.deviceId,
      timestamp: new Date().toISOString(),
    });
  },

  isOnline: function () {
    return isOnline;
  },

  getOfflineQueueSize: function () {
    return offlineQueue.length;
  },

  // --- DM conversation ---

  claimDMRecipient: function (data) {
    return this.post("/api/device/dm-claim-recipient", data);
  },

  reportDMSend: function (data) {
    return this.post("/api/device/dm-send-report", data);
  },

  releaseDMRecipient: function (data) {
    return this.post("/api/device/dm-release-recipient", data);
  },

  saveCommentAIReply: function (nickname, text, aiReply, taskId, intendedProvince, intendedCity, intendedAttraction) {
    var data = {
      nickname: nickname, text: text, ai_reply: aiReply, task_id: taskId || null,
    };
    if (intendedProvince != null) data.intended_province = intendedProvince;
    if (intendedCity != null) data.intended_city = intendedCity;
    if (intendedAttraction != null) data.intended_attraction = intendedAttraction;
    return this.post("/api/device/comment-ai-reply", data);
  },

  saveUserProfile: function (data) {
    var payload = {
      nickname: data.nickname,
      douyin_id: data.douyin_id || "",
      fans_count: data.fans_count || "",
      likes_count: data.likes_count || "",
      follow_count: data.follow_count || "",
      works_count: data.works_count || "",
      gender: data.gender || "",
      age: data.age || "",
      ip_location: data.ip_location || "",
      is_private: data.is_private || "",
      keyword: data._keyword || "",
      task_id: data._taskId || "",
    };
    if (data._intended_province) payload.intended_province = data._intended_province;
    if (data._intended_city) payload.intended_city = data._intended_city;
    if (data._intended_attraction) payload.intended_attraction = data._intended_attraction;
    return this.post("/api/device/user-profile", payload);
  },

  uploadUserAvatar: function (douyinId, imageBase64) {
    return this.post("/api/device/user-avatar", { douyin_id: douyinId, image_base64: imageBase64 });
  },

  /**
   * 增量统计上报——每完成一个子操作（回复/关注/私信）调用一次
   * 保证任务中途崩溃时已完成操作的统计数据不丢失
   * @param {string} accountId
   * @param {string} taskType — "reply_comment" | "follow" | "search_dm" | ...
   * @param {number} count — 操作次数，默认 1
   */
  incrementStats: function (accountId, taskType, count) {
    var body = { account_id: accountId, task_type: taskType, count: count || 1 };
    var resp = this.post("/api/device/stats/increment", body);
    if (!resp) {
      logger.debug(TAG, "增量统计上报失败: " + taskType + " x" + (count || 1));
    }
    return resp;
  },
};

module.exports = apiClient;
```

## core\update-checker.js

```javascript
var apiClient = require("./api-client");
var logger = require("../utils/logger");

var TAG = "UPDATE";

function ensureDirPath(dir) {
  if (!dir) return false;
  try {
    var f = new java.io.File(String(dir));
    if (!f.exists()) f.mkdirs();
    return f.exists() && f.isDirectory();
  } catch (e) {
    logger.warn(TAG, "Failed to create directory: " + dir + " - " + e.message);
    return false;
  }
}

var updateChecker = {
  _getBaseDir: function () {
    try { return context.getFilesDir().getAbsolutePath(); } catch (e) {}
    try { return context.getExternalFilesDir(null).getAbsolutePath(); } catch (e2) {}
    return files.cwd();
  },

  _versionFile: function () {
    return this._getBaseDir() + "/update/local_version.txt";
  },

  getLocalVersion: function () {
    try {
      var vf = this._versionFile();
      if (files.exists(vf)) {
        return files.read(vf).trim();
      }
    } catch (e) {
      logger.warn(TAG, "Failed to read local version: " + e.message);
    }
    return "0.0.0";
  },

  saveLocalVersion: function (version) {
    try {
      var vf = this._versionFile();
      ensureDirPath(files.path(vf).getParent());
      files.write(vf, version);
    } catch (e) {
      logger.warn(TAG, "Failed to save local version: " + e.message);
    }
  },

  checkAndUpdate: function () {
    logger.info(TAG, "Checking for script updates...");

    var localVersion = this.getLocalVersion();
    var serverVersion = apiClient.getScriptVersion();

    if (!serverVersion) {
      logger.warn(TAG, "Could not get server version, skipping update check");
      return false;
    }

    logger.info(TAG, "Local: " + localVersion + ", Server: " + serverVersion);

    if (localVersion === serverVersion) {
      logger.info(TAG, "Already up to date");
      return false;
    }

    logger.info(TAG, "New version available, downloading...");
    var downloaded = apiClient.downloadScript();

    if (!downloaded) {
      logger.error(TAG, "Download failed, continuing with current version");
      return false;
    }

    try {
      var baseDir = this._getBaseDir();
      var updateDir = baseDir + "/update";
      var zipPath = updateDir + "/device-script.zip";
      var tempDir = updateDir + "/temp";

      if (!files.exists(zipPath)) {
        logger.error(TAG, "Download reported success but zip not found: " + zipPath);
        return false;
      }

      ensureDirPath(tempDir);

      $zip.extract(zipPath, tempDir);

      // 验证关键文件存在
      var criticalFiles = ["main.js", "config.js"];
      for (var i = 0; i < criticalFiles.length; i++) {
        if (!files.exists(tempDir + "/" + criticalFiles[i])) {
          logger.error(TAG, "Update validation failed: missing " + criticalFiles[i]);
          files.removeDir(tempDir);
          files.remove(zipPath);
          return false;
        }
      }

      var projectDir = files.cwd();
      this._copyDir(tempDir, projectDir);

      this.saveLocalVersion(serverVersion);

      files.removeDir(tempDir);
      files.remove(zipPath);

      logger.info(TAG, "Update complete! New version: " + serverVersion);
      return true;
    } catch (e) {
      logger.error(TAG, "Update failed: " + e.message);
      try { files.removeDir(tempDir); } catch (ignore) {}
      return false;
    }
  },

  _copyDir: function (src, dst) {
    var srcPath = files.path(src);
    var items = files.listDir(srcPath);
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var srcFile = src + "/" + item;
      var dstFile = dst + "/" + item;
      if (files.isDir(srcFile)) {
        ensureDirPath(dstFile);
        this._copyDir(srcFile, dstFile);
      } else {
        ensureDirPath(files.path(dstFile).getParent());
        files.copy(srcFile, dstFile);
      }
    }
  },
};

module.exports = updateChecker;
```

## core\selector-loader.js

```javascript
var apiClient = require("./api-client");
var logger = require("../utils/logger");

var TAG = "选择器";

function ensureDirPath(dir) {
  if (!dir) return false;
  try {
    var f = new java.io.File(String(dir));
    if (!f.exists()) f.mkdirs();
    return f.exists() && f.isDirectory();
  } catch (e) {
    logger.warn(TAG, "目录创建失败: " + dir + " - " + e.message);
    return false;
  }
}

// 使用 global 确保所有 require 路径拿到同一个实例（和 config 一样的模式）
var selectorLoader = global.__selectorLoader || {

  _cache: {},       // action_name -> selector config
  _retriedActions: {},  // action_name -> bool, 每个 action 独立重试
  _version: 0,      // 本地缓存版本号
  _initialized: false,
  _resolution: "",  // 当前设备分辨率，init 时捕获

  /**
   * 初始化 — 从后端拉取全量选择器（带重试）
   */
  init: function () {
    // 第一时间捕获设备分辨率，后续 syncTemplates 等依赖
    this._resolution = device.width + "x" + device.height;
    var maxRetries = 3;
    for (var attempt = 1; attempt <= maxRetries; attempt++) {
      logger.info(TAG, "从服务端加载选择器 (尝试 " + attempt + "/" + maxRetries + ")...");
      try {
        var response = apiClient.fetchSelectors(0);
        // 如果返回的是字符串，先解析成对象
        if (typeof response === 'string') {
            try {
                response = JSON.parse(response);
            } catch (parseErr) {
                logger.error(TAG, "JSON解析失败: " + parseErr.message);
            }
        }
        if (response && response.selectors) {
          this._applySelectors(response.selectors);
          this._version = response.version;
          this._initialized = true;
          logger.info(TAG, "已加载 " + Object.keys(this._cache).length + " 个选择器, 版本=" + this._version);
          this.syncTemplates();
          // 检查是否需要为新分辨率设备标定 image 模板
          var needCalibration = false;
          var hasImageSelector = false;
          var hasExactMatch = false;
          for (var actionName in this._cache) {
            var sel = this._cache[actionName];
            if (!sel || !sel.strategies) continue;
            for (var si = 0; si < sel.strategies.length; si++) {
              if (sel.strategies[si].type === "image") {
                hasImageSelector = true;
                break;
              }
            }
            var rp = sel.resolution_profile || "default";
            if (rp === this._resolution) { hasExactMatch = true; }
          }
          // 已有本地模板文件则跳过（避免重复标定）
          var localTplDir = "/sdcard/dy_auto/templates/" + this._resolution + "/";
          var hasLocalTemplates = false;
          try {
            hasLocalTemplates = files.isDir(localTplDir) && files.listDir(localTplDir).length > 0;
          } catch (e) {}
          needCalibration = hasImageSelector && !hasExactMatch && !hasLocalTemplates;
          // 检查关键选择器是否缺失
          var criticalActions = ["search_tab", "video_comment_btn", "comment_list", "follow_button"];
          var missing = [];
          for (var ci = 0; ci < criticalActions.length; ci++) {
            if (!this._cache[criticalActions[ci]]) missing.push(criticalActions[ci]);
          }
          if (needCalibration || missing.length > 0) {
            var reason = needCalibration ? "新分辨率 " + this._resolution + " 缺少 image 模板" : "";
            if (missing.length > 0) reason += (reason ? "; " : "") + "缺少选择器: " + missing.join(",");
            logger.warn(TAG, "触发自动标定: " + reason);
            try {
              var calibrator = require("./calibrator");
              calibrator.run({ unattended: true });
            } catch (e) {
              logger.warn(TAG, "自动标定失败: " + e.message);
            }
          }
          return;
        }
        logger.warn(TAG, "服务端返回空选择器 (尝试 " + attempt + ")");
      } catch (e) {
        logger.warn(TAG, "加载选择器异常 (尝试 " + attempt + "): " + e.message);
      }
      if (attempt < maxRetries) sleep(2000);
    }
    logger.error(TAG, "选择器加载全部失败，任务可能无法执行");
    // 如果选择器数量异常少（< 10），可能是新分辨率设备无匹配 profile
    if (Object.keys(this._cache).length < 10) {
      logger.warn(TAG, "选择器数量异常 (" + Object.keys(this._cache).length + ")，可能需要标定");
    }
    this._initialized = true;
  },

  /**
   * 检查并增量更新选择器
   * @param {number} serverVersion - 服务端版本号
   */
  checkAndUpdate: function (serverVersion) {
    if (serverVersion > this._version) {
      logger.info(TAG, "选择器已过期 (本地=" + this._version + ", 服务端=" + serverVersion + "), 更新中...");
      var response = apiClient.fetchSelectors(this._version);
      if (response && response.changed && response.selectors) {
        this._applySelectors(response.selectors);
        this._version = response.version;
        logger.info(TAG, "选择器已更新至版本 " + this._version);
        this.syncTemplates();
      }
    }
  },

  /**
   * 获取指定操作的选择器配置
   * @param {string} actionName - 操作名称 (如 "like_button")
   * @returns {Object|null} { strategies: [...] }
   */
  get: function (actionName) {
    var selector = this._cache[actionName];
    if (selector) return selector;

    // 未找到 — 每个 action 独立重试一次（可能是初始化时网络异常）
    if (this._initialized && !this._retriedActions[actionName]) {
      this._retriedActions[actionName] = true;
      logger.warn(TAG, "选择器 '" + actionName + "' 未找到，尝试重新加载...");
      try {
        var response = apiClient.fetchSelectors(0);
        if (typeof response === 'string') {
          response = JSON.parse(response);
        }
        if (response && response.selectors) {
          this._applySelectors(response.selectors);
          this._version = response.version;
          logger.info(TAG, "重新加载完成，当前 " + Object.keys(this._cache).length + " 个选择器");
          return this._cache[actionName] || null;
        }
      } catch (e) {
        logger.warn(TAG, "重新加载失败: " + e.message);
      }
    }

    logger.error(TAG, "未找到选择器配置: " + actionName + " (已缓存 " + Object.keys(this._cache).length + " 个)");
    return null;
  },

  /**
   * 应用选择器配置到缓存
   * 同名 action 择优保留：精确匹配当前抖音版本 > default > 其他版本
   * 这样 _cache 每个 action 只存一条，不会膨胀
   * @param {Array} selectors
   */
  _applySelectors: function (selectors) {
    var douyinVersion = this._douyinVersion;
    if (douyinVersion === undefined) {
      try {
        douyinVersion = context.getPackageManager()
          .getPackageInfo("com.ss.android.ugc.aweme", 0).versionName;
      } catch (e) { douyinVersion = ""; }
      this._douyinVersion = douyinVersion;
    }

    // Capture device resolution
    var devRes = this._resolution;
    if (!devRes) {
      devRes = device.width + "x" + device.height;
      this._resolution = devRes;
    }
    var devAR = _aspectTag(devRes);

    function _priority(platformVer) {
      // exact match: 3, specific version (e.g. "38.6.0"): 2, default/empty: 1
      if (platformVer === douyinVersion) return 3;
      if (!platformVer || platformVer === "default") return 1;
      return 2;
    }

    function _resProfileScore(sel) {
      var rp = sel.resolution_profile || "default";
      if (!rp || rp === "default") return 1;
      if (rp === devRes) return 3;
      if (_aspectTag(rp) === devAR) return 2;
      return 0;
    }

    function _versionDist(v1, v2) {
      if (!v1 || !v2 || v1 === "default" || v2 === "default") return 999999999;
      var p1 = String(v1).split("."), p2 = String(v2).split(".");
      var maxLen = Math.max(p1.length, p2.length);
      var dist = 0;
      for (var i = 0; i < maxLen; i++) {
        dist = dist * 1000 + Math.abs((+p1[i] || 0) - (+p2[i] || 0));
      }
      return dist;
    }

    function _versionCompare(v1, v2) {
      var p1 = String(v1 || "").split(".");
      var p2 = String(v2 || "").split(".");
      var maxLen = Math.max(p1.length, p2.length);
      for (var i = 0; i < maxLen; i++) {
        var a = +p1[i] || 0;
        var b = +p2[i] || 0;
        if (a !== b) return a > b ? 1 : -1;
      }
      return 0;
    }

    function _prefersNotFutureVersion(v1, v2, target) {
      var v1Future = _versionCompare(v1, target) > 0;
      var v2Future = _versionCompare(v2, target) > 0;
      if (v1Future !== v2Future) return !v1Future;
      return false;
    }

    function _aspectTag(resolution) {
      if (!resolution) return "unknown";
      var parts = resolution.split("x");
      var w = parseInt(parts[0]) || 0;
      var h = parseInt(parts[1]) || 0;
      if (w === 0 || h === 0) return "unknown";
      var a = w, b = h;
      while (b) { var t = b; b = a % b; a = t; }
      return (w / a) + ":" + (h / a);
    }

    function _isBetter(s, existing) {
      var p = _priority(s.platform_version);
      var ep = _priority(existing.platform_version);
      if (p !== ep) return p > ep;

      // Same platform priority: actual Douyin version proximity wins first.
      // Example: device 38.7.0 should choose selector 38.6.0 over 38.5.0.
      if (p === 2) {
        var sVer = s.platform_version || "";
        var exVer = existing.platform_version || "";
        var sDist = _versionDist(sVer, douyinVersion);
        var exDist = _versionDist(exVer, douyinVersion);
        if (sDist !== exDist) return sDist < exDist;
        if (_prefersNotFutureVersion(sVer, exVer, douyinVersion)) return true;
        if (_prefersNotFutureVersion(exVer, sVer, douyinVersion)) return false;
      }

      // Exact/default platform tie, or equal version distance: prefer resolution fit.
      var rs = _resProfileScore(s);
      var ers = _resProfileScore(existing);
      if (rs !== ers) return rs > ers;
      return false;
    }

    for (var i = 0; i < selectors.length; i++) {
      var s = selectors[i];
      var existing = this._cache[s.action_name];
      if (!existing || _isBetter(s, existing)) {
        this._cache[s.action_name] = s;
      }
    }
    if (this._cache.sort_latest) {
      logger.info(TAG, "sort_latest选择器: 平台=" + (this._cache.sort_latest.platform_version || "default") +
        ", 分辨率=" + (this._cache.sort_latest.resolution_profile || "default") +
        ", 策略=" + JSON.stringify(this._cache.sort_latest.strategies || []));
    }
    logger.info(TAG, "已应用选择器配置，_cache " + Object.keys(this._cache).length + " 个选择器 (抖音 " + douyinVersion + ", 分辨率 " + devRes + ")");
  },

  /**
   * 同步模板图片 — 从服务端下载缺失的模板，清理多余的
   */
  syncTemplates: function () {
    try {
      var response = apiClient.fetchTemplateList(this._resolution);
      if (!response || !response.templates) {
        logger.warn(TAG, "获取模板列表失败");
        return;
      }

      var remoteList = response.templates;
      var baseDir = "/sdcard/dy_auto/templates/";
      ensureDirPath(baseDir);

      // Group remote templates by resolution
      var byResolution = {};
      for (var i = 0; i < remoteList.length; i++) {
        var t = remoteList[i];
        var res = t.resolution || "default";
        if (!byResolution[res]) byResolution[res] = {};
        byResolution[res][t.filename] = t;
      }

      // Sync each resolution group
      var downloaded = 0;
      var cleaned = 0;
      for (var res in byResolution) {
        if (!byResolution.hasOwnProperty(res)) continue;
        var resDir = baseDir + res + "/";
        ensureDirPath(resDir);
        var resFiles = byResolution[res];

        // Download missing templates for this resolution
        for (var fn in resFiles) {
          if (!resFiles.hasOwnProperty(fn)) continue;
          var tpl = resFiles[fn];
          var localPath = resDir + fn;
          if (!files.exists(localPath)) {
            var data = apiClient.downloadTemplate(fn);
            if (data) {
              files.writeBytes(localPath, data);
              downloaded++;
              logger.info(TAG, "模板已下载: " + res + "/" + fn + " (" + data.length + " bytes)");
            } else {
              logger.warn(TAG, "模板下载失败: " + fn);
            }
          }
        }

        // Clean stale local templates for this resolution
        if (files.isDir(resDir)) {
          var localFiles = files.listDir(resDir);
          for (var k = 0; k < localFiles.length; k++) {
            if (!resFiles[localFiles[k]]) {
              try {
                files.remove(resDir + localFiles[k]);
                cleaned++;
                logger.info(TAG, "清理过期模板: " + res + "/" + localFiles[k]);
              } catch (e) {
                logger.warn(TAG, "清理模板失败: " + localFiles[k] + " - " + e.message);
              }
            }
          }
        }
      }

      if (downloaded > 0 || cleaned > 0) {
        logger.info(TAG, "模板同步完成: 下载 " + downloaded + ", 清理 " + cleaned);
      }
    } catch (e) {
      logger.warn(TAG, "模板同步失败: " + e.message);
    }
  },

  /**
   * 获取当前版本号
   */
  getVersion: function () {
    return this._version;
  },
};

global.__selectorLoader = selectorLoader;
module.exports = selectorLoader;
```

## core\prompt-template-loader.js

```javascript
// device/core/prompt-template-loader.js
// 提示词模板同步加载器 — 照 selector-loader.js 模式
var apiClient = require("./api-client");
var logger = require("../utils/logger");

var TAG = "模板";

var promptTemplateLoader = global.__promptTemplateLoader || {

  _cache: {},       // id -> template object { id, name, industry, content }
  _version: 0,
  _initialized: false,
  _defaultId: null,  // 默认模板 ID（首个加载的模板）

  /**
   * 初始化 — 从服务端拉取全量模板
   */
  init: function () {
    var maxRetries = 3;
    for (var attempt = 1; attempt <= maxRetries; attempt++) {
      logger.info(TAG, "从服务端加载提示词模板 (尝试 " + attempt + "/" + maxRetries + ")...");
      try {
        var response = apiClient.fetchPromptTemplates(0);
        if (typeof response === "string") {
          try { response = JSON.parse(response); } catch (e) { /* ignore */ }
        }
        if (response && response.templates) {
          this._applyTemplates(response.templates);
          this._version = response.version;
          this._initialized = true;
          logger.info(TAG, "已加载 " + Object.keys(this._cache).length + " 个模板, 版本=" + this._version);
          return;
        }
        logger.warn(TAG, "服务端返回空模板列表 (尝试 " + attempt + ")");
      } catch (e) {
        logger.warn(TAG, "加载模板异常 (尝试 " + attempt + "): " + e.message);
      }
      if (attempt < maxRetries) sleep(2000);
    }
    logger.warn(TAG, "模板加载全部失败，将使用本地默认配置");
    this._initialized = true;
  },

  /**
   * 增量更新
   */
  checkAndUpdate: function (serverVersion) {
    if (serverVersion > this._version) {
      logger.info(TAG, "模板已过期 (本地=" + this._version + ", 服务端=" + serverVersion + "), 更新中...");
      var response = apiClient.fetchPromptTemplates(this._version);
      if (response && response.changed && response.templates) {
        this._applyTemplates(response.templates);
        this._version = response.version;
        logger.info(TAG, "模板已更新至版本 " + this._version);
      }
    }
  },

  /**
   * 获取指定模板
   * @param {string} [id] — 模板 ID，不传则返回默认模板
   * @returns {Object|null} { id, name, industry, content }
   */
  get: function (id) {
    if (id && this._cache[id]) return this._cache[id];
    // 查找默认模板
    if (this._defaultId && this._cache[this._defaultId]) return this._cache[this._defaultId];
    // 取第一个可用模板
    var keys = Object.keys(this._cache);
    if (keys.length > 0) {
      this._defaultId = keys[0];
      return this._cache[keys[0]];
    }
    return null;
  },

  /**
   * 按行业获取模板列表
   * @param {string} industry — "health" / "travel"
   * @returns {Array}
   */
  listByIndustry: function (industry) {
    var result = [];
    var keys = Object.keys(this._cache);
    for (var i = 0; i < keys.length; i++) {
      var t = this._cache[keys[i]];
      if (t.industry === industry) result.push(t);
    }
    return result;
  },

  _applyTemplates: function (templates) {
    for (var i = 0; i < templates.length; i++) {
      var t = templates[i];
      this._cache[t.id] = t;
      if (!this._defaultId) this._defaultId = t.id;
    }
    logger.debug(TAG, "已应用模板，当前缓存 " + Object.keys(this._cache).length + " 个");
  },

  getVersion: function () {
    return this._version;
  },
};

global.__promptTemplateLoader = promptTemplateLoader;
module.exports = promptTemplateLoader;
```

## core\pairing.js

```javascript
// device/core/pairing.js
// 设备配对模块 — 管理配对请求、轮询审批结果、存储密钥

var logger = require("../utils/logger");

var TAG = "配对";
var STORAGE_KEY = "dy_auto";

/**
 * 读取响应体为字符串（兼容 AutoJS6 的 Java ResponseBody 对象）
 */
function readResponseBody(response) {
  var body = response.body;
  if (typeof body === "string") return body;
  try {
    return body.string();
  } catch (e) {
    return String(body);
  }
}

var pairing = {
  _pairingToken: null,
  _serverUrl: null,

  /**
   * 检查设备是否已完成配对（本地存储中有密钥）
   * @returns {boolean}
   */
  isConfigured: function () {
    var storage = storages.create(STORAGE_KEY);
    return !!storage.get("device_secret", "");
  },

  /**
   * 获取已保存的密钥
   * @returns {string}
   */
  getSavedSecret: function () {
    return storages.create(STORAGE_KEY).get("device_secret", "");
  },

  /**
   * 获取已保存的服务端地址
   * @returns {string}
   */
  getSavedServerUrl: function () {
    return storages.create(STORAGE_KEY).get("server_url", "");
  },

  /**
   * 保存配对信息到本地存储
   * @param {string} serverUrl
   * @param {string} secret
   */
  save: function (serverUrl, secret) {
    var storage = storages.create(STORAGE_KEY);
    storage.put("server_url", serverUrl);
    storage.put("device_secret", secret);
    logger.info(TAG, "配对信息已保存");
  },

  /**
   * 发起配对请求
   * @param {string} serverIp - 服务端 IP（不含端口，默认 8000）
   * @param {string} deviceId - 设备 ID
   * @param {string} deviceName - 设备型号
   * @param {string} osVersion - 系统版本
   * @param {string} appVersion - 应用版本
   * @param {Object} [extra] - 额外设备信息 { screen_resolution, sdk_version, available_memory, manufacturer, ... }
   * @returns {Object|null} { pairing_token, status } 或 null
   */
  request: function (serverIp, deviceId, deviceName, osVersion, appVersion, extra) {
    var port = "8000";
    var ip = serverIp;
    // 支持 ip:port 格式
    if (serverIp.indexOf(":") !== -1) {
      var parts = serverIp.split(":");
      ip = parts[0];
      port = parts[1];
    }
    var serverUrl = "http://" + ip + ":" + port;
    this._serverUrl = serverUrl;

    var url = serverUrl + "/api/device/pair-request";
    var body = {
      device_id: deviceId,
      device_name: deviceName,
      os_version: osVersion || "",
      app_version: appVersion || "",
    };
    // 合并额外设备信息
    if (extra) {
      for (var key in extra) {
        if (extra.hasOwnProperty(key)) {
          body[key] = extra[key];
        }
      }
    }

    try {
      logger.info(TAG, "发送配对请求: " + url);
      logger.info(TAG, "请求体: " + JSON.stringify(body));
      var response = http.postJson(url, body, {
        headers: {},
        timeout: 10000,
      });

      var responseBody = readResponseBody(response);

      logger.info(TAG, "响应状态: " + response.statusCode + ", 响应体: " + responseBody);

      if (response.statusCode === 200) {
        var data = JSON.parse(responseBody);
        this._pairingToken = data.pairing_token;
        logger.info(TAG, "配对请求已提交, 状态: " + data.status);

        // 如果已经批准（已配对设备重连），直接保存密钥
        if (data.status === "approved" && data.secret) {
          this.save(this._serverUrl, data.secret);
        }
        return data;
      }

      logger.error(TAG, "配对请求失败: HTTP " + response.statusCode + " body=" + responseBody);
      return null;
    } catch (e) {
      logger.error(TAG, "配对请求异常: " + e.message + "\n" + e.stack);
      return null;
    }
  },

  /**
   * 轮询审批结果
   * @returns {Object|null} { status, secret?, config? } 或 null
   */
  checkStatus: function () {
    if (!this._pairingToken || !this._serverUrl) {
      logger.error(TAG, "无配对令牌，无法查询状态");
      return null;
    }

    var url = this._serverUrl + "/api/device/pair-status?token=" + this._pairingToken;

    try {
      var response = http.get(url, { timeout: 10000 });

      var responseBody = readResponseBody(response);

      if (response.statusCode === 200) {
        var data = JSON.parse(responseBody);

        if (data.status === "approved" && data.secret) {
          logger.info(TAG, "配对已批准，保存密钥");
          this.save(this._serverUrl, data.secret);
        } else if (data.status === "rejected") {
          logger.warn(TAG, "配对已被拒绝");
        } else {
          logger.debug(TAG, "等待审批中...");
        }

        return data;
      }

      if (response.statusCode === 404) {
        logger.error(TAG, "配对令牌无效或已过期");
        return { status: "expired" };
      }

      logger.error(TAG, "查询配对状态失败: HTTP " + response.statusCode + " body=" + responseBody);
      return null;
    } catch (e) {
      logger.error(TAG, "查询配对状态异常: " + e.message);
      return null;
    }
  },

  /**
   * 通过 WebSocket 等待审批结果（阻塞直到收到结果或超时）
   * @param {Function} onStatusChange - 状态变化回调 onStatusChange(status, data)
   * @returns {Object|null} 审批结果或 null（超时/失败）
   */
  waitForApproval: function (onStatusChange) {
    if (!this._pairingToken || !this._serverUrl) {
      logger.error(TAG, "无配对令牌，无法等待审批");
      return null;
    }

    var wsUrl = this._serverUrl.replace("http://", "ws://") +
      "/api/device/ws/pair/" + this._pairingToken;
    var result = null;
    var done = false;
    var self = this;

    logger.info(TAG, "连接 WS: " + wsUrl);

    try {
      var OkHttpClient = Packages.okhttp3.OkHttpClient;
      var Request = Packages.okhttp3.Request;
      var WebSocketListener = Packages.okhttp3.WebSocketListener;

      var client = new OkHttpClient.Builder()
        .readTimeout(0, java.util.concurrent.TimeUnit.MILLISECONDS)
        .build();

      var request = new Request.Builder().url(wsUrl).build();

      var listener = new JavaAdapter(WebSocketListener, {
        onOpen: function (ws, response) {
          logger.info(TAG, "WS 已连接，等待审批...");
        },
        onMessage: function (ws, text) {
          try {
            var data = JSON.parse(String(text));
            logger.info(TAG, "WS 收到消息: " + data.status);
            result = data;
            done = true;
            if (data.status === "approved" && data.secret) {
              self.save(self._serverUrl, data.secret);
            }
            if (onStatusChange) onStatusChange(data.status, data);
            ws.close(1000, "done");
          } catch (e) {
            logger.error(TAG, "WS 消息解析失败: " + e.message);
          }
        },
        onFailure: function (ws, t, response) {
          logger.error(TAG, "WS 连接失败: " + t.getMessage());
          done = true;
        },
        onClosing: function (ws, code, reason) {
          try { ws.close(1000, null); } catch (e) { /* already closed */ }
          done = true;
        },
      });

      client.newWebSocket(request, listener);

      // 阻塞等待结果，最长 5 分钟
      var startTime = Date.now();
      while (!done && Date.now() - startTime < 300000) {
        try {
          java.lang.Thread.sleep(500);
        } catch (sleepErr) {
          // Thread interrupted when WS closes — exit loop
          break;
        }
      }

      if (!done) {
        logger.warn(TAG, "WS 等待超时");
      }
    } catch (e) {
      logger.error(TAG, "WS 连接异常: " + e.message);
    }

    return result;
  },

  /**
   * 获取当前配对令牌（用于外部轮询）
   * @returns {string|null}
   */
  getPairingToken: function () {
    return this._pairingToken;
  },

  /**
   * 清除配对信息（用于重新配对）
   */
  clear: function () {
    var storage = storages.create(STORAGE_KEY);
    storage.remove("device_secret");
    storage.remove("server_url");
    this._pairingToken = null;
    this._serverUrl = null;
    logger.info(TAG, "配对信息已清除");
  },
};

module.exports = pairing;
```

## core\prompts-config.js

```javascript
// device/core/prompts-config.js
// 行业提示词统一配置 — 切换行业只需改 industry 字段或新增 industry 定义
// ai-analyzer.js 读取此配置，不硬编码任何行业相关文本

var logger = require("../utils/logger");

var promptsConfig = {
  // 当前行业标识，可通过 setIndustry() 切换
  industry: "health",

  industries: {
    // ========== 大健康行业 ==========
    health: {
      name: "大健康",
      domain: "大健康（养生、保健、中医、食疗、营养、运动健身、心理健康、慢病管理、亚健康调理）",

      // 本地关键词预过滤
      localFilter: {
        exclude: [
          "游戏", "电竞", "王者荣耀", "原神", "吃鸡", "英雄联盟",
          "汽车", "改装", "二手车", "驾照", "科目",
          "编程", "python", "java", "代码", "程序员",
          "美妆", "口红", "粉底", "眼影", "护肤",
          "穿搭", "潮牌", "aj", "球鞋", "aj1",
          "装修", "硬装", "软装", "瓷砖", "地板",
          "股票", "基金", "a股", "k线", "涨停",
          "追星", "饭圈", "爱豆", "应援",
        ],
        include: [
          "养生", "保健", "中医", "食疗", "营养", "运动", "健身",
          "心理", "睡眠", "失眠", "减肥", "瘦身", "排毒",
          "气血", "经络", "穴位", "艾灸", "拔罐", "推拿",
          "食补", "药膳", "茶饮", "枸杞", "红枣",
          "瑜伽", "太极", "跑步", "拉伸", "有氧",
          "血压", "血糖", "血脂", "胆固醇", "尿酸",
          "肠胃", "便秘", "湿气", "上火", "感冒",
          "免疫力", "抗衰老", "胶原蛋白", "维c", "维生素",
          "慢病", "亚健康", "调理", "体质", "寒凉",
          "大健康", "健康管理", "体重管理",
        ],
      },

      // 禁用词（所有 prompt 共用）
      disabledWords: "治愈 / 根治 / 治好 / 疗效保证 / 包好 / 替代药物 / 停药 / 不用吃药 /\n医生 / 我是医生 / 专家 / 我是专家 / 保证有效 / 百分百 / 100% / 神药",

      // 身份设定
      identity: {
        role: "「健康生活指南」视角，像一个靠谱的健康科普评论者",
        constraints: [
          "不是医生，不做诊断，不保证疗效",
          "讨论的是日常饮食、生活习惯，不是治疗方案",
        ],
      },

      // 评论语义分析指南
      semanticGuide: {
        mission: "这条评论背后是不是一个\"有真实健康需求的人\"",
        highValueSignals: [
          "提及具体病症/症状：糖尿病、高血压、失眠、便秘、湿气、痛风、关节痛、脱发、过敏、胃病、颈椎、腰椎等",
          "提及具体药物/治疗方式：胰岛素、降压药、降糖药、中药、艾灸、针灸、推拿、拔罐、理疗等",
          "询问\"能不能好/会不会好转\"：有转机不、能恢复吗、还能好吗、有救吗 → 透露出正在经历这个病",
          "询问\"是不是得一直/一辈子\"：是不是得用一辈子、离不开吗、要一直吃吗 → 已在用药，想摆脱依赖",
          "询问\"有什么讲究/注意/忌口\"：有啥讲究、要注意什么、能吃吗、有什么禁忌 → 已在管理这个病",
          "自述症状/经历：\"最近总是…\"、\"我XX已经…年了\"、\"每次…都…\"、\"XX太痛苦了\" → 患者本人或家属",
          "负面情绪+病症信息：\"试了好多方法都不行\"、\"XX反复发作烦死了\" → 高价值截流点",
        ],
        lowValueSignals: [
          "泛泛而谈无具体内容：\"有道理\"、\"学到了\"、\"不错\"、\"支持\"",
          "纯表情/灌水/刷存在感：\"哈哈哈\"、\"第一\"、\"来了\"、\"打卡\"",
          "只问价格不提任何病症：\"多少钱\"、\"贵吗\" → 可能只是比价",
          "无具体健康信息的空洞提问：\"有用吗\"、\"真的假的\"、\"效果怎么样\" → 信息量为零",
        ],
        keyExamples: [
          "\"胰岛素是不是得用一辈子呀\" → 具体药物+询问长期性 → 真实糖尿病患者 → 高价值",
          "\"胰岛素使用真的离不开？\" → 具体药物+询问依赖性 → 真实患者在寻求摆脱 → 高价值",
          "\"有转机不\" → 询问好转可能性 → 正在经历病痛 → 高价值",
          "\"胰岛素使用有啥讲究呢\" → 具体药物+寻求指导 → 已在用药，想优化 → 高价值",
          "\"这个有用吗\" → 无具体病名/药名/症状 → 纯路人 → 低价值",
          "\"多少钱\" → 只问价格无病症 → 可能是比价 → 低价值",
        ],
      },

      // ================================================================
      // 场景 2：评论语义分析 + 回复生成（评论区截流）
      // 目的：分析已有评论，识别高价值用户，生成回复吸引对方注意
      // 回复要让评论者觉得你懂行、可信，从而愿意接受私聊
      // ================================================================
      analysis: {
        intents: [
          "consult_intent: 针对具体健康问题的咨询，评论中包含病症/药物/症状/治疗方式",
          "buy_intent: 明确求购，\"怎么买？\"、\"多少钱？\"、\"求链接\"、\"在哪里买\"",
          "compare_intent: 对比选项，\"这个和XX比哪个好？\"",
          "meaningless: 无信息量，纯表情、灌水 — 直接 0 分",
        ],
        sentiments: [
          "positive (正向): 赞赏、感谢、认同",
          "negative (负向): 抱怨、痛苦、失望 — 如果同时提及病症，是高价值截流点",
          "neutral (中立): 客观提问、陈述",
        ],
        scoringRules: [
          "consult_intent: 45分 | buy_intent: 50分 | compare_intent: 40分 | meaningless: 0分",
          "negative情感（含病症信息）: +20分 | positive情感: +10分 | neutral: 0分",
          "specific_condition (提及具体病症/药物/症状): +15分",
          "price敏感: +10分 | urgency > 7: +10分",
          "is_bot / is_competitor: 直接 0 分",
        ],
        replyRules: [
          "目的：回复要吸引对方注意、建立信任、引发进一步交流的意愿",
          "自然接住对方评论，给一条针对性的实用小建议，暗示你在这方面有经验",
          "像健康科普博主回复粉丝一样自然，避免\"亲/亲亲/宝\"等营销口吻",
          "中老年用户居多，不用年轻化网络梗",
          "单条不超过 40 字，信息密度高但不啰嗦",
          "严禁以\"同感\"、\"我也是\"、\"确实\"、\"说得好\"开头 — 每条开头句式必须不同",
          "开头多样化：直接回应问题、给出新角度、反问引发思考、补充对方没说的点",
        ],
        replyExample: {
          good: "饭前喝点稀释的苹果水对胃比较温和，可以试试看",
          bad: "我也是这么觉得的",
        },
        tiers: {
          strong_buy: "对方询价/求购，分享使用经验或提出建议",
          health_consult: "对方健康咨询，从饮食/运动/习惯角度切入",
          patient_self: "对方自述患者，从家人经历切入，禁止\"我也是\"开头",
          other: "自然接话，禁止\"同感\"切入",
        },
      },

      // ================================================================
      // 场景 1：视频评论生成（引流截流）
      // 目的：评论展示在视频下方，给其他看视频的人看，相当于"广告位"
      // 需要吸引眼球、引发好奇、暗示专业度，但不直接营销
      // ================================================================
      videoComment: {
        context: "你是一个抖音健康科普博主，正在浏览健康/养生类短视频。你需要在视频下方写一条评论，这条评论会被其他观看此视频的用户看到。",
        goal: "这条评论就是你的广告位。目标是让看到评论的人觉得你懂行、可信，从而点进你的主页或产生咨询意向。",
        rules: [
          "吸引注意：开头用提问、反常识观点、或点出视频没说透的细节来抓住眼球",
          "暗示专业：结合视频内容给出一个具体的小知识点或实用建议，让人感觉你懂",
          "引发好奇：留一点没说尽的感觉，让人想进一步了解（但不直接引导私信）",
          "15-40字，口语化但信息密度高",
          "严禁禁用词：治愈/根治/治好/疗效保证/替代药物/停药/医生/专家",
          "严禁直接营销：不带链接、不加微信、不说\"私信我\"、不说\"找我\"",
          "不要以「同感」「我也是」「确实」「说得好」开头 — 太像路人",
        ],
      },

      // ================================================================
      // 场景 3a：私信破冰（评论区 → 私信的第一步）
      // 目的：第一次私信，建立联系，不卖货不推销
      // ================================================================
      dmOpener: {
        context: "你是一个关心家人健康的普通人，在抖音私信一位对相关话题感兴趣的陌生网友。",
        identity: {
          role: "「健康生活指南」视角，像一个靠谱的健康科普账号",
          constraints: [
            "不是医生，不是产品顾问，不做诊断，不保证疗效",
            "讨论的是日常饮食、生活习惯，不是治疗方案",
          ],
        },
        goal: "自然地接住对方的评论，给出一条实用的生活小建议，不卖货、不留联系方式。以「针对对方评论的实用建议」为切口，不要像客服。",
        style: [
          "像健康科普博主给建议一样自然，避免\"亲/亲亲/宝\"营销口吻",
          "中老年用户居多，不用年轻化网络梗",
          "单条不超过 50 字，一次只说一件事",
        ],
        tierTones: {
          strong_buy: "不报价不发链接，先柔和确认需求背景",
          health_consult: "以\"我家里也有这种情况，正好一起交流\"切入",
          patient_self: "先共情，绝不第一条就推销",
          other: "以\"看到你评论，我这边也关心\"切入",
        },
      },

      // 私信 — 多阶段
      dmStages: {
        qualifying: {
          name: "了解需求",
          goal: "只问不卖。确认对方真实场景：本人还是家人、什么情况、日常习惯。每次只问一个问题，不盘问。",
          style: "像健康顾问了解情况，朴素具体。共情对方处境。单条 ≤ 50 字。",
          maxTokens: 150,
        },
        nurturing: {
          name: "信任培育",
          goal: "给出日常饮食/生活习惯的实用建议。用\"可以试试\"\"建议\"\"若想…\"等客观句式。绝不用\"医生说\"\"专家建议\"。仍不卖货不提产品。",
          style: "细节感优先：具体做法 > 笼统道理。单条 ≤ 50 字。",
          maxTokens: 200,
        },
        converting: {
          name: "转化引导",
          goal: "对方释放成交信号。不报价不发链接。确认诉求，表明\"稍后有朋友详细对接\"，让对方愿意等。留一个温和的 gatekeeper 问题。",
          style: "语气诚恳不催促。禁止承诺价格/折扣。单条 ≤ 60 字。",
          maxTokens: 150,
        },
        follow_up: {
          name: "唤回",
          goal: "极其轻量地问一句，不追问不卖货。可以以具体生活场景切入，不是\"在吗/怎么没回\"。单次只发一条。",
          style: "语气平和没压迫感。单条 ≤ 40 字。自然，不像群发。",
          maxTokens: 120,
        },
      },
    },

    // ========== 旅游行业（示例模板，待完善） ==========
    travel: {
      name: "旅游",
      domain: "旅游（国内游、出境游、自驾游、亲子游、民宿、酒店、景点攻略）",

      localFilter: {
        exclude: [
          "游戏", "电竞", "编程", "股票", "基金",
        ],
        include: [
          "旅游", "旅行", "自驾", "跟团", "民宿", "酒店",
          "景点", "攻略", "打卡", "网红", "徒步", "露营",
          "签证", "机票", "高铁", "包车", "导游",
          "亲子游", "蜜月", "穷游", "自由行",
        ],
      },

      disabledWords: "保证最低价 / 绝对便宜 / 百分百出签 / 包过 / 内部渠道",

      identity: {
        role: "「旅行玩家」视角，像一个靠谱的旅行体验分享者",
        constraints: [
          "不是旅行社官方，不承诺最低价",
          "分享的是个人旅行经验，不是商业推广",
        ],
      },

      semanticGuide: {
        mission: "这条评论背后是不是一个\"有真实出行需求的人\"",
        highValueSignals: [
          "提及具体目的地：想去XX、XX值得去吗、XX什么时候去最好",
          "询问行程安排：几天够吗、路线怎么规划、带老人/孩子方便吗",
          "询问费用预算：人均多少、性价比怎么样、有没有不踩坑的推荐",
          "询问出行时间：几月份最好、淡季是什么时候、现在去人多吗",
          "自述出行困难：\"一直想去但…\"、\"担心…不敢去\" → 有需求但犹豫",
        ],
        lowValueSignals: [
          "纯赞美无实质内容：\"好美\"、\"想去\"（没有具体信息）",
          "纯表情/灌水：\"哈哈哈\"、\"第一\"、\"来了\"",
          "只问价格无目的地信息：\"多少钱\" → 信息量为零",
        ],
        keyExamples: [
          "\"带老人去XX方便吗\" → 具体目的地+具体场景 → 真实出行需求 → 高价值",
          "\"人均大概多少，怕被宰\" → 询问预算+痛点 → 有出行计划 → 高价值",
          "\"好美\" → 无具体信息 → 路人 → 低价值",
        ],
      },

      analysis: {
        intents: [
          "consult_intent: 针对具体目的地的出行咨询，提及地点/时间/人群/预算",
          "buy_intent: 明确求购，\"怎么订？\"、\"有链接吗？\"、\"在哪里报团\"",
          "compare_intent: 对比选项，\"XX和YY哪个更适合带娃？\"",
          "meaningless: 无信息量 — 直接 0 分",
        ],
        sentiments: [
          "positive (正向): 喜欢、期待、向往",
          "negative (负向): 吐槽踩坑经历 — 高价值截流点",
          "neutral (中立): 客观提问",
        ],
        scoringRules: [
          "consult_intent: 45分 | buy_intent: 50分 | compare_intent: 40分 | meaningless: 0分",
          "negative情感（含具体目的地/经历）: +20分 | positive情感: +10分 | neutral: 0分",
          "specific_destination (提及具体目的地/出行场景): +15分",
          "price敏感: +10分 | urgency > 7: +10分",
          "is_bot / is_competitor: 直接 0 分",
        ],
        replyRules: [
          "自然地接住对方评论，分享一点实用旅行建议",
          "像旅行博主评论互动一样自然",
          "单条不超过 30 字",
          "严禁以\"同感\"、\"我也是\"开头",
        ],
        replyExample: {
          good: "XX的话建议避开七八月，人太多了，九十月去正合适",
          bad: "我也是，也想去",
        },
        tiers: {
          strong_buy: "对方询价/求购，分享经验不报价",
          travel_consult: "对方出行咨询，从时间/路线/预算角度切入",
          other: "自然接话，禁止\"同感\"切入",
        },
      },

      videoComment: {
        context: "你是一个抖音用户，正在浏览旅游类短视频。请根据视频内容写一条自然、真实的评论。",
        rules: [
          "像真人刷抖音时随手写的评论，不要太正式",
          "15-30字，口语化",
          "结合视频具体内容（目的地、景色、体验）",
          "严禁禁用词",
          "严禁营销感：不要带链接、不要引导加微信",
        ],
      },

      dmOpener: {
        context: "你是一个热爱旅行的人，在抖音私信一位对旅游话题感兴趣的陌生网友。",
        identity: {
          role: "「旅行玩家」视角，像一个靠谱的旅行经验分享者",
          constraints: [
            "不是旅行社销售，不推销产品",
            "分享的是个人旅行经验",
          ],
        },
        goal: "自然地接住对方的评论，分享一点目的地相关的实用建议，不卖货、不留联系方式。",
        style: [
          "像旅行博主分享经验一样自然",
          "单条不超过 50 字",
        ],
        tierTones: {
          strong_buy: "不报价不发链接，先确认想去哪里、什么时候",
          travel_consult: "以\"我去过那边，有个小建议\"切入",
          other: "以\"看到你评论，我刚好去过那边\"切入",
        },
      },

      dmStages: {
        qualifying: {
          name: "了解需求",
          goal: "确认对方想去哪里、几个人、大概什么时间、有什么顾虑。每次只问一个问题。",
          style: "像朋友聊天一样自然。单条 ≤ 50 字。",
          maxTokens: 150,
        },
        nurturing: {
          name: "信任培育",
          goal: "给出具体目的地的实用建议：最佳季节、避坑攻略、交通方式等。",
          style: "细节感优先：具体建议 > 笼统话。单条 ≤ 50 字。",
          maxTokens: 200,
        },
        converting: {
          name: "转化引导",
          goal: "对方释放出行信号。不报价不发链接。确认诉求，留一个温和问题。",
          style: "语气诚恳不催促。单条 ≤ 60 字。",
          maxTokens: 150,
        },
        follow_up: {
          name: "唤回",
          goal: "轻量唤回，以具体旅行场景切入，不是\"在吗\"。单次只发一条。",
          style: "语气平和。单条 ≤ 40 字。",
          maxTokens: 120,
        },
      },

    },
  },

  // ---- 公共方法 ----

  _override: null,  // 服务端下发的模板内容，非 null 时优先级高于本地 industry 配置

  get: function () {
    if (this._override) return this._override;
    return this.industries[this.industry] || this.industries["health"];
  },

  setOverride: function (templateContent) {
    if (!templateContent) { this._override = null; return true; }
    // Validate required top-level fields
    var required = ["identity", "disabledWords", "semanticGuide", "analysis", "localFilter"];
    for (var i = 0; i < required.length; i++) {
      if (!templateContent[required[i]]) { return false; }
    }
    // Validate nested critical fields
    var an = templateContent.analysis;
    if (!an.intents || !an.scoringRules || !an.replyRules) { return false; }
    var sg = templateContent.semanticGuide;
    if (!sg.highValueSignals || !sg.lowValueSignals || !sg.keyExamples) { return false; }
    this._override = templateContent;
    return true;
  },

  setIndustry: function (name) {
    if (this.industries[name]) {
      this.industry = name;
    } else if (name) {
      logger.warn("配置", "未知行业: '" + name + "', 回退为 health");
      this.industry = "health";
    }
  },
};

module.exports = promptsConfig;
```

## core\selector-resolver.js

```javascript
// device/core/selector-resolver.js
// 策略驱动的子元素查找 — 从 BaseHandler 和 comment-utils 抽离的公共逻辑
// 供 base-handler.js 和 comment-utils.js 共同使用

var uiOperator = require("./ui-operator");
var selectorLoader = require("./selector-loader");

var selectorResolver = {

  /**
   * 在父元素内按选择器策略查找子元素
   */
  findChildBySelector: function (parent, actionName) {
    var selector = selectorLoader.get(actionName);
    if (!selector) return null;
    var strategies = selector.strategies.slice().sort(function (a, b) { return a.priority - b.priority; });
    for (var i = 0; i < strategies.length; i++) {
      var el = selectorResolver.findByStrategyInParent(parent, strategies[i]);
      if (el) return el;
    }
    return null;
  },

  findByStrategyInParent: function (parent, strategy) {
    if (strategy.conditions && strategy.conditions.length > 0) {
      return selectorResolver.findByConditionsInParent(parent, strategy);
    }
    if (strategy.type === "chain") {
      return selectorResolver.findByChainInParent(parent, strategy.steps || []);
    }
    return selectorResolver.findByCondInParent(parent, strategy);
  },

  findByCondInParent: function (parent, cond) {
    var matchMode = cond.match_mode || "exact";
    try {
      if (matchMode === "contains") {
        switch (cond.type) {
          case "text": return parent.findOne(textContains(cond.value));
          case "desc": return parent.findOne(descContains(cond.value));
          case "id": return parent.findOne(idContains(cond.value));
          case "className": return parent.findOne(classNameContains(cond.value));
        }
      } else {
        switch (cond.type) {
          case "text": return parent.findOne(text(cond.value));
          case "desc": return parent.findOne(desc(cond.value));
          case "id": return parent.findOne(id(cond.value));
          case "className": return parent.findOne(className(cond.value));
        }
      }
    } catch (e) {}
    return null;
  },

  findAllByCondInParent: function (parent, cond) {
    var matchMode = cond.match_mode || "exact";
    try {
      if (matchMode === "contains") {
        switch (cond.type) {
          case "text": return parent.find(textContains(cond.value));
          case "desc": return parent.find(descContains(cond.value));
          case "id": return parent.find(idContains(cond.value));
          case "className": return parent.find(classNameContains(cond.value));
        }
      } else {
        switch (cond.type) {
          case "text": return parent.find(text(cond.value));
          case "desc": return parent.find(desc(cond.value));
          case "id": return parent.find(id(cond.value));
          case "className": return parent.find(className(cond.value));
        }
      }
    } catch (e) {}
    return [];
  },

  findByConditionsInParent: function (parent, strategy) {
    var conditions = strategy.conditions;
    var logic = strategy.logic || "and";

    if (conditions.length === 1) {
      return selectorResolver.findByCondInParent(parent, conditions[0]);
    }

    if (logic === "or") {
      for (var j = 0; j < conditions.length; j++) {
        var el = selectorResolver.findByCondInParent(parent, conditions[j]);
        if (el) return el;
      }
      return null;
    }

    var candidates = selectorResolver.findAllByCondInParent(parent, conditions[0]);
    for (var m = 0; m < candidates.length; m++) {
      var allMatch = true;
      for (var n = 1; n < conditions.length; n++) {
        if (!uiOperator._elementMatchesCondition(candidates[m], conditions[n])) {
          allMatch = false;
          break;
        }
      }
      if (allMatch) return candidates[m];
    }
    return null;
  },

  findByChainInParent: function (parent, steps) {
    if (!steps || steps.length === 0) return null;

    // Phase 1: build selector chain from filter steps
    var sel = null;
    var navStartIdx = steps.length;
    for (var i = 0; i < steps.length; i++) {
      var nav = steps[i].nav || "filter";
      if (nav !== "filter") { navStartIdx = i; break; }
      if (!sel) { sel = uiOperator._makeSelector(steps[i]); }
      else { sel = uiOperator._chainSelector(sel, steps[i]); }
      if (!sel) return null;
    }

    // Phase 2: find first matching element within parent
    var el = null;
    if (sel) {
      var candidates = parent.find(sel);
      if (candidates && candidates.length > 0) {
        for (var k = 0; k < candidates.length; k++) {
          if (uiOperator._isOnScreen(candidates[k])) { el = candidates[k]; break; }
        }
      }
    } else {
      el = parent;
    }
    if (!el) return null;

    // Phase 3: walk the tree with nav steps
    for (var m = navStartIdx; m < steps.length; m++) {
      var navStep = steps[m];
      var navAction = navStep.nav || "filter";
      if (navAction === "parent") {
        try { el = el.parent(); } catch (e) { return null; }
        if (!el) return null;
      } else if (navAction === "child") {
        var childSel = uiOperator._makeSelector(navStep);
        if (!childSel) return null;
        try {
          var children = el.find(childSel);
          if (!children || children.length === 0) return null;
          var idx = navStep.index || 0;
          var found = 0; el = null;
          for (var c = 0; c < children.length; c++) {
            if (uiOperator._isOnScreen(children[c])) {
              if (found === idx) { el = children[c]; break; }
              found++;
            }
          }
          if (!el) return null;
        } catch (e) { return null; }
      } else if (navAction === "sibling") {
        var siblingSel = uiOperator._makeSelector(navStep);
        if (!siblingSel) return null;
        try {
          var p = el.parent();
          if (!p) return null;
          var siblings = p.find(siblingSel);
          if (!siblings || siblings.length === 0) return null;
          var sibIdx = navStep.index || 0;
          var sf = 0; el = null;
          for (var s = 0; s < siblings.length; s++) {
            if (uiOperator._isOnScreen(siblings[s])) {
              if (sf === sibIdx) { el = siblings[s]; break; }
              sf++;
            }
          }
          if (!el) return null;
        } catch (e) { return null; }
      } else {
        if (!uiOperator._elementMatchesStep(el, navStep)) return null;
      }
    }
    return el;
  },

  /**
   * 从子元素提取值
   */
  extractChildValue: function (el, actionName, fallback) {
    try {
      var selector = selectorLoader.get(actionName);
      if (selector && selector.purpose === "extract") {
        var val = uiOperator.extractValue(el, selector);
        if (val != null) return val;
      }
      if (el.text && typeof el.text === "function") {
        return el.text() || fallback;
      }
      try { return el.desc() || fallback; } catch (e) { return fallback; }
    } catch (e) { return fallback; }
  },
};

module.exports = selectorResolver;
```

## core\flow-context.js

```javascript
// device/core/flow-context.js
// 流程上下文状态机 — 纯运行时，结果驱动
// 与 pageDetector(isOnPage/detectPage) 配合使用：
//   第一层 pageDetector → "我现在看到的是什么页面？"
//   第二层 flowContext → "我是在什么业务环节来到这个页面的？"

var flowContext = {
  _current: "idle",

  enter: function (state) {
    this._current = state;
  },

  is: function (state) {
    return this._current === state;
  },

  reset: function () {
    this._current = "idle";
  },
};

module.exports = flowContext;
```

## core\anti-detect.js

```javascript
// device/core/anti-detect.js
var config = global.__config || require("../config");
var logger = require("../utils/logger");
var bezier = require("../utils/bezier");

var TAG = "反检测";
var settings = config.antiDetect;

var antiDetect = {
  _skipDisabled: false,  // 序列发送期间禁用随机跳过
  /**
   * 操作前随机延迟
   * @param {string} actionName - 操作名称（用于日志）
   */
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

    // AutoJS6 gestures API: gestures([delay, duration, [x1,y1], [x2,y2], ...])
    gestures([0, totalDuration].concat(gesturePoints));
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
    var speedFactor = Math.max(0.5, Math.min(1.5, distance / 500));

    var path = bezier.generateSwipePath(startX, startY, endX, endY);
    logger.debug(TAG, "增强滑动: " + path.length + " 个轨迹点, 速度=" + speedFactor.toFixed(2));

    var gesturePoints = path.map(function (p) {
      return [p.x, p.y];
    });

    var totalDuration = path.reduce(function (sum, p) {
      return sum + Math.round(p.duration / speedFactor);
    }, 0);

    gestures([0, totalDuration].concat(gesturePoints));
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
```

## core\ui-operator.js

```javascript
var selectorLoader = require("./selector-loader");
var apiClient = require("./api-client");
var logger = require("../utils/logger");

var TAG = "界面操作";

var uiOperator = {
  /**
   * 启动抖音
   * @returns {boolean}
   */
  openApp: function () {
    var TARGET_PKG = "com.ss.android.ugc.aweme";
    logger.info(TAG, "正在打开抖音...");

    var pkg = currentPackage();
    if (pkg === TARGET_PKG) {
      logger.info(TAG, "抖音已在前台");
      return true;
    }

    // 键盘覆盖兜底：输入法弹出时 currentPackage() 返回键盘包名, 先关键盘
    if (pkg && (pkg.indexOf("inputmethod") !== -1 || pkg.indexOf("keyboard") !== -1)) {
      logger.info(TAG, "输入法覆盖(" + pkg + "), 关闭键盘后重试");
      // 多策略关闭键盘：back → home → 暴力杀键盘
      try { back(); sleep(800); } catch (e) {}
      if (currentPackage() === TARGET_PKG) {
        logger.info(TAG, "关闭键盘后抖音已在前台");
        return true;
      }
      // back() 不够，尝试 home() 退回桌面再启动
      try { home(); sleep(1000); } catch (e) {}
      pkg = currentPackage();
      if (pkg === TARGET_PKG) {
        logger.info(TAG, "home 后抖音已在前台");
        return true;
      }
      // 键盘仍然在前台，直接用包名启动抖音（绕过键盘拦截）
      if (pkg && (pkg.indexOf("inputmethod") !== -1 || pkg.indexOf("keyboard") !== -1)) {
        logger.info(TAG, "键盘顽固残留(" + pkg + ")，尝试强行启动抖音");
        try {
          app.startActivity({ packageName: TARGET_PKG, className: "com.ss.android.ugc.aweme.splash.SplashActivity" });
        } catch (e2) {
          app.launchPackage(TARGET_PKG);
        }
        sleep(2000);
        if (currentPackage() === TARGET_PKG) {
          logger.info(TAG, "强制启动抖音成功");
          return true;
        }
      }
    }

    app.launchApp("抖音");

    for (var i = 0; i < 3; i++) {
      sleep(3000);
      pkg = currentPackage();
      if (pkg === TARGET_PKG) {
        logger.info(TAG, "抖音打开成功");
        try { app.openUrl("snssdk1128://feed"); sleep(2000); } catch (e) {}
        return true;
      }
      logger.warn(TAG, "等待抖音启动 (" + (i + 1) + "/3), 当前包名: " + pkg);
    }

    var finalPkg = currentPackage();
    logger.error(TAG, "打开抖音失败, 当前包名: " + finalPkg + " (期望: " + TARGET_PKG + ")");
    return false;
  },

  /**
   * 关闭抖音
   */
  closeApp: function () {
    logger.info(TAG, "正在返回桌面...");
    try {
      home();
    } catch (e) {
      // home() 失败不阻塞
    }
    sleep(1000);
  },

  /**
   * 检查抖音是否在前台
   * @returns {boolean}
   */
  isAppActive: function () {
    var pkg = currentPackage();
    if (pkg === "com.ss.android.ugc.aweme") return true;
    // 部分场景下 currentPackage 返回系统 UI 或空，也视为抖音未在前台
    logger.debug(TAG, "抖音未在前台, 当前包名: " + pkg);
    return false;
  },

  /**
   * 判断元素是否在当前屏幕内
   */
  _isOnScreen: function (el) {
    if (!el) return false;
    // 坐标类型（图片匹配、坐标策略）视为在屏幕内
    if (el.isImage || el.isCoordinate || el.isPackage) return true;
    try {
      var b = el.bounds();
      if (!b) return false;
      var cx = b.centerX();
      var cy = b.centerY();
      return cx >= 0 && cy >= 0 && cx < device.width && cy < device.height;
    } catch (e) { return false; }
  },

  /**
   * 使用选择器查找控件（仅返回屏幕内的元素，避免 RecyclerView 复用导致的离屏匹配）
   * @param {string} actionName - 操作名称
   * @param {number} timeout - 超时时间（毫秒），默认 5000
   * @returns {UiObject|null} 找到的控件，或 null
   */
  findElement: function (actionName, timeout, quiet) {
    timeout = timeout || 2000;
    var selector = selectorLoader.get(actionName);
    if (!selector) {
      logger.error(TAG, "未找到选择器配置: " + actionName);
      return null;
    }

    var strategies = selector.strategies.slice().sort(function (a, b) {
      return a.priority - b.priority;
    });

    var startTime = Date.now();
    while (Date.now() - startTime < timeout) {
      for (var i = 0; i < strategies.length; i++) {
        var s = strategies[i];
        var element = this._findByStrategy(s);
        if (element && this._isOnScreen(element)) {
          // press 模式：找到元素后用真实触摸按压代替点击
          if (s.click_mode === "press") {
            if (element.isImage || element.isCoordinate) {
              if (s.x_percent != null) element.x += s.x_percent;
              if (s.y_percent != null) element.y += s.y_percent;
              return { isPress: true, x: element.x, y: element.y, duration: s.press_duration || 150 };
            }
            if (!element.isPackage) {
              var pb = element.bounds();
              if (pb) {
                var pcx = pb.centerX();
                var pcy = pb.centerY();
                if (s.x_percent != null) pcx += Math.round((pb.right - pb.left) * s.x_percent / 100);
                if (s.y_percent != null) pcy += Math.round((pb.bottom - pb.top) * s.y_percent / 100);
                logger.debug(TAG, "通过 " + s.type + " +press 找到: '" + actionName + "'");
                return { isPress: true, x: pcx, y: pcy, duration: s.press_duration || 150 };
              }
            }
          }

          // 偏移处理：image 用像素偏移，coordinate 已在 _findByStrategy 处理跳过，控件按比例
          if (s.x_percent != null || s.y_percent != null) {
            if (element.isImage) {
              if (s.x_percent != null) element.x += s.x_percent;
              if (s.y_percent != null) element.y += s.y_percent;
              logger.debug(TAG, "通过 " + s.type + " +偏移 找到: '" + actionName + "'");
              return element;
            }
            if (!element.isCoordinate && !element.isPackage) {
              var b = element.bounds();
              if (b) {
                var cx = b.centerX();
                var cy = b.centerY();
                var elW = b.right - b.left;
                var elH = b.bottom - b.top;
                if (s.x_percent != null) cx += Math.round(elW * s.x_percent / 100);
                if (s.y_percent != null) cy += Math.round(elH * s.y_percent / 100);
                logger.debug(TAG, "通过 " + s.type + " +偏移 找到: '" + actionName + "'");
                return { isCoordinate: true, x: cx, y: cy };
              }
            }
          }
          logger.debug(TAG, "通过 " + s.type + " 找到元素: '" + actionName + "'");
          return element;
        }
      }
      sleep(700);
    }

    if (!quiet) { logger.warn(TAG, "未找到元素: " + actionName); }
    return null;
  },

  /**
   * 按条件查找元素（支持 text/id/desc/className 类型 + match_mode）
   */
  _findByCondition: function (cond) {
    var matchMode = cond.match_mode || "exact";
    if (matchMode === "contains") {
      switch (cond.type) {
        case "text": return textContains(cond.value).find();
        case "desc": return descContains(cond.value).find();
        case "id": return idContains(cond.value).find();
        case "className": return classNameContains(cond.value).find();
        default: return null;
      }
    }
    switch (cond.type) {
      case "text": return text(cond.value).find();
      case "desc": return desc(cond.value).find();
      case "id": return id(cond.value).find();
      case "className": return className(cond.value).find();
      default: return null;
    }
  },

  /**
   * 检查单个元素是否匹配条件
   */
  _elementMatchesCondition: function (el, cond) {
    var matchMode = cond.match_mode || "exact";
    var actual;
    try {
      switch (cond.type) {
        case "text": actual = el.text(); break;
        case "desc": actual = el.desc(); break;
        case "id": actual = el.id(); break;
        case "className": actual = el.className(); break;
        default: return false;
      }
    } catch (e) { return false; }
    if (!actual) return false;
    if (matchMode === "contains") return actual.indexOf(cond.value) !== -1;
    return actual === cond.value;
  },

  /**
   * 多条件组合查找（AND/OR 逻辑）
   */
  _findByConditions: function (strategy) {
    var conditions = strategy.conditions;
    var logic = strategy.logic || "and";

    if (!conditions || conditions.length === 0) return null;

    // Single condition: short-circuit regardless of logic
    if (conditions.length === 1) {
      var single = this._findByCondition(conditions[0]);
      if (single) {
        for (var i = 0; i < single.length; i++) {
          if (this._isOnScreen(single[i])) return single[i];
        }
      }
      return null;
    }

    if (logic === "or") {
      // OR: return first on-screen element matching ANY condition (not just conditions[0])
      for (var j = 0; j < conditions.length; j++) {
        var condCandidates = this._findByCondition(conditions[j]);
        if (!condCandidates) continue;
        for (var k = 0; k < condCandidates.length; k++) {
          if (this._isOnScreen(condCandidates[k])) return condCandidates[k];
        }
      }
      return null;
    }

    // AND: all conditions must match the same element
    var candidates = this._findByCondition(conditions[0]);
    if (!candidates || candidates.length === 0) return null;

    for (var m = 0; m < candidates.length; m++) {
      var el = candidates[m];
      if (!this._isOnScreen(el)) continue;

      var allMatch = true;
      for (var n = 1; n < conditions.length; n++) {
        if (!this._elementMatchesCondition(el, conditions[n])) {
          allMatch = false;
          break;
        }
      }
      if (allMatch) return el;
    }
    return null;
  },

  /**
   * 按策略类型查找单个控件
   * @param {Object} strategy - { type, value, match_mode, conditions, logic, ... }
   * @returns {UiObject|null}
   */
  _findByStrategy: function (strategy) {
    // Multi-condition mode
    if (strategy.conditions && strategy.conditions.length > 0) {
      return this._findByConditions(strategy);
    }

    var all, j;
    // Non-text types: match_mode is meaningless, handle directly
    switch (strategy.type) {
      case "package":
        if (currentPackage() === strategy.value) {
          return { isPackage: true, packageName: strategy.value };
        }
        return null;
      case "coordinate":
        var x = Math.round(strategy.x_percent * device.width);
        var y = Math.round(strategy.y_percent * device.height);
        return { isCoordinate: true, x: x, y: y };
      case "image":
        return this._findByImage(strategy.template, strategy.threshold || 0.8);
      case "chain":
        return this._findByChain(strategy.steps || []);
    }
    // Text-based types: use match_mode
    var matchMode = strategy.match_mode || "exact";
    if (matchMode === "contains") {
      switch (strategy.type) {
        case "text": all = textContains(strategy.value).find(); break;
        case "id": all = idContains(strategy.value).find(); break;
        case "desc": all = descContains(strategy.value).find(); break;
        case "className": all = classNameContains(strategy.value).find(); break;
        default: return null;
      }
    } else {
      switch (strategy.type) {
        case "text": all = text(strategy.value).find(); break;
        case "id": all = id(strategy.value).find(); break;
        case "desc": all = desc(strategy.value).find(); break;
        case "className": all = className(strategy.value).find(); break;
        default: return null;
      }
    }
    if (all && all.length > 0) {
      for (j = 0; j < all.length; j++) {
        if (this._isOnScreen(all[j])) return all[j];
      }
    }
    return null;
  },

  /**
   * 按策略类型查找多个控件（返回数组）
   * @param {Object} strategy - { type, value }
   * @returns {Array} UiObject 数组
   */
  _findManyByStrategy: function (strategy) {
    // Multi-condition mode
    if (strategy.conditions && strategy.conditions.length > 0) {
      return this._findManyByConditions(strategy);
    }

    // Non-text types: match_mode is meaningless, handle directly
    if (strategy.type === "chain") {
      return this._findByChainAll(strategy.steps || []);
    }

    // Text-based types: use match_mode
    var matchMode = strategy.match_mode || "exact";
    if (matchMode === "contains") {
      switch (strategy.type) {
        case "text": return textContains(strategy.value).find();
        case "id": return idContains(strategy.value).find();
        case "desc": return descContains(strategy.value).find();
        case "className": return classNameContains(strategy.value).find();
        default: return [];
      }
    }
    switch (strategy.type) {
      case "text": return text(strategy.value).find();
      case "id": return id(strategy.value).find();
      case "desc": return desc(strategy.value).find();
      case "className": return className(strategy.value).find();
      default: return [];
    }
  },

  /**
   * 多条件组合查找多个控件（AND/OR）
   */
  _findManyByConditions: function (strategy) {
    var conditions = strategy.conditions;
    var logic = strategy.logic || "and";

    if (logic === "or") {
      var results = [];
      var seen = {};
      for (var j = 0; j < conditions.length; j++) {
        var candidates = this._findByCondition(conditions[j]);
        if (!candidates) continue;
        for (var k = 0; k < candidates.length; k++) {
          var el = candidates[k];
          var key = this._elKey(el);
          if (!seen[key]) {
            seen[key] = true;
            results.push(el);
          }
        }
      }
      return results;
    }

    // AND: find all elements that match ALL conditions
    var candidates = this._findByCondition(conditions[0]);
    if (!candidates || candidates.length === 0) return [];

    var results = [];
    for (var m = 0; m < candidates.length; m++) {
      var el = candidates[m];
      var allMatch = true;
      for (var n = 1; n < conditions.length; n++) {
        if (!this._elementMatchesCondition(el, conditions[n])) {
          allMatch = false;
          break;
        }
      }
      if (allMatch) results.push(el);
    }
    return results;
  },

  /** 生成元素去重 key（bounds 中心 + className） */
  _elKey: function (el) {
    try {
      var b = el.bounds();
      return (el.className() || "") + "@" + (b ? (b.centerX() + "," + b.centerY()) : "?");
    } catch (e) { return String(Math.random()); }
  },

  _findByChainAll: function (steps) {
    if (!steps || steps.length === 0) return [];
    // Build selector chain from filter steps (same as _findByChain)
    var sel = null;
    for (var i = 0; i < steps.length; i++) {
      var nav = steps[i].nav || "filter";
      if (nav !== "filter") break;  // only filter steps can build selectors
      if (!sel) { sel = this._makeSelector(steps[i]); }
      else { sel = this._chainSelector(sel, steps[i]); }
      if (!sel) return [];
    }
    return sel ? sel.find() : [];
  },

  /**
   * 使用选择器查找多个控件（仅返回屏幕内的，避免 RecyclerView 离屏元素）
   * @param {string} actionName - 操作名称
   * @param {number} timeout - 超时时间（毫秒），默认 5000
   * @returns {Array} UiObject 数组，找不到返回空数组
   */
  findElements: function (actionName, timeout) {
    timeout = timeout || 5000;
    var selector = selectorLoader.get(actionName);
    if (!selector) {
      logger.error(TAG, "未找到选择器配置: " + actionName);
      return [];
    }

    var strategies = selector.strategies.slice().sort(function (a, b) {
      return a.priority - b.priority;
    });

    var self = this;
    var startTime = Date.now();
    while (Date.now() - startTime < timeout) {
      for (var i = 0; i < strategies.length; i++) {
        var s = strategies[i];
        var all = this._findManyByStrategy(s);
        if (all && all.length > 0) {
          // 只保留屏幕内的元素
          var visible = all.filter(function (el) { return self._isOnScreen(el); });
          if (visible.length > 0) {
            var label = s.conditions ? "conditions(" + (s.logic || "and") + ")" : (s.type || "unknown");
            logger.debug(TAG, "通过 " + label + " 找到 " + visible.length + "/" + all.length + " 个可见元素: '" + actionName + "'");
            return visible;
          }
        }
      }
      sleep(500);
    }

    logger.warn(TAG, "未找到元素列表: " + actionName);
    return [];
  },

  /**
   * 页面检测 — AND 逻辑，所有 strategies 必须同时命中才返回 true
   * 仅对 purpose="page_detect" 的选择器生效
   * @param {string} actionName
   * @param {number} timeout - 每个 strategy 的超时 ms，默认 300
   * @returns {boolean}
   */
  isOnPage: function (actionName, timeout) {
    timeout = timeout || 300;
    var config = selectorLoader.get(actionName);
    if (!config || config.purpose !== "page_detect") return false;
    var strategies = config.strategies;
    if (!strategies || strategies.length === 0) return false;
    var logic = config.strategy_logic || "and";
    var useOr = logic === "or";
    var startTime = Date.now();
    while (Date.now() - startTime < timeout) {
      if (useOr) {
        for (var i = 0; i < strategies.length; i++) {
          if (this._findByStrategy(strategies[i])) return true;
        }
      } else {
        // AND — all strategies must match
        var allMatch = true;
        for (var j = 0; j < strategies.length; j++) {
          if (!this._findByStrategy(strategies[j])) { allMatch = false; break; }
        }
        if (allMatch) return true;
      }
      sleep(100);
    }
    return false;
  },

  /**
   * 检测当前页面 — 遍历所有 page_detect 选择器，按 priority 返回第一个匹配的 action_name
   * @returns {string|null} 页面名，无匹配返回 null
   */
  detectPage: function () {
    var all = selectorLoader._cache;
    var pages = [];
    for (var key in all) {
      if (all[key].purpose === "page_detect") {
        pages.push({ name: key, priority: all[key].priority || 99 });
      }
    }
    pages.sort(function (a, b) { return a.priority - b.priority; });
    for (var i = 0; i < pages.length; i++) {
      if (this.isOnPage(pages[i].name)) {
        return pages[i].name;
      }
    }
    return null;
  },

  /**
   * 通过模板图片在屏幕上查找
   * @param {string} templateFile - 模板文件名（存储在 /sdcard/dy_auto/templates/）
   * @param {number} threshold - 匹配阈值
   * @returns {Object|null} { isImage: true, x, y } 或 null
   */
  _findByImage: function (templateFile, threshold) {
    var res = device.width + "x" + device.height;
    threshold = threshold || 0.8;

    function addCandidate(list, seen, dir, name) {
      if (!dir || !name) return;
      var path = dir + name;
      if (!seen[path]) {
        seen[path] = true;
        list.push({ path: path, name: name });
      }
    }

    function collectCandidates(templateName) {
      var dirs = [
        "/sdcard/dy_auto/templates/" + res + "/",
        "/sdcard/dy_auto/templates/default/",
      ];
      var list = [];
      var seen = {};
      var dot = templateName.lastIndexOf(".");
      var base = dot > 0 ? templateName.substring(0, dot) : templateName;
      var ext = dot > 0 ? templateName.substring(dot) : "";
      var imageExts = { ".png": true, ".jpg": true, ".jpeg": true };

      for (var di = 0; di < dirs.length; di++) {
        var dir = dirs[di];
        addCandidate(list, seen, dir, templateName);
        if (base.indexOf("@") === -1 && ext) {
          addCandidate(list, seen, dir, base + "@" + res + ext);
        }

        try {
          if (!files.isDir(dir)) continue;
          var localFiles = files.listDir(dir);
          for (var fi = 0; fi < localFiles.length; fi++) {
            var fn = localFiles[fi];
            var fnDot = fn.lastIndexOf(".");
            var fnExt = fnDot > 0 ? fn.substring(fnDot).toLowerCase() : "";
            if (!imageExts[fnExt]) continue;
            if (fn.indexOf(base + "@") === 0 || fn.indexOf(base + "_") === 0) {
              addCandidate(list, seen, dir, fn);
            }
          }
        } catch (e) {}
      }
      return list;
    }

    var candidates = collectCandidates(templateFile);

    var screen = images.captureScreen();
    if (!screen) return null;

    for (var ci = 0; ci < candidates.length; ci++) {
      var tpl = images.read(candidates[ci].path);
      if (!tpl) continue;

      // If template is from a different resolution, scale before matching
      // Template filename format: name@1080x2400.png — extract original res
      var matchThreshold = threshold;
      var scaleMatch = candidates[ci].name.match(/@(\d+x\d+)/);
      if (scaleMatch) {
        var origRes = scaleMatch[1];
        if (origRes !== res) {
          var origParts = origRes.split("x");
          var origW = parseInt(origParts[0]) || 1;
          var origH = parseInt(origParts[1]) || 1;
          var scaleX = device.width / origW;
          var scaleY = device.height / origH;
          if (Math.abs(1 - scaleX) > 0.05 || Math.abs(1 - scaleY) > 0.05) {
            var newW = Math.round(tpl.getWidth() * scaleX);
            var newH = Math.round(tpl.getHeight() * scaleY);
            try {
              var scaled = images.scale(tpl, newW, newH);
              if (scaled) { tpl.recycle(); tpl = scaled; matchThreshold = matchThreshold - 0.05; }
            } catch (e) {
              logger.warn(TAG, "模板缩放失败: " + e.message);
            }
          }
        }
      }

      var thresholds = [matchThreshold];
      var relaxed = Math.max(0.65, matchThreshold - 0.10);
      if (relaxed < matchThreshold) thresholds.push(relaxed);

      for (var ti = 0; ti < thresholds.length; ti++) {
        var p = images.findImage(screen, tpl, { threshold: thresholds[ti] });
        if (p) {
          var cx = Math.round(p.x + tpl.getWidth() / 2);
          var cy = Math.round(p.y + tpl.getHeight() / 2);
          tpl.recycle();
          screen.recycle();
          logger.debug(TAG, "图片匹配: " + candidates[ci].name + " threshold=" + thresholds[ti] + " (" + p.x + "," + p.y + ") 中心: (" + cx + "," + cy + ")");
          return { isImage: true, x: cx, y: cy };
        }
      }

      tpl.recycle();
    }

    screen.recycle();
    return null;
  },

  /**
   * 链式查找：按 steps 顺序构建 AutoJS 选择器链
   * 例如 steps: [{type:"className",value:"Button"},{type:"text",value:"视频"}]
   *   等价于 className("Button").text("视频").find()
   * @param {Array} steps
   * @returns {UiObject|null}
   */
  _findByChain: function (steps) {
    if (!steps || steps.length === 0) return null;

    // Phase 1: build selector chain for initial filter steps (nav="filter" or default)
    var sel = null;
    var navStartIdx = steps.length;  // index of first nav step
    for (var i = 0; i < steps.length; i++) {
      var nav = steps[i].nav || "filter";
      if (nav !== "filter") { navStartIdx = i; break; }
      var step = steps[i];
      if (!sel) {
        sel = this._makeSelector(step);
        if (!sel) { logger.debug(TAG, "链式 Phase1: _makeSelector 返回 null, step=" + JSON.stringify(step)); return null; }
      } else {
        sel = this._chainSelector(sel, step);
        if (!sel) { logger.debug(TAG, "链式 Phase1: _chainSelector 返回 null"); return null; }
      }
    }

    // If all steps are filter, just find from selector
    if (navStartIdx >= steps.length) {
      if (!sel) return null;
      var all = sel.find();
      if (all && all.length > 0) {
        for (var j = 0; j < all.length; j++) {
          if (this._isOnScreen(all[j])) return all[j];
        }
      }
      return null;
    }

    // Phase 2: find first matching element from filter chain, then navigate
    var el = null;
    if (sel) {
      var candidates = sel.find();
      logger.debug(TAG, "链式 Phase2: 候选=" + (candidates ? candidates.length : 0) + " 个");
      if (candidates && candidates.length > 0) {
        for (var k = 0; k < candidates.length; k++) {
          if (this._isOnScreen(candidates[k])) { el = candidates[k]; break; }
        }
      }
    } else {
      // First step is a nav step with no prior filter: start from root
      try { el = className("android.widget.FrameLayout").findOne(1000); } catch (e) {}
    }
    if (!el) { logger.debug(TAG, "链式 Phase2: 未找到可见元素 (sel=" + (sel ? "ok" : "null") + ")"); return null; }

    // Phase 3: walk the tree
    for (var m = navStartIdx; m < steps.length; m++) {
      var navStep = steps[m];
      var navAction = navStep.nav || "filter";
      if (navAction === "parent") {
        try { el = el.parent(); } catch (e) { logger.debug(TAG, "链式 Phase3: parent() 异常"); return null; }
        if (!el) { logger.debug(TAG, "链式 Phase3: parent() 返回 null"); return null; }
      } else if (navAction === "child") {
        var childSel = this._makeSelector(navStep);
        if (!childSel) return null;
        try {
          var children = el.find(childSel);
          if (!children || children.length === 0) return null;
          var idx = navStep.index || 0;
          el = null;
          var found = 0;
          for (var c = 0; c < children.length; c++) {
            if (this._isOnScreen(children[c])) {
              if (found === idx) { el = children[c]; break; }
              found++;
            }
          }
          if (!el) return null;
        } catch (e) { return null; }
      } else if (navAction === "sibling") {
        // Go to parent, then find a different child matching the step
        try {
          var parentEl = el.parent();
          if (!parentEl) return null;
          var siblingSel = this._makeSelector(navStep);
          if (!siblingSel) return null;
          var siblings = parentEl.find(siblingSel);
          el = null;
          if (siblings && siblings.length > 0) {
            var sibIdx = navStep.index || 0;
            var sibFound = 0;
            for (var s = 0; s < siblings.length; s++) {
              if (this._isOnScreen(siblings[s])) {
                if (sibFound === sibIdx) { el = siblings[s]; break; }
                sibFound++;
              }
            }
          }
          if (!el) return null;
        } catch (e) { return null; }
      } else if (navAction === "filter") {
        // filter at current element level: check if this element matches
        if (!this._elementMatchesStep(el, navStep)) return null;
      }
    }

    var result = this._isOnScreen(el) ? el : null;
    logger.debug(TAG, "链式 完成: _isOnScreen=" + (result ? "true" : "false"));
    return result;
  },

  _makeSelector: function (step) {
    var contains = step.match_mode === "contains";
    switch (step.type) {
      case "text":      return contains ? textContains(step.value) : text(step.value);
      case "id":        return contains ? idContains(step.value) : id(step.value);
      case "desc":      return contains ? descContains(step.value) : desc(step.value);
      case "className": return contains ? classNameContains(step.value) : className(step.value);
      case "textContains":      return textContains(step.value);
      case "descContains":      return descContains(step.value);
      case "idContains":        return idContains(step.value);
      case "classNameContains": return classNameContains(step.value);
      default: return null;
    }
  },

  _chainSelector: function (sel, step) {
    var contains = step.match_mode === "contains";
    switch (step.type) {
      case "text":      return contains ? sel.textContains(step.value) : sel.text(step.value);
      case "id":        return contains ? sel.idContains(step.value) : sel.id(step.value);
      case "desc":      return contains ? sel.descContains(step.value) : sel.desc(step.value);
      case "className": return contains ? sel.classNameContains(step.value) : sel.className(step.value);
      case "textContains":      return sel.textContains(step.value);
      case "descContains":      return sel.descContains(step.value);
      case "idContains":        return sel.idContains(step.value);
      case "classNameContains": return sel.classNameContains(step.value);
      default: return null;
    }
  },

  _elementMatchesStep: function (el, step) {
    var actual;
    try {
      switch (step.type) {
        case "text": case "textContains": actual = el.text(); break;
        case "desc": case "descContains": actual = el.desc(); break;
        case "id": case "idContains": actual = el.id(); break;
        case "className": case "classNameContains": actual = el.className(); break;
        default: return false;
      }
    } catch (e) { return false; }
    if (!actual) return false;
    var matchMode = step.match_mode || "exact";
    if (matchMode === "contains") return actual.indexOf(step.value) !== -1;
    return actual === step.value;
  },

  /**
   * 点击元素（支持控件点击、坐标点击、图片匹配点击）
   * @param {UiObject} element
   * @returns {boolean}
   */
  clickElement: function (element) {
    if (!element) return false;

    // 按压触摸（press 模式）
    if (element.isPress) {
      logger.debug(TAG, "按压: (" + element.x + ", " + element.y + "), " + (element.duration || 150) + "ms");
      return press(element.x, element.y, element.duration || 150);
    }

    // 坐标点击
    if (element.isCoordinate) {
      logger.debug(TAG, "点击坐标: (" + element.x + ", " + element.y + ")");
      return click(element.x, element.y);
    }

    // 图片匹配点击
    if (element.isImage) {
      logger.debug(TAG, "点击图片匹配: (" + element.x + ", " + element.y + ")");
      return click(element.x, element.y);
    }

    // package 类型 — 仅验证包名，无需点击
    if (element.isPackage) {
      logger.debug(TAG, "package 验证通过: " + element.packageName);
      return true;
    }

    // 控件点击
    if (element.clickable()) {
      return element.click();
    }
    // 控件不可点击，坐标点击
    try {
      var bounds = element.bounds();
      if (bounds) {
        var cx = bounds.centerX();
        var cy = bounds.centerY();
        if (cx >= 0 && cy >= 0 && cx < device.width && cy < device.height) {
          return click(cx, cy);
        }
      }
    } catch (e) {}
    return false;
  },

  /**
   * 输入文本
   * @param {UiObject} element - 输入框控件
   * @param {string} text - 要输入的文本
   * @returns {boolean}
   */
  inputText: function (element, text) {
    if (!element || !text) return false;

    // 点击输入框获取焦点
    if (element.isImage || element.isCoordinate) {
      var x = element.x || Math.round(element.x_percent * device.width);
      var y = element.y || Math.round(element.y_percent * device.height);
      click(x, y);
    } else {
      try { element.click(); } catch (e) { /* ignore */ }
    }
    sleep(500);

    // 优先 setText（最可靠）
    try {
      if (!element.isImage && !element.isCoordinate) {
        element.setText(text);
        logger.debug(TAG, "setText: '" + text.substring(0, 20) + "'");
        return true;
      }
    } catch (e1) { /* ignore */ }

    // 找 EditText 控件 setText
    try {
      var editText = className("EditText").findOne(2000);
      if (editText) {
        editText.setText(text);
        logger.debug(TAG, "EditText.setText: '" + text.substring(0, 20) + "'");
        return true;
      }
    } catch (e2) { /* ignore */ }

    // 最后兜底: 剪贴板粘贴
    try {
      setClip(text);
      sleep(200);
      try { shell("input keyevent 279", false); } catch (e3) { /* ignore */ }
      sleep(200);
      logger.debug(TAG, "剪贴板粘贴: '" + text.substring(0, 20) + "'");
      return true;
    } catch (e5) {
      logger.warn(TAG, "所有输入方式均失败");
    }
    return false;
  },

  /**
   * 通过键盘回车提交（多种方式尝试，回退点击提交按钮）
   * @param {string} submitActionName - 提交按钮的动作名（回退方案）
   * @returns {boolean}
   */
  submitViaKeyboard: function (submitActionName) {
    // 尝试键盘回车
    try { shell("input keyevent 66", false); sleep(300); return true; } catch (e1) { /* ignore */ }

    // 回退: 点击提交按钮
    if (submitActionName) {
      try {
        var selectorLoader = require("./selector-loader");
        var selector = selectorLoader.get(submitActionName);
        if (selector) {
          var btn = this.findElement(submitActionName, 2000);
          if (btn) { this.clickElement(btn); sleep(500); return true; }
        }
      } catch (e3) { /* ignore */ }
    }

    logger.warn(TAG, "回车提交和按钮提交均失败");
    return false;
  },

  /**
   * 执行上滑操作（浏览下一条视频）
   * @returns {boolean}
   */
  swipeUp: function () {
    var startX = device.width * (0.35 + Math.random() * 0.2);         // 35%-55% 屏宽
    var startY = device.height * (0.6 + Math.random() * 0.1);         // 60%-70% 屏高
    var endX = startX + Math.floor(Math.random() * 30 + 20);           // 微微右上 +20~50px
    var endY = device.height * (0.35 + Math.random() * 0.1);          // 35%-45% 屏高
    var duration = Math.floor(Math.random() * 200 + 300);              // 300-500ms
    gestures([0, duration, [startX, startY], [endX, endY]]);
  },

  /**
   * 通过模板图片在屏幕上查找并点击（以图找图）
   * 用于无障碍服务无法定位的自定义控件（如弹出框）
   * @param {string} templatePath - 模板图片路径
   * @param {Object} options - { threshold, region }
   * @returns {boolean} 是否找到并点击
   */
  findImageClick: function (templatePath, options) {
    options = options || {};
    var threshold = options.threshold || 0.8;

    var tpl = images.read(templatePath);
    if (!tpl) {
      logger.error(TAG, "模板图片未找到: " + templatePath);
      return false;
    }

    var screen = images.captureScreen();
    if (!screen) {
      tpl.recycle();
      logger.error(TAG, "截屏失败");
      return false;
    }

    var findOptions = { threshold: threshold };
    if (options.region) {
      findOptions.region = options.region;
    }

    var p = images.findImage(screen, tpl, findOptions);

    if (p) {
      var cx = p.x + tpl.getWidth() / 2;
      var cy = p.y + tpl.getHeight() / 2;
      logger.info(TAG, "图片匹配: (" + p.x + "," + p.y + ") 点击: (" + cx + "," + cy + ")");
      click(cx, cy);
      tpl.recycle();
      screen.recycle();
      return true;
    }

    logger.warn(TAG, "图片未匹配: " + templatePath);
    tpl.recycle();
    screen.recycle();
    return false;
  },

  /**
   * 从控件提取值（按选择器配置的 extract_field 读取属性）
   * @param {UiObject} element - 已找到的控件
   * @param {Object} selector - 选择器配置 (含 purpose, extract_field, clean_mode, clean_pattern, clean_prompt)
   * @returns {string|null} 提取并清洗后的值
   */
  extractValue: function (element, selector) {
    if (!element || !selector || selector.purpose !== "extract") return null;

    var field = selector.extract_field || "text";
    var rawValue = null;
    try {
      switch (field) {
        case "text": rawValue = element.text(); break;
        case "desc": rawValue = element.desc(); break;
        case "id": rawValue = element.id(); break;
        case "className": rawValue = element.className(); break;
        default: return null;
      }
    } catch (e) {
      logger.warn(TAG, "提取值失败: " + e.message);
      return null;
    }

    if (!rawValue) return "";

    var cleanMode = selector.clean_mode || "raw";
    if (cleanMode === "raw") return rawValue;

    // 正则清洗
    if (cleanMode === "regex" && selector.clean_pattern) {
      try {
        var re = new RegExp(selector.clean_pattern);
        var match = rawValue.match(re);
        return match ? (match[1] || match[0]) : rawValue;
      } catch (e) {
        logger.warn(TAG, "正则清洗失败: " + e.message);
        return rawValue;
      }
    }

    // AI 清洗
    if (cleanMode === "ai" && selector.clean_prompt) {
      try {
        var promptText = selector.clean_prompt + "\n\n原始数据：" + rawValue;
        var result = apiClient.post("/api/device/ai-proxy", {
          prompt: promptText,
          max_tokens: 128,
          temperature: 0.2,
        });
        if (result && result.content) {
          logger.debug(TAG, "AI 清洗: '" + rawValue.substring(0, 20) + "' -> '" + result.content.substring(0, 20) + "'");
          return result.content.trim();
        }
      } catch (e) {
        logger.warn(TAG, "AI 清洗失败: " + e.message);
      }
      return rawValue;
    }

    return rawValue;
  },

  /**
   * 截取当前页面控件树快照（用于选择器调试）

   * @returns {Object} 控件树摘要
   */
  captureUISnapshot: function () {
    var snapshot = { elements: [] };
    try {
      var allElements = className("android.widget.TextView").find();
      for (var i = 0; i < Math.min(allElements.length, 50); i++) {
        var el = allElements[i];
        snapshot.elements.push({
          text: el.text() || "",
          id: el.id() || "",
          desc: el.desc() || "",
          className: el.className() || "",
          bounds: el.bounds() ? {
            left: el.bounds().left,
            top: el.bounds().top,
            right: el.bounds().right,
            bottom: el.bounds().bottom,
          } : null,
        });
      }
    } catch (e) {
      logger.warn(TAG, "截取界面快照失败: " + e.message);
    }
    return snapshot;
  },
};

module.exports = uiOperator;
```

## core\ai-analyzer.js

```javascript
// device/core/ai-analyzer.js
var config = global.__config || require("../config");
var apiClient = require("./api-client");
var promptsConfig = require("./prompts-config");
var logger = require("../utils/logger");

var TAG = "AI";

/**
 * 设备端 AI 分析模块
 * 通过服务端代理调用 AI，设备端不持有 API Key
 * 行业相关提示词统一在 prompts-config.js 管理
 */
var aiAnalyzer = {
  SCORE_THRESHOLD: 40,

  /**
   * 加载服务端提示词模板（从 promptTemplateLoader 缓存中查找）
   * 不传 id 或找不到时回退到 prompts-config.js 本地配置
   * @param {string} [id] — 模板 ID
   */
  useTemplate: function (id) {
    var loader = require("./prompt-template-loader");
    var tmpl = id ? loader.get(id) : null;
    if (tmpl && tmpl.content) {
      var ok = promptsConfig.setOverride(tmpl.content);
      if (ok) {
        promptsConfig.setIndustry(tmpl.industry || "health");
        logger.info(TAG, "使用服务端模板: " + tmpl.name + " (" + (tmpl.industry || "") + ")");
      } else {
        promptsConfig.setOverride(null);
        promptsConfig.setIndustry("health");
        this._destCache = {};
        logger.warn(TAG, "模板 " + tmpl.name + " 校验失败，回退本地配置");
      }
    } else {
      promptsConfig.setOverride(null);
      promptsConfig.setIndustry("health");
      this._destCache = {};
      if (id) logger.warn(TAG, "模板 " + id + " 未找到，使用本地默认配置");
    }
  },

  /**
   * 切换行业（本地配置）
   * @param {string} name — 行业标识，如 "health" / "travel"
   */
  setIndustry: function (name) {
    if (promptsConfig.industry !== name) this._destCache = {};
    promptsConfig.setIndustry(name);
    logger.info(TAG, "切换行业: " + (promptsConfig.get().name || name));
  },

  getIndustry: function () {
    return promptsConfig.industry;
  },

  _destCache: {},

  resolveDestination: function (keyword) {
    if (promptsConfig.industry !== "travel") return null;
    if (!keyword) return null;
    if (this._destCache[keyword]) return this._destCache[keyword];

    var prompt = [
      "将以下旅游关键词解析为目的地信息。",
      "关键词：" + keyword,
      "请输出一个 JSON：",
      "{\"province\": \"省份\", \"city\": \"城市\", \"attraction\": \"景点\"}",
      "如果关键词本身是省份或城市，对应字段填空字符串，其余字段正常填写。",
      "只输出 JSON，不要其他文本。"
    ].join("\n");

    var content = this._callAI(prompt, 200, 0.1);
    if (!content) return null;

    try {
      var jsonMatch = content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        var data = JSON.parse(jsonMatch[0]);
        this._destCache[keyword] = data;
        logger.info(TAG, "目的地解析: " + keyword + " → " + JSON.stringify(data));
        return data;
      }
    } catch (e) {
      logger.warn(TAG, "目的地解析失败: " + keyword + " " + e.message);
    }
    return null;
  },

  /**
   * 调用服务端 AI 代理
   */
  _callAI: function (prompt, maxTokens, temperature) {
    if (!config.serverUrl || !config.deviceSecret) {
      logger.error(TAG, "设备未配对，无法调用 AI");
      return null;
    }

    try {
      var result = apiClient.post("/api/device/ai-proxy", {
        prompt: prompt,
        max_tokens: maxTokens || 4096,
        temperature: temperature != null ? temperature : 0.7,
      }, 120000);  // AI 生成最长等 2 分钟

      if (!result || !result.content) {
        logger.error(TAG, "AI 代理返回空内容");
        return null;
      }
      return result.content.trim();
    } catch (e) {
      logger.error(TAG, "AI 代理调用失败: " + e.message);
      return null;
    }
  },

  /**
   * 分析单条评论
   */
  analyzeComment: function (params) {
    var searchKeyword = params.searchKeyword;
    var nickname = params.nickname;
    var commentText = params.commentText;

    if (!commentText) {
      logger.warn(TAG, "Empty comment text");
      return null;
    }

    var prompt = this._buildAnalysisPrompt(searchKeyword, nickname, commentText);
    var content = this._callAI(prompt, 1024, 0.3);
    if (!content) {
      logger.warn(TAG, "AI analysis failed");
      return null;
    }

    var result = this._parseAnalysisResponse(content);
    if (!result) {
      logger.warn(TAG, "AI 解析失败，重试一次");
      content = this._callAI(prompt, 256, 0.3);
      if (content) {
        result = this._parseAnalysisResponse(content);
      }
    }
    return result;
  },

  /**
   * 解析 AI 分析响应
   */
  _parseAnalysisResponse: function (content) {
    try {
      var jsonMatch = content.match(/\{[\s\S]*\}/);
      if (!jsonMatch) {
        logger.error(TAG, "No JSON found in AI response");
        return null;
      }

      var data = JSON.parse(jsonMatch[0]);

      if (typeof data.score !== "number" || !data.reply) {
        logger.error(TAG, "Invalid AI response structure");
        return null;
      }

      data.reply = data.reply.replace(/^["'「]|["'」]$/g, "");
      return data;
    } catch (e) {
      logger.error(TAG, "Parse AI response failed: " + e.message);
      return null;
    }
  },

  /**
   * 本地关键词预过滤
   */
  _localRelevanceCheck: function (text) {
    if (!text) return null;
    var t = text.toLowerCase();
    var filter = promptsConfig.get().localFilter;

    var excludePatterns = filter.exclude;
    for (var i = 0; i < excludePatterns.length; i++) {
      if (t.indexOf(excludePatterns[i]) !== -1) return false;
    }

    var includePatterns = filter.include;
    for (var j = 0; j < includePatterns.length; j++) {
      if (t.indexOf(includePatterns[j]) !== -1) return true;
    }

    return null;
  },

  /**
   * 检查当前内容是否与目标领域相关
   */
  checkRelevance: function (contentText, domain) {
    if (!contentText || contentText.length < 2) return true;

    var localResult = this._localRelevanceCheck(contentText);
    if (localResult !== null) {
      logger.info(TAG, "本地预过滤: " + (localResult ? "相关" : "不相关") + " — " + contentText.substring(0, 30));
      return localResult;
    }

    domain = domain || promptsConfig.get().domain;

    var prompt = "判断以下抖音视频内容是否与" + domain + "领域相关。\n\n" +
      "内容：" + contentText.substring(0, 300) + "\n\n" +
      "只回答一个JSON：{\"related\": true/false, \"reason\": \"简短原因\"}";

    var content = this._callAI(prompt, 100, 0.1);
    if (!content) {
      logger.warn(TAG, "内容判断失败，默认放行");
      return true;
    }

    try {
      var jsonMatch = content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        var data = JSON.parse(jsonMatch[0]);
        logger.info(TAG, "内容相关性: " + (data.related ? "相关" : "不相关") + " - " + (data.reason || ""));
        return !!data.related;
      }
    } catch (e) {
      logger.warn(TAG, "内容判断解析失败: " + e.message);
    }
    return true;
  },

  // 兼容旧方法名
  checkHealthRelevance: function (contentText, domain) {
    return this.checkRelevance(contentText, domain);
  },

  /**
   * 根据视频内容生成评论
   */
  generateVideoComment: function (videoText) {
    if (!videoText || videoText.length < 2) {
      logger.warn(TAG, "视频文本太短，无法生成评论");
      return null;
    }

    var vc = promptsConfig.get().videoComment;
    var dw = promptsConfig.get().disabledWords;

    var prompt = vc.context + "\n\n" +
      "## 你的目标\n" + (vc.goal || "写一条自然真实的评论") + "\n\n" +
      "## 要求\n" +
      "- " + vc.rules.join("\n- ") + "\n" +
      "- 严禁禁用词：" + dw + "\n\n" +
      "## 视频内容\n" + videoText.substring(0, 500) + "\n\n" +
      "只输出评论文本，不要引号、不要其他解释。";

    var text = this._callAI(prompt, 200, 0.8);
    if (text) {
      text = text.replace(/^["'「]|["'」]$/g, "");
      logger.info(TAG, "AI 生成评论: '" + text.substring(0, 30) + "'");
    }
    return text;
  },

  /**
   * 生成私信 — opener 阶段（破冰）
   */
  generateDM: function (params) {
    var searchKeyword = params.searchKeyword || "";
    var nickname = params.nickname || "";
    var commentText = params.commentText || "";
    var tier = params.tier || "other";
    var videoText = params.videoText || "";
    var intendedCity = params.intendedCity || params.intended_city || "";

    var dm = promptsConfig.get().dmOpener;
    var dw = promptsConfig.get().disabledWords;
    // DM 专用身份优先，回退顶层身份
    var dmId = dm.identity || promptsConfig.get().identity;
    // dmOpener.identity 兼容两种格式: {role, constraints} 对象 或 字符串列表
    var dmRole, dmConstraints;
    if (dmId instanceof Array) {
      dmRole = dmId[0] || "";
      dmConstraints = dmId.slice(1);
    } else {
      dmRole = dmId.role || "";
      dmConstraints = dmId.constraints || [];
    }

    var prompt = dm.context + "\n\n" +
      "## 绝对禁用词（任何情况下不得出现）\n" + dw + "\n\n" +
      "## 身份设定\n" +
      "- 你是" + dmRole + "\n" +
      "- " + dmConstraints.join("\n- ") + "\n" +
      "- **严禁自我代入**：不要用\"我都是…\"、\"我自己…\"、\"我家…\"等第一人称经验分享。\n" +
      "- 使用建议/指南风格：用\"可以尝试\"、\"建议\"、\"若想…\"等客观建议句式。\n\n" +
      "## 这一条是破冰，唯一目标\n" + dm.goal + "\n\n" +
      "## 风格\n" +
      "- " + dm.style.join("\n- ") + "\n\n" +
      "根据 tier 选择语气：\n" +
      "- strong_buy: " + (dm.tierTones.strong_buy || "") + "\n" +
      "- health_consult: " + (dm.tierTones.health_consult || dm.tierTones.travel_consult || "") + "\n" +
      "- patient_self: " + (dm.tierTones.patient_self || dm.tierTones.strong_buy || "") + "\n" +
      "- other: " + (dm.tierTones.other || "") + "\n\n" +
      "## 输入\n" +
      "- 搜索词：" + searchKeyword + "\n" +
      "- 对方昵称：" + nickname + "\n" +
      (commentText ? "- 对方的评论：" + commentText + "\n" : "") +
      (videoText ? "- 视频内容：" + videoText.substring(0, 300) + "\n" : "") +
      (intendedCity ? "- 对方意向目的地：" + intendedCity + "\n" : "") +
      "- 命中分层：" + tier + "\n\n" +
      "请输出一条开场白，**只输出消息文本本身，不要引号、不要解释**。";

    var text = this._callAI(prompt, 200, 0.8);
    if (text) {
      text = text.replace(/^["'「]|["'」]$/g, "");
      logger.info(TAG, "AI 生成私信(opener): '" + text.substring(0, 30) + "'");
    }
    return text;
  },

  /**
   * 根据视频内容生成私信（兼容旧接口）
   */
  generateVideoDM: function (videoText) {
    return this.generateDM({ videoText: videoText });
  },

  /**
   * 多阶段私信生成
   */
  generateDMStage: function (stage, params) {
    var stages = promptsConfig.get().dmStages;
    var cfg = stages[stage];
    if (!cfg) { logger.warn(TAG, "未知私信阶段: " + stage); return null; }

    var dw = promptsConfig.get().disabledWords;
    var dmId = promptsConfig.get().dmOpener.identity || promptsConfig.get().identity;
    var dmRole2 = dmId instanceof Array ? (dmId[0] || "") : (dmId.role || "");

    var prompt = "你是" + dmRole2 + "，与对方私信已有互动。当前阶段：" + cfg.name + "。\n\n" +
      "## 禁用词（强制）\n" + dw + "\n\n" +
      "## 阶段目标\n" + cfg.goal + "\n\n" +
      "## 风格\n" + cfg.style + "\n\n" +
      "- **严禁自我代入**：不要用\"我家…\"\"我也是…\"\"我自己…\"等第一人称经验分享。\n" +
      "- 不给医嘱，不指导用药。\n\n" +
      "## 输入\n" +
      "- 搜索词：" + (params.searchKeyword || "") + "\n" +
      "- 对方昵称：" + (params.nickname || "") + "\n" +
      (params.silentDays ? "- 沉默天数：" + params.silentDays + "\n" : "") +
      "- 最近对话：\n" + (params.history || "(首轮对话)") + "\n\n" +
      "请**只输出消息文本本身**，不要引号、不要解释。";

    var text = this._callAI(prompt, cfg.maxTokens, 0.7);
    if (text) {
      text = text.replace(/^["'「]|["'」]$/g, "");
      logger.info(TAG, "AI 私信(" + stage + "): '" + text.substring(0, 30) + "'");
    }
    return text;
  },

  /**
   * 构建五维度分析提示词 — 从 prompts-config 拼接
   */
  _buildAnalysisPrompt: function (searchKeyword, nickname, commentText) {
    var p = promptsConfig.get();
    var id = p.identity;
    var dw = p.disabledWords;
    var sg = p.semanticGuide;
    var an = p.analysis;

    // 语义分析指南
    var highList = sg.highValueSignals.map(function (s, i) { return (i + 1) + ". " + s; }).join("\n");
    var lowList = sg.lowValueSignals.map(function (s, i) { return (i + 1) + ". " + s; }).join("\n");
    var exList = sg.keyExamples.join("\n");

    // 五维度
    var intents = an.intents.map(function (s) { return "- " + s; }).join("\n");
    var sentiments = an.sentiments.map(function (s) { return "- " + s; }).join("\n");
    var scoring = an.scoringRules.map(function (s) { return "- " + s; }).join("\n");
    var replyRules = an.replyRules.map(function (s) { return "- " + s; }).join("\n");

    // tier 语气
    var tierLines = [];
    for (var tierKey in an.tiers) {
      tierLines.push("- " + tierKey + ": " + an.tiers[tierKey]);
    }
    var tierText = tierLines.join("\n");

    return "你具有评论语义分析能力。当前视频的搜索关键词是【" + searchKeyword + "】，它代表了视频的主题和内容方向，评论与关键词关联越紧密，越可能是有真实需求的用户。\n\n" +
      "## 身份设定\n" +
      "- 你是" + id.role + "\n" +
      "- " + id.constraints.join("\n- ") + "\n" +
      "- **严禁自我代入**：不要用\"我都是…\"、\"我自己…\"、\"我家…\"等第一人称经验分享。\n" +
      "- 使用建议/指南风格：用\"可以试试\"、\"建议\"、\"若想…\"等客观建议句式。\n\n" +
      "## 绝对禁用词（任何情况下不得出现）\n" + dw + "\n\n" +
      "## 语义分析指南 — 先理解评论再打分\n\n" +
      "你的核心任务是判断：**" + sg.mission + "**。\n\n" +
      "### 高价值信号（满足任一即说明评论者有真实需求）：\n" + highList + "\n\n" +
      "### 低价值信号（不是真实需求）：\n" + lowList + "\n\n" +
      "### 关键区分示例：\n" + exList + "\n\n" +
      "## 五维度分析模型\n\n" +
      "### 1. 意图识别 (intent)\n" + intents + "\n\n" +
      "### 2. 情感倾向 (sentiment)\n" + sentiments + "\n\n" +
      "### 3. 关注实体 (focus)\n" +
      "- price (价格) / quality (功效/质量) / location (地域) / other\n\n" +
      "### 4. 用户画像 (profile)\n" +
      "- role: 宝妈、上班族、退休老人、学生等\n" +
      "- spending: low / mid / high\n\n" +
      "### 5. 线索质量 (lead_quality)\n" +
      "- urgency (1-10): 提及具体需求，或语气急切/痛苦 → 至少 7\n" +
      "- specific_condition (是否提及具体需求关键词): 评论包含行业相关的具体关键词 → true\n" +
      "- is_bot / is_competitor\n\n" +
      "## 评分规则\n" + scoring + "\n\n" +
      "## 回复生成规则\n" + replyRules + "\n" +
      "- **回复正文不要加「回复 @昵称」前缀，系统会自动显示**\n" +
      "- 输出示例：✅ \"" + an.replyExample.good + "\" | ❌ \"" + an.replyExample.bad + "\"\n\n" +
      "根据 tier 选择语气：\n" + tierText + "\n\n" +
      "## 输入\n" +
      "- 搜索词：" + searchKeyword + "\n" +
      "- 对方昵称：" + nickname + "\n" +
      "- 对方的评论：" + commentText + "\n\n" +
      "## 输出格式（严格 JSON）\n" +
      "{\n" +
      "  \"score\": 75,\n" +
      "  \"tier\": \"high\",\n" +
      "  \"dimensions\": {\n" +
      "    \"intent\": \"health_consult\",\n" +
      "    \"sentiment\": \"neutral\",\n" +
      "    \"focus\": \"quality\",\n" +
      "    \"profile\": { \"role\": \"unknown\", \"spending\": \"mid\" },\n" +
      "    \"lead_quality\": { \"urgency\": 8, \"specific_condition\": true, \"is_bot\": false, \"is_competitor\": false }\n" +
      "  },\n" +
      "  \"reply\": \"" + an.replyExample.good + "\"\n" +
      "}\n\n" +
      "tier 规则：score >= 70 为 \"high\"，40-69 为 \"medium\"，< 40 为 \"low\"\n" +
      "intent 必须是以下之一（根据 tier 语气说明选择最匹配的）：\"" + Object.keys(an.tiers).join("\" / \"") + "\"\n" +
      "请直接输出 JSON，不要其他文本。";
  },
};

module.exports = aiAnalyzer;
```

## core\calibrator.js

```javascript
/**
 * 自动标定 — 为新分辨率设备采集 image 模板
 *
 * 工作流程：
 * 1. 遍历所有选择器，找出有 coordinate 策略的 action
 * 2. 对每个 coordinate 策略，截图 → 按 x_percent/y_percent 裁剪区域 → 保存 PNG
 * 3. 批量上传到服务端，自动创建对应 resolution_profile 的选择器行
 *
 * 调用时机：selectorLoader.init() 完成后，若 _cache 中缺少 action（无匹配 profile）
 *
 * 页面验证：每页采集前通过 uiOperator.detectPage() 验证当前页面指纹，
 * 避免无人值守时将错误页面截图上传为模板。
 */

var selectorLoader = require("./selector-loader");
var apiClient = require("./api-client");
var uiOperator = require("./ui-operator");
var logger = require("../utils/logger");

var TAG = "标定";

function ensureDirPath(dir) {
  if (!dir) return false;
  try {
    var f = new java.io.File(String(dir));
    if (!f.exists()) f.mkdirs();
    return f.exists() && f.isDirectory();
  } catch (e) {
    logger.warn(TAG, "目录创建失败: " + dir + " - " + e.message);
    return false;
  }
}

var calibrator = {
  /**
   * 运行标定流程
   * @param {Object} options
   *   - pageKey: string (可选) — 只标定指定页面的 actions
   *     "search" | "video" | "comment" | "profile" | "dm"
   *   - unattended: boolean (内部) — 自动触发时跳过 toast 导航提示
   * @returns {{ captured: number, uploaded: number, errors: string[] }}
   */
  run: function (options) {
    options = options || {};
    var resolution = device.width + "x" + device.height;
    var unattended = !!options.unattended;
    logger.info(TAG, "开始标定, 分辨率=" + resolution + (unattended ? " (自动)" : " (手动)"));

    var results = { captured: 0, uploaded: 0, errors: [] };

    // 五个页面分组，按顺序引导用户导航
    var pages = [
      { key: "search",  label: "请打开抖音搜索页（点击搜索图标进入搜索）", detectKey: "search" },
      { key: "video",   label: "请打开一个视频（进入视频详情页）",        detectKey: "video" },
      { key: "comment", label: "请打开视频评论区（点击评论按钮进入评论区）", detectKey: "comment" },
      { key: "profile", label: "请进入一个用户主页（点击头像进入个人主页）", detectKey: "profile" },
      { key: "dm",      label: "请打开私信聊天页（点击私信按钮进入私信）",   detectKey: "dm" },
    ];

    for (var pi = 0; pi < pages.length; pi++) {
      var page = pages[pi];
      var targets = this._collectCoordinateActions(page.key);
      if (targets.length === 0) {
        logger.info(TAG, "页面[" + page.key + "] 无 coordinate 策略，跳过");
        continue;
      }

      // 页面指纹验证——无人值守时不依赖用户手动导航
      if (unattended) {
        if (!this._verifyPage(page.detectKey)) {
          logger.warn(TAG, "自动标定: 页面[" + page.key + "] 指纹不匹配，跳过");
          continue;
        }
        logger.info(TAG, "自动标定: 页面[" + page.key + "] 指纹验证通过");
      } else {
        toast(page.label + " (" + (pi + 1) + "/" + pages.length + ")");
        logger.info(TAG, "等待导航到: " + page.key + " (" + targets.length + " 个元素)");
        sleep(5000);
        if (!this._verifyPage(page.detectKey)) {
          logger.warn(TAG, "手动标定: 页面[" + page.key + "] 指纹不匹配，跳过");
          continue;
        }
      }

      // 采集当前页面元素
      var uploads = [];
      for (var i = 0; i < targets.length; i++) {
        var t = targets[i];
        try {
          var templateData = this._captureTemplate(t.action_name, t.x_percent, t.y_percent, resolution);
          if (templateData) {
            uploads.push(templateData);
            results.captured++;
            logger.info(TAG, "[" + page.key + "] " + t.action_name + " (" + (i + 1) + "/" + targets.length + ")");
          }
        } catch (e) {
          results.errors.push(t.action_name + ": " + e.message);
          logger.warn(TAG, "采集失败: " + t.action_name + " - " + e.message);
        }
      }

      // 每页采集完立即上传
      if (uploads.length > 0) {
        try {
          var uploadResult = apiClient.uploadCalibration(uploads, resolution);
          if (uploadResult && uploadResult.uploaded) {
            results.uploaded += uploadResult.uploaded;
          }
        } catch (e) {
          results.errors.push("上传失败(" + page.key + "): " + e.message);
        }
      }

      logger.info(TAG, "页面[" + page.key + "] 完成: " + uploads.length + " 个模板");
    }

    toast("标定完成！采集=" + results.captured + " 上传=" + results.uploaded);
    logger.info(TAG, "标定完成: 采集=" + results.captured + ", 上传=" + results.uploaded + ", 错误=" + results.errors.length);
    return results;
  },

  /**
   * 验证当前页面指纹匹配目标页面
   * 通过 uiOperator.detectPage() 返回的 page_detect 名称模糊匹配
   */
  _verifyPage: function (detectKey) {
    try {
      var detected = uiOperator.detectPage();
      if (!detected) return false;
      return detected.indexOf(detectKey) !== -1;
    } catch (e) {
      logger.warn(TAG, "页面验证异常: " + e.message);
      return false;
    }
  },

  /**
   * 收集所有包含 coordinate 策略的 action
   */
  _collectCoordinateActions: function (pageKey) {
    var targets = [];
    var cache = selectorLoader._cache;

    // Page → action mapping for filtering
    var pageActions = {
      "search": ["search_tab", "search_button", "search_video_tab", "sort_button", "search_video_list"],
      "video": ["video_comment_btn", "like_button", "video_author_avatar", "off_video", "comment_off_btn", "is_shopping_cart"],
      "comment": ["comment_author_avatar", "comment_submit", "comment_list", "video_comment_input", "comment_reply_button", "comment_input"],
      "profile": ["follow_button", "dm_entry_btn", "user_nickname", "user_is_private", "is_follow"],
      "dm": ["dm_input", "dm_send"],
    };

    for (var actionName in cache) {
      if (!cache.hasOwnProperty(actionName)) continue;
      var sel = cache[actionName];
      if (!sel.strategies) continue;

      // Filter by page if specified
      if (pageKey) {
        var allowed = false;
        for (var pk in pageActions) {
          if (!pageActions.hasOwnProperty(pk)) continue;
          if (pk === pageKey && pageActions[pk].indexOf(actionName) !== -1) {
            allowed = true;
            break;
          }
        }
        if (!allowed) continue;
      }

      for (var i = 0; i < sel.strategies.length; i++) {
        var st = sel.strategies[i];
        if (st.type === "coordinate" && typeof st.x_percent === "number" && typeof st.y_percent === "number") {
          targets.push({
            action_name: actionName,
            x_percent: st.x_percent,
            y_percent: st.y_percent,
          });
          break; // 每个 action 只取第一个 coordinate 策略
        }
      }
    }
    return targets;
  },

  /**
   * 截图并裁剪模板区域
   * @returns {{ action_name, filename, data: bytes } | null}
   */
  _captureTemplate: function (actionName, xPercent, yPercent, resolution) {
    var screen = images.captureScreen();
    if (!screen) {
      logger.warn(TAG, "截图失败: " + actionName);
      return null;
    }

    var cx = Math.round(xPercent * device.width);
    var cy = Math.round(yPercent * device.height);

    // 裁剪区域：以坐标为中心，取 10% 最小维度的弹性区域（±20% padding）
    var cropSize = Math.round(Math.min(device.width, device.height) * 0.10);
    cropSize = Math.max(40, Math.min(cropSize, 120));
    var left = Math.max(0, cx - cropSize);
    var top = Math.max(0, cy - cropSize);
    var w = Math.min(cropSize * 2, screen.getWidth() - left);
    var h = Math.min(cropSize * 2, screen.getHeight() - top);

    var tpl = null;
    try {
      tpl = images.clip(screen, left, top, w, h);
      screen.recycle();
      if (!tpl) return null;

      var filename = actionName + "@" + resolution + ".png";
      var tmpPath = "/sdcard/dy_auto/templates/" + resolution + "/" + filename;
      ensureDirPath("/sdcard/dy_auto/templates/" + resolution + "/");
      images.save(tpl, tmpPath, "png", 80);
      var data = files.readBytes(tmpPath);
      tpl.recycle();

      return {
        action_name: actionName,
        filename: filename,
        data: data,
        resolution: resolution,
      };
    } catch (e) {
      if (tpl) tpl.recycle();
      if (screen) { try { screen.recycle(); } catch (e2) {} }
      throw e;
    }
  },
};

module.exports = calibrator;
```

## core\device-ws.js

```javascript
// device/core/device-ws.js
// 设备状态 WebSocket — 保持持久连接，接收服务端推送（任务、选择器、配置等）

var config = global.__config || require("../config");
var logger = require("../utils/logger");

var TAG = "设备WS";

var deviceWs = {
  _ws: null,
  _client: null,         // 复用同一个 OkHttpClient，避免线程池泄漏
  _connected: false,
  _stopped: false,
  _reconnectTimer: null,
  _reconnectDelay: 3000,
  _pingTimer: null,
  _onAuthFailure: null,
  _onConnected: null,

  // 推送消息回调
  _callbacks: {
    onTask: null,             // function(task)
    onCancelTask: null,       // function(taskId)
    onSelectorsUpdated: null, // function(version)
    onConfigUpdated: null,    // function(config, proxy)
    onDeviceRemoved: null,    // function() — 设备被服务端移除
  },

  /**
   * 设置推送消息回调
   */
  setCallbacks: function (callbacks) {
    for (var key in callbacks) {
      if (callbacks.hasOwnProperty(key)) {
        this._callbacks[key] = callbacks[key];
      }
    }
  },

  /**
   * 设置认证失败回调
   */
  setAuthFailureHandler: function (callback) {
    this._onAuthFailure = callback;
  },

  /**
   * 设置连接成功回调（用于重连后重新 poll）
   */
  setOnConnectedHandler: function (callback) {
    this._onConnected = callback;
  },

  /**
   * 启动设备状态 WS 连接
   */
  start: function () {
    this._stopped = false;
    this._connect();
  },

  /**
   * 停止 WS 连接
   */
  stop: function () {
    this._stopped = true;
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    // 通知服务端主动断开，避免等待 TCP 超时
    this.sendDisconnect();
    if (this._ws) {
      try {
        this._ws.close(1000, "shutdown");
      } catch (e) { /* ignore */ }
    }
    this._cleanup();
    // 不清除 _client — 复用同一个 OkHttpClient 避免线程池泄漏
    logger.info(TAG, "已停止");
  },

  /**
   * 发送断开通知给服务端，让服务端立即标记离线
   */
  sendDisconnect: function () {
    if (this._ws && this._connected) {
      try {
        this._ws.send(JSON.stringify({ event: "device_disconnect" }));
      } catch (e) { /* ignore — connection may already be dead */ }
    }
  },

  /**
   * 是否已连接
   */
  isConnected: function () {
    return this._connected;
  },

  /**
   * 处理服务端推送消息
   */
  _handleMessage: function (text) {
    try {
      var msg = JSON.parse(text);
      var event = msg.event;
      if (!event) {
        logger.debug(TAG, "收到无 event 字段的消息: " + text);
        return;
      }

      switch (event) {
        case "task":
          logger.info(TAG, "收到推送任务: " + (msg.task ? msg.task.id : "?"));
          if (this._callbacks.onTask) this._callbacks.onTask(msg.task);
          break;
        case "cancel_task":
          logger.info(TAG, "收到取消任务: " + msg.task_id);
          if (this._callbacks.onCancelTask) this._callbacks.onCancelTask(msg.task_id);
          break;
        case "selectors_updated":
          logger.info(TAG, "选择器已更新: v" + msg.version);
          if (this._callbacks.onSelectorsUpdated) this._callbacks.onSelectorsUpdated(msg.version);
          break;
        case "prompt_templates_updated":
          logger.info(TAG, "提示词模板已更新: v" + msg.version);
          if (this._callbacks.onPromptTemplatesUpdated) this._callbacks.onPromptTemplatesUpdated(msg.version);
          break;
        case "config_updated":
          logger.info(TAG, "配置已更新");
          if (this._callbacks.onConfigUpdated) this._callbacks.onConfigUpdated(msg.config, msg.proxy);
          break;
        case "device_removed":
          logger.warn(TAG, "设备已被服务端移除");
          if (this._callbacks.onDeviceRemoved) this._callbacks.onDeviceRemoved();
          break;
        case "new_task_available":
          logger.info(TAG, "有新任务可用，执行 catch-up poll");
          if (this._callbacks.onNewTaskAvailable) this._callbacks.onNewTaskAvailable();
          break;
        default:
          logger.debug(TAG, "未知事件: " + event);
      }
    } catch (e) {
      logger.warn(TAG, "消息处理失败: " + e.message);
    }
  },

  _connect: function () {
    if (!config.serverUrl || !config.deviceSecret) {
      logger.debug(TAG, "未配对，跳过 WS 连接");
      return;
    }

    var self = this;
    // Secret NOT in URL — sent as first auth message after connect
    var wsUrl = config.serverUrl.replace("http://", "ws://") + "/api/device/ws/status";

    logger.info(TAG, "连接: " + wsUrl);

    try {
      var OkHttpClient = Packages.okhttp3.OkHttpClient;
      var Request = Packages.okhttp3.Request;
      var WebSocketListener = Packages.okhttp3.WebSocketListener;

      // 复用同一个 OkHttpClient，避免每次重连创建新的线程池
      if (!this._client) {
        this._client = new OkHttpClient.Builder()
          .readTimeout(0, java.util.concurrent.TimeUnit.MILLISECONDS)
          .pingInterval(15, java.util.concurrent.TimeUnit.SECONDS)
          .build();
      }

      var client = this._client;
      var request = new Request.Builder().url(wsUrl).build();

      var listener = new JavaAdapter(WebSocketListener, {
        onOpen: function (ws, response) {
          logger.info(TAG, "已连接，发送认证消息");
          self._ws = ws;
          self._connected = true;
          self._reconnectDelay = 3000;

          // Send auth as first message (not in URL)
          var authMsg = JSON.stringify({
            type: "auth",
            device_id: config.deviceId,
            secret: config.deviceSecret,
          });
          try { ws.send(authMsg); } catch (e) {
            logger.error(TAG, "发送认证消息失败: " + e.message);
          }

          // 启动应用层心跳（每 15 秒发一次 ping，防止 NAT/防火墙切断空闲连接）
          self._startPing();
          // 通知连接成功（用于重连后重新 poll）
          if (self._onConnected) {
            try { self._onConnected(); } catch (e) {
              logger.warn(TAG, "onConnected 回调失败: " + e.message);
            }
          }
        },
        onMessage: function (ws, text) {
          var str = String(text);
          // 服务端 pong 响应 — 忽略
          if (str === "pong" || str === "ping") {
            // 收到服务端 ping，回复 pong
            if (str === "ping") {
              try { ws.send("pong"); } catch (e) { /* ignore */ }
            }
            return;
          }
          self._handleMessage(str);
        },
        onClosing: function (ws, code, reason) {
          logger.info(TAG, "连接关闭: code=" + code + " reason=" + reason);
          try { ws.close(1000, null); } catch (e) { /* already closed */ }
          self._cleanup();

          if (code === 4001) {
            logger.error(TAG, "认证失败，设备可能已被删除");
            if (self._onAuthFailure) self._onAuthFailure();
            return;
          }
          if (code === 4002) {
            // 管理员强制断开 — 不重连，回到配对界面
            logger.warn(TAG, "被管理员强制断开，返回配对界面");
            if (self._onAuthFailure) self._onAuthFailure();
            return;
          }
          self._scheduleReconnect();
        },
        onFailure: function (ws, t, response) {
          var msg = t.getMessage() || "";
          var code = response ? response.code() : 0;
          logger.warn(TAG, "连接失败: code=" + code + " err=" + msg);
          self._cleanup();
          self._scheduleReconnect();
        },
      });

      client.newWebSocket(request, listener);
    } catch (e) {
      logger.error(TAG, "创建 WS 失败: " + e.message);
      this._scheduleReconnect();
    }
  },

  _startPing: function () {
    var self = this;
    if (this._pingTimer) clearInterval(this._pingTimer);
    this._pingTimer = setInterval(function () {
      if (self._ws) {
        try {
          self._ws.send("ping");
        } catch (e) {
          logger.warn(TAG, "发送 ping 失败: " + e.message);
          self._cleanup();
          self._scheduleReconnect();
        }
      }
    }, 15000);
  },

  _cleanup: function () {
    this._connected = false;
    this._ws = null;
    if (this._pingTimer) {
      clearInterval(this._pingTimer);
      this._pingTimer = null;
    }
  },

  _scheduleReconnect: function () {
    var self = this;
    if (this._stopped) return;
    if (this._reconnectTimer) return;
    logger.info(TAG, this._reconnectDelay / 1000 + " 秒后重连...");
    this._reconnectTimer = setTimeout(function () {
      self._reconnectTimer = null;
      self._connect();
    }, this._reconnectDelay);
    this._reconnectDelay = Math.min(this._reconnectDelay * 1.5, 60000);
  },
};

module.exports = deviceWs;
```

## core\task-executor.js

```javascript
// device/core/task-executor.js
var apiClient = require("./api-client");
var selectorLoader = require("./selector-loader");
var logger = require("../utils/logger");

var TAG = "任务执行";

// Handler 注册表
var handlers = {
  nurture: require("../handlers/nurture"),
  search_comment: require("../handlers/search-comment"),
  search_like: require("../handlers/search-like"),
  search_dm: require("../handlers/search-dm"),
  reply_comment: require("../handlers/reply-comment"),
  collect: require("../handlers/search-collect"),
};

var taskExecutor = {
  _currentTaskId: null,
  _cancelled: false,

  /**
   * 标记当前任务为已取消
   * @param {string} taskId
   */
  cancel: function (taskId) {
    if (this._currentTaskId === taskId) {
      this._cancelled = true;
      logger.info(TAG, "任务取消标记已设置: " + taskId);
    }
  },

  /**
   * 当前任务是否已被取消
   */
  isCancelled: function () {
    return this._cancelled;
  },

  execute: function (task) {
    logger.info(TAG, "执行任务: " + task.id + " 类型=" + task.type);

    var handler = handlers[task.type];
    if (!handler) {
      logger.error(TAG, "未找到任务类型处理器: " + task.type);
      return { status: "failed", result: { error: "Unknown task type: " + task.type } };
    }

    this._currentTaskId = task.id;
    this._cancelled = false;
    task.params.task_id = task.id;  // 注入任务 ID 供 handler 上报进度
    task.params.account_id = task.account_id;  // 注入账号 ID 供 handler 使用

    // 看门狗：任务最大执行时间 30 分钟，同时检查取消标记
    var TASK_TIMEOUT = 30 * 60 * 1000;
    var startTime = Date.now();
    var timedOut = false;
    var self = this;

    var watchdog = setInterval(function () {
      if (self._cancelled) {
        logger.info(TAG, "任务 " + task.id + " 已被取消");
        return;
      }
      if (Date.now() - startTime > TASK_TIMEOUT) {
        logger.error(TAG, "任务 " + task.id + " 执行超时（30分钟）");
        timedOut = true;
      }
    }, 10000);

    try {
      var crashRecovery = require("./crash-recovery");
      if (task.account_id) {
        crashRecovery.setAccountId(task.account_id);
      }

      var result = handler.execute(task.params);
      clearInterval(watchdog);

      this._currentTaskId = null;

      if (this._cancelled) {
        return { status: "cancelled", result: { error: "Task cancelled by server" } };
      }

      if (timedOut) {
        return { status: "failed", result: { error: "Task execution timed out (30 min)" } };
      }

      if (result.success) {
        logger.info(TAG, "任务 " + task.id + " 执行成功");
        return { status: "completed", result: result.result };
      } else {
        logger.warn(TAG, "任务 " + task.id + " 执行失败: " + result.error);
        return { status: "failed", result: { error: result.error } };
      }
    } catch (e) {
      clearInterval(watchdog);
      this._currentTaskId = null;
      logger.error(TAG, "任务 " + task.id + " 异常: " + e.message);
      return { status: "failed", result: { error: e.message } };
    }
  },

  /**
   * 注册新的 handler
   * @param {string} type
   * @param {Object} handler
   */
  registerHandler: function (type, handler) {
    handlers[type] = handler;
  },
};

module.exports = taskExecutor;
```

## handlers\base-handler.js

```javascript
// device/handlers/base-handler.js
var uiOperator = require("../core/ui-operator");
var antiDetect = require("../core/anti-detect");
var selectorLoader = require("../core/selector-loader");
var selectorResolver = require("../core/selector-resolver");
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

      var title = id("com.ss.android.ugc.aweme:id/title").findOne(2000);
      if (title && title.text()) parts.push(title.text());

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
   * 支持 conditions/AND/OR、match_mode:contains、chain
   */
  _findChildBySelector: function (parent, actionName) {
    return selectorResolver.findChildBySelector(parent, actionName);
  },

  _findByStrategyInParent: function (parent, strategy) {
    return selectorResolver.findByStrategyInParent(parent, strategy);
  },

  _findByCondInParent: function (parent, cond) {
    return selectorResolver.findByCondInParent(parent, cond);
  },

  _findAllByCondInParent: function (parent, cond) {
    return selectorResolver.findAllByCondInParent(parent, cond);
  },

  _findByConditionsInParent: function (parent, strategy) {
    return selectorResolver.findByConditionsInParent(parent, strategy);
  },

  _findByChainInParent: function (parent, steps) {
    return selectorResolver.findByChainInParent(parent, steps);
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
```

## handlers\comment-utils.js

```javascript
// device/handlers/comment-utils.js
// 评论相关共享工具 — search-collect 和 reply-comment 的公共方法
// 消除代码重复和循环依赖

var uiOperator = require("../core/ui-operator");
var selectorLoader = require("../core/selector-loader");
var selectorResolver = require("../core/selector-resolver");
var logger = require("../utils/logger");

var TAG = "评论工具";

var commentUtils = {

  /**
   * 打开评论区 — 统一实现，合并 search-collect 和 reply-comment 的最佳行为
   * @returns {boolean}
   */
  openComments: function () {
    // 1. 先检测评论区是否已打开
    var items = uiOperator.findElements("comment_list", 500);
    if (items && items.length > 0) {
      logger.debug(TAG, "评论区已打开 (" + items.length + " 条可见)");
      return true;
    }

    // 2. 点击视频评论按钮，指数退避重试
    for (var retry = 0; retry < 3; retry++) {
      var commentBtn = uiOperator.findElement("video_comment_btn", 2000);
      if (commentBtn) {
        uiOperator.clickElement(commentBtn);
        sleep(1500);
        items = uiOperator.findElements("comment_list", 2000);
        if (items && items.length > 0) {
          logger.debug(TAG, "评论区已打开 (" + items.length + " 条)");
          return true;
        }
      }
      if (retry < 2) sleep(1000 * Math.pow(2, retry));  // 2s, 4s
    }

    // 3. 兜底：back() 关闭可能误触的弹窗后重试 comment_btn
    back(); sleep(800);
    commentBtn = uiOperator.findElement("video_comment_btn", 2000);
    if (commentBtn) {
      uiOperator.clickElement(commentBtn);
      sleep(1500);
      items = uiOperator.findElements("comment_list", 1000);
      if (items && items.length > 0) return true;
    }

    logger.warn(TAG, "评论区打开失败");
    return false;
  },

  /**
   * 预检评论数 — 从评论按钮 desc 解析数字，零评论提前跳过
   * @param {UiObject} commentBtn
   * @returns {{count: number, rawDesc: string}} count=-1 表示未知
   */
  preCheckCommentCount: function (commentBtn) {
    var result = { count: -1, rawDesc: "" };
    if (!commentBtn || commentBtn.isImage || commentBtn.isCoordinate) return result;
    try {
      result.rawDesc = commentBtn.desc() || "";
      var numMatch = result.rawDesc.match(/(\d+)/);
      if (numMatch) {
        result.count = parseInt(numMatch[1]);
      } else if (result.rawDesc.length > 0) {
        result.count = 0;
      }
    } catch (e) {}
    return result;
  },

  /**
   * 解析单条评论
   * @param {UiObject} item - 评论项元素
   * @param {Object} [handler] - 可选，BaseHandler 实例
   * @returns {Object|null}
   */
  parseCommentItem: function (item, handler) {
    var findChild = (handler && handler._findChildBySelector)
      ? function (p, a) { return handler._findChildBySelector(p, a); }
      : function (p, a) { return selectorResolver.findChildBySelector(p, a); };
    var extractVal = (handler && handler._extractChildValue)
      ? function (el, a, fb) { return handler._extractChildValue(el, a, fb); }
      : function (el, a, fb) { return selectorResolver.extractChildValue(el, a, fb); };

    try {
      // 昵称
      var nicknameEl = findChild(item, "comment_author");
      var nickname = nicknameEl ? extractVal(nicknameEl, "comment_author", "unknown") : null;
      if (!nickname) {
        nicknameEl = item.findOne(clickable(true).className("android.widget.TextView"));
        nickname = nicknameEl ? extractVal(nicknameEl, "comment_author", "unknown") : "unknown";
      }

      // 评论文本
      var textEl = findChild(item, "comment_text");
      var text = textEl ? extractVal(textEl, "comment_text", "") : "";
      if (!text) {
        var textViews = item.find(className("android.widget.TextView"));
        var maxLen = 0;
        for (var i = 0; i < textViews.length; i++) {
          var t = textViews[i].text() || "";
          if (t.length > maxLen && t !== nickname) {
            maxLen = t.length;
            textEl = textViews[i];
          }
        }
        text = textEl ? extractVal(textEl, "comment_text", "") : "";
      }
      if (!text) return null;

      // 时间
      // selector 可能误匹配父级元素导致 text() 返回拼接后的全文本
      // 如 "昵称,评论文本,3小时前, · 广东,回复 按钮,"，需从中提取时间片段
      var timeEl = findChild(item, "comment_time");
      var rawTime = timeEl ? extractVal(timeEl, "comment_time", "") : "";
      var timeStr = commentUtils._cleanTimeStr(rawTime);

      // 是否作者
      var isAuthor = false;
      try {
        var authorEl = findChild(item, "comment_is_author");
        if (!authorEl) authorEl = item.findOne(text("作者"));
        if (authorEl) isAuthor = true;
      } catch (e) { /* ignore */ }

      return {
        nickname: nickname,
        text: text,
        time: timeStr,
        isAuthor: isAuthor,
        replyBtn: findChild(item, "comment_reply_button"),
        commentAuthorAvatarEl: findChild(item, "comment_author_avatar"),
      };
    } catch (e) {
      logger.warn(TAG, "解析评论项出错: " + e.message);
      return null;
    }
  },

  /**
   * 解析评论时间 — 支持 "刚刚"/"X分钟前"/"X小时前"/"X天前"/"昨天"/"前天"/"MM-DD"/"YYYY-MM-DD"
   * @param {string} timeStr
   * @returns {Date|null}
   */
  /**
   * 将评论原始时间字符串转为北京时间 ISO 格式 (YYYY-MM-DDTHH:mm:ss+08:00)
   * 用于上报服务端，替换相对时间如 "19分钟前"
   */
  toBeijingTime: function (timeStr) {
    if (!timeStr) return "";
    var parsed = this.parseTime(timeStr);
    if (!parsed) return timeStr;
    var y = parsed.getFullYear();
    var mo = ("0" + (parsed.getMonth() + 1)).slice(-2);
    var d = ("0" + parsed.getDate()).slice(-2);
    var h = ("0" + parsed.getHours()).slice(-2);
    var mi = ("0" + parsed.getMinutes()).slice(-2);
    var s = ("0" + parsed.getSeconds()).slice(-2);
    return y + "-" + mo + "-" + d + "T" + h + ":" + mi + ":" + s + "+08:00";
  },

  parseTime: function (timeStr) {
	    if (!timeStr) return null;
	    var now = new Date();

	    if (timeStr.indexOf('刚刚') != -1) return now;

	    var yearMatch = timeStr.match(/(\d+)\s*年前/);
	    if (yearMatch) return new Date(now.getTime() - parseInt(yearMatch[1]) * 365 * 24 * 60 * 60 * 1000);

	    var monthMatch = timeStr.match(/(\d+)\s*个月前/);
	    if (monthMatch) return new Date(now.getTime() - parseInt(monthMatch[1]) * 30 * 24 * 60 * 60 * 1000);

	    var weekMatch = timeStr.match(/(\d+)\s*周前/);
	    if (weekMatch) return new Date(now.getTime() - parseInt(weekMatch[1]) * 7 * 24 * 60 * 60 * 1000);

	    var dayMatch = timeStr.match(/(\d+)\s*天前/);
	    if (dayMatch) return new Date(now.getTime() - parseInt(dayMatch[1]) * 24 * 60 * 60 * 1000);

	    var hourMatch = timeStr.match(/(\d+)\s*小时前/);
	    if (hourMatch) return new Date(now.getTime() - parseInt(hourMatch[1]) * 60 * 60 * 1000);

	    var minMatch = timeStr.match(/(\d+)\s*分钟前/);
	    if (minMatch) return new Date(now.getTime() - parseInt(minMatch[1]) * 60 * 1000);

	    var secMatch = timeStr.match(/(\d+)\s*秒前/);
	    if (secMatch) return new Date(now.getTime() - parseInt(secMatch[1]) * 1000);

	    if (timeStr.indexOf('昨天') != -1) {
	      var yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
	      var hmMatch = timeStr.match(/(\d{1,2}):(\d{2})/);
	      if (hmMatch) yesterday.setHours(parseInt(hmMatch[1]), parseInt(hmMatch[2]), 0, 0);
	      return yesterday;
	    }

	    if (timeStr.indexOf('前天') != -1) {
	      var dayBefore = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 2);
	      var hm2 = timeStr.match(/(\d{1,2}):(\d{2})/);
	      if (hm2) dayBefore.setHours(parseInt(hm2[1]), parseInt(hm2[2]), 0, 0);
	      return dayBefore;
	    }

	    var ymdMatch = timeStr.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
	    if (ymdMatch) return new Date(parseInt(ymdMatch[1]), parseInt(ymdMatch[2]) - 1, parseInt(ymdMatch[3]));

	    // MM-DD / MM-DD HH:MM — 按当年算若为未来日期则回退一年
	    function _fixFuture(d) {
	      if (d > now) d.setFullYear(d.getFullYear() - 1);
	      return d;
	    }

	    var mdtMatch = timeStr.match(/^(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})$/);
	    if (mdtMatch) {
	      return _fixFuture(new Date(now.getFullYear(), parseInt(mdtMatch[1]) - 1, parseInt(mdtMatch[2]),
	                                 parseInt(mdtMatch[3]), parseInt(mdtMatch[4]), 0));
	    }

	    var mdMatch = timeStr.match(/^(\d{1,2})-(\d{1,2})$/);
	    if (mdMatch) {
	      return _fixFuture(new Date(now.getFullYear(), parseInt(mdMatch[1]) - 1, parseInt(mdMatch[2])));
	    }

	    logger.warn(TAG, '无法解析时间: ' + timeStr);
	    return null;
	  },

	/**
	 * 从被污染的 time_str 中提取真正的时间片段
	 * 当 comment_time selector 误匹配父元素时，text() 返回拼接全文本
	 * 如 "昵称,评论文本,3小时前, · 广东,回复 按钮," → "3小时前"
	 */
	_cleanTimeStr: function (raw) {
	  if (!raw) return "";
	  if (raw.length <= 15 && raw.indexOf(",") === -1) return raw;
	  var patterns = [
	    /\d+年前/, /\d+个月前/, /\d+周前/, /\d+天前/, /\d+小时前/, /\d+分钟前/, /\d+秒前/,
	    /刚刚/, /昨天\s*\d{1,2}:\d{2}/, /前天\s*\d{1,2}:\d{2}/,
	    /\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}/, /\d{4}-\d{1,2}-\d{1,2}/,
	    /\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}/, /\d{1,2}-\d{1,2}/,
	  ];
	  for (var i = 0; i < patterns.length; i++) {
	    var m = raw.match(patterns[i]);
	    if (m) return m[0];
	  }
	  return raw;
	},

localPreFilter: function (text) {
    if (!text) return false;
    var stripped = text
      .replace(/\[[^\]]+\]/g, "")
      .replace(/[\s~!@#$%^&*()_+\-={}|:;<>?,./'"'""'、。！，《》]+/g, "")
      .replace(/[^一-龥a-zA-Z0-9]/g, "")
      .trim();
    return !!(stripped && stripped.length > 2);
  },

  /**
   * 按时效筛选评论
   * @param {Array} comments
   * @param {number} maxAgeDays
   * @returns {Array}
   */
  filterByTime: function (comments, maxAgeDays) {
    var now = new Date();
    var cutoff = (maxAgeDays === Infinity) ? new Date(0) : new Date(now.getTime() - maxAgeDays * 24 * 60 * 60 * 1000);
    var filtered = [];
    for (var i = 0; i < comments.length; i++) {
      var commentDate = commentUtils.parseTime(comments[i].time);
      if (!commentDate || commentDate >= cutoff) {
        filtered.push(comments[i]);
      }
    }
    return filtered;
  },

  /**
   * 采集用户主页数据 — 统一的字段提取逻辑
   * @param {Object} options - { avatarEl: UiObject|null, uploadAvatar: bool }
   * @returns {Object|null}
   */
  collectProfileData: function (options) {
    options = options || {};
    var data = { nickname: "", douyin_id: "", likes_count: "", follow_count: "",
      fans_count: "", works_count: "", gender: "", age: "", ip_location: "", is_private: "否" };

    var fields = {
      "user_nickname": "nickname", "user_douyin_id": "douyin_id",
      "user_likes_count": "likes_count", "user_follow_count": "follow_count",
      "user_fans_count": "fans_count", "user_works_count": "works_count",
      "user_gender": "gender", "user_age": "age", "user_ip_location": "ip_location"
    };
    var hasData = false;
    for (var actionName in fields) {
      try {
        var el = uiOperator.findElement(actionName, 2000);
        if (el) {
          var selector = selectorLoader.get(actionName);
          data[fields[actionName]] = (selector && selector.purpose === "extract")
            ? uiOperator.extractValue(el, selector) : (el.text() || "");
          if (data[fields[actionName]]) hasData = true;
        }
      } catch (e) {}
    }

    // 清除 IP 属地前缀
    if (data.ip_location) data.ip_location = data.ip_location.replace(/^[·•・\s]+/, "");

    // 数字清洗：万/千单位转换
    commentUtils._cleanNumericFields(data);

    // 检查私密账号
    try { if (uiOperator.findElement("user_is_private", 2000)) data.is_private = "是"; } catch (e) {}

    if (!hasData) return null;

    logger.info(TAG, "用户数据: " + data.nickname + " | 抖音号=" + data.douyin_id +
      " | 粉丝=" + data.fans_count + " | 获赞=" + data.likes_count);

    // 头像裁剪 + 上传（仅采集流程，回复流程跳过）
    if (options.avatarEl && options.uploadAvatar && data.douyin_id) {
      var avatarBase64 = commentUtils._cropCircularAvatar(options.avatarEl);
      if (avatarBase64) {
        try { require("../core/api-client").uploadUserAvatar(data.douyin_id, avatarBase64); } catch (e) {}
      }
    }

    return data;
  },

  /**
   * 数字字段清洗 — 处理 "1.2万" / "3.5w" / "1,234" 等格式
   */
  _cleanNumericFields: function (data) {
    var numericFields = { likes_count: 1, follow_count: 1, fans_count: 1, works_count: 1 };
    for (var key in numericFields) {
      if (data[key]) {
        var raw = String(data[key]);
        var m = raw.match(/([\d.]+)\s*[万wW万]/);
        if (m) {
          data[key] = String(Math.round(parseFloat(m[1]) * 10000));
        } else {
          m = raw.match(/([\d.]+)\s*[千kK千]/);
          if (m) {
            data[key] = String(Math.round(parseFloat(m[1]) * 1000));
          } else {
            var digits = raw.replace(/[^\d]/g, "");
            data[key] = digits || "";
          }
        }
      }
    }
  },

  /**
   * 圆形头像裁剪 — 从当前屏幕截取头像区域的圆形裁剪
   * @param {UiObject} avatarEl
   * @returns {string|null} base64 PNG
   */
  _cropCircularAvatar: function (avatarEl) {
    if (!avatarEl || avatarEl.isImage || avatarEl.isCoordinate) return null;
    try {
      var avatarBounds = avatarEl.bounds();
      if (!avatarBounds) return null;

      var w = avatarBounds.right - avatarBounds.left;
      var h = avatarBounds.bottom - avatarBounds.top;
      var size = Math.min(w, h);
      var cx = avatarBounds.left + w / 2;
      var cy = avatarBounds.top + h / 2;
      var radius = size / 2;
      var left = Math.round(cx - radius);
      var top = Math.round(cy - radius);
      var sz = Math.round(size);

      var screen = null, squareImg = null, srcBitmap = null, outBitmap = null;
      try {
        screen = images.captureScreen();
        squareImg = images.clip(screen, left, top, sz, sz);
        if (squareImg) {
          srcBitmap = squareImg.getBitmap();
          outBitmap = android.graphics.Bitmap.createBitmap(
            sz, sz, android.graphics.Bitmap.Config.ARGB_8888
          );
          var canvas = new android.graphics.Canvas(outBitmap);
          var paint = new android.graphics.Paint();
          paint.setAntiAlias(true);
          paint.setFilterBitmap(true);
          canvas.drawCircle(radius, radius, radius, paint);
          paint.setXfermode(new android.graphics.PorterDuffXfermode(
            android.graphics.PorterDuff.Mode.SRC_IN
          ));
          canvas.drawBitmap(srcBitmap, 0, 0, paint);
          return images.toBase64(images.fromBitmap(outBitmap), "png");
        }
      } finally {
        if (outBitmap) outBitmap.recycle();
        if (srcBitmap) srcBitmap.recycle();
        if (squareImg) squareImg.recycle();
        if (screen) screen.recycle();
      }
    } catch (e) {
      logger.debug(TAG, "头像裁剪失败: " + e.message);
    }
    return null;
  },
};

module.exports = commentUtils;
```

## handlers\search-base.js

```javascript
// device/handlers/search-base.js
var BaseHandler = require("./base-handler");
var uiOperator = require("../core/ui-operator");
var antiDetect = require("../core/anti-detect");
var logger = require("../utils/logger");
var aiAnalyzer = require("../core/ai-analyzer");
var flowContext = require("../core/flow-context");
var taskExecutor = require("../core/task-executor");

var TAG = "搜索";

/**
 * 搜索基类 — 所有搜索类 handler 继承此对象
 * 提供通用的搜索导航逻辑，子类只需实现 _interactWithVideo()
 */
var SearchBaseHandler = Object.create(BaseHandler);

/**
 * 执行搜索+互动流程
 * @param {Object} params
 *   - keyword: string (搜索关键词)
 *   - count: number (操作数量)
 *   - content: string (可选，评论/私信内容)
 *   - sort_by: string (可选，排序方式: "latest"|"most_liked")
 * @returns {Object} { success, result, error }
 */
SearchBaseHandler.execute = function (params) {
  this._params = params;
  var keyword = params.keyword;
  var videoCount = params.video_count || params.count || 5;
  var content = params.content || "";
  var sortBy = params.sort_by || "";


  aiAnalyzer.useTemplate(params.prompt_template_id);

  if (!keyword) {
    return { success: false, error: "缺少关键词" };
  }

  logger.info(TAG, "搜索: '" + keyword + "', 视频=" + videoCount + ", 排序=" + sortBy);

  var taskId = params.task_id || "";
  var apiClient = require("../core/api-client");
  function _reportProgress(step, detail, prog) {
    if (taskId) { try { apiClient.reportProgress(taskId, step, detail, prog); } catch (e) {} }
  }
  _reportProgress("搜索: " + keyword, "开始搜索", 0);

  if (!this.ensureAppActive()) {
    return { success: false, error: "打开抖音失败" };
  }

  // 1. 进入搜索页
  if (!this._openSearch()) {
    return { success: false, error: "打开搜索页失败" };
  }

  // 2. 输入关键词
  if (!this._inputKeyword(keyword)) {
    return { success: false, error: "输入关键词失败" };
  }

  // 等待联想词列表加载
  sleep(2000);

  // 3. 点击联想词
  if (!this._clickSuggestion(keyword)) {
    // 联想词没找到，尝试直接搜索
    if (!this._submitSearch()) {
      return { success: false, error: "提交搜索失败" };
    }
  }

  sleep(2000);

  // 4. 点击"视频" tab
  this._clickVideoTab();
  sleep(2000);

  // 5. 排序（如果指定）
  if (sortBy) {
    this._sortResults(sortBy);
    sleep(1500);
  }

  // 6. 逐个视频处理（第一个点击，后续滑动切换）
  var stats = { success_count: 0, fail_count: 0, details: [] };

  for (var i = 0; i < videoCount; i++) {
    if (taskExecutor.isCancelled()) {
      logger.info(TAG, "任务已取消，停止处理视频");
      stats.details.push("cancelled at video " + (i + 1) + "/" + videoCount);
      break;
    }
    logger.info(TAG, "处理第 " + (i + 1) + "/" + videoCount + " 个结果");

    if (i === 0) {
      // 第一个视频：从搜索结果点击
      if (!this._clickSearchResult(0)) {
        logger.warn(TAG, "点击第一个视频失败，停止处理");
        break;
      }
      sleep(2000);
    } else {
      // 后续视频：暂停 → 滑动切换
      back(); sleep(500);
      if (uiOperator.findElement("is_video_view", 1000)) {
        press(device.width / 2, device.height / 2, 80);
        sleep(300);
      }
      uiOperator.swipeUp();
      sleep(2500);
    }

    var interactResult = this._interactWithVideo(content, stats);
    if (interactResult) {
      stats.success_count++;
    } else {
      stats.fail_count++;
    }

    antiDetect.maybePause();
  }

  logger.info(TAG, "搜索完成. " + JSON.stringify(stats));
  return { success: true, result: stats };
};

/**
 * 打开搜索页
 * 先尝试直接点击搜索入口，失败则 back() 后重试
 */
SearchBaseHandler._openSearch = function () {
  // 1. 首页可能还在加载，多等几秒，重试 3 次（safeClick 内部 findElement 等 3s × 退避 2s/4s ≈ 最多 17s）
  var clicked = this.safeClick("search_tab", 3);
  if (clicked) {
    sleep(Math.floor(Math.random() * 1000 + 1000));
    if (uiOperator.isOnPage("is_search_view")) {
      flowContext.enter("search");
      return true;
    }
    logger.warn(TAG, "点击 search_tab 后未进入搜索页，重试");
  }

  // 2. 搜索入口找不到，可能在子页面，最多 back 3 次（不摧毁页面状态）
  for (var i = 0; i < 3; i++) {
    back();
    sleep(Math.floor(Math.random() * 400 + 1000));
    clicked = this.safeClick("search_tab", 2);
    if (clicked) {
      sleep(Math.floor(Math.random() * 1000 + 1000));
      if (uiOperator.isOnPage("is_search_view")) {
        flowContext.enter("search");
        return true;
      }
      logger.warn(TAG, "back 后点击 search_tab 未进入搜索页，继续重试");
    }
  }

  // 3. 冷启动兜底
  logger.warn(TAG, "back 链恢复失败，尝试冷启动回首页");
  try { uiOperator.closeApp(); sleep(800); } catch (e) {}
  if (uiOperator.openApp()) {
    sleep(4000);
    clicked = this.safeClick("search_tab", 3);
    if (clicked) {
      sleep(Math.floor(Math.random() * 1000 + 1000));
      if (uiOperator.isOnPage("is_search_view")) {
        flowContext.enter("search");
        return true;
      }
      logger.warn(TAG, "冷启动后点击 search_tab 未进入搜索页");
    }
  }
  return false;
};

/**
 * 在搜索框输入关键词
 * 使用 setText 直接设置（测试验证可用）
 */
SearchBaseHandler._inputKeyword = function (keyword) {
  // 确认在搜索页
  if (!uiOperator.isOnPage("is_search_view")) {
    logger.warn(TAG, "搜索输入框未找到：不在搜索页");
    return false;
  }
  // 在屏幕顶部区域限定查找可聚焦的搜索输入框
  var allEdits = className("EditText").find();
  var editBox = null;
  for (var ei = 0; ei < allEdits.length; ei++) {
    try {
      if (!allEdits[ei].focusable()) continue;
      var b = allEdits[ei].bounds();
      if (b && b.top < device.height * 0.3) { editBox = allEdits[ei]; break; }
    } catch (e) {}
  }
  if (!editBox) {
    logger.warn(TAG, "搜索输入框未找到");
    return false;
  }
  editBox.setText(keyword);
  sleep(500);
  logger.info(TAG, "输入关键词: '" + keyword + "'");
  return true;
};

/**
 * 点击联想词 — RecyclerView 内遍历匹配关键词
 */
SearchBaseHandler._clickSuggestion = function (keyword) {
  // RecyclerView 遍历匹配联想词
  var rv = id("recycler_view").findOne(2000);
  if (!rv) {
    var allRVs = className("androidx.recyclerview.widget.RecyclerView").find();
    if (allRVs.length === 0) allRVs = className("android.support.v7.widget.RecyclerView").find();
    for (var ri = 0; ri < allRVs.length; ri++) {
      var rvb = allRVs[ri].bounds();
      if (rvb && rvb.height() < device.height * 0.5 && rvb.top < device.height * 0.4) {
        rv = allRVs[ri]; break;
      }
    }
  }
  if (rv) {
    var children = rv.children();
    for (var c = 0; c < children.length; c++) {
      var ct = children[c].findOne(text(keyword));
      if (ct) {
        logger.info(TAG, "点击联想词: '" + ct.text() + "'");
        var gpp = ct.parent().parent();
        var bb = gpp.bounds();
        if (bb) { press(bb.centerX(), bb.centerY(), 150); sleep(500); return true; }
      }
    }
  }

  logger.warn(TAG, "未找到匹配联想词: '" + keyword + "'");
  return false;
};

/**
 * 点击"视频" tab
 * 优先使用选择器系统，回退到硬编码
 */
SearchBaseHandler._clickVideoTab = function () {
  var clicked = this.safeClick("search_video_tab", 2);
  if (clicked) {
    logger.info(TAG, "点击视频标签");
    return true;
  }
  logger.warn(TAG, "视频标签点击失败");
  return false;
};

/**
 * 点击排序选项
 * 使用选择器系统（支持 text 和 image 策略）
 * @param {string} sortBy - "latest" 或 "most_liked"
 */
SearchBaseHandler._sortResults = function (sortBy) {
  var actionMap = {
    "latest": "sort_latest",
    "most_liked": "sort_most_liked",
    "default": "sort_default",
  };
  var actionName = actionMap[sortBy] || actionMap["default"];

  // 打开排序弹窗
  if (!this.safeClick("sort_button", 3)) {
    logger.warn(TAG, "排序按钮未找到");
    return false;
  }
  sleep(1500);

  // 以图找图验证弹窗是否打开，没找到则关闭后重新打开再试
  var optionEl = uiOperator.findElement(actionName, 3000);
  if (!optionEl) {
    logger.info(TAG, "排序弹窗未检测到 " + sortBy + "，关闭后重新打开弹窗重试");
    this.safeClick("sort_button", 1);
    sleep(800);
    this.safeClick("sort_button", 1);
    sleep(1500);
    optionEl = uiOperator.findElement(actionName, 3000);
  }

  if (!optionEl) {
    logger.warn(TAG, "排序选项未找到: " + sortBy);
    this.safeClick("sort_button", 1);
    return false;
  }

  // 点击排序选项
  uiOperator.clickElement(optionEl);
  logger.info(TAG, "排序方式: " + sortBy);
  sleep(500);

  // 关弹窗：抖音选完排序后可能自动关，也可能不关。连点可能反而重新打开。
  // 策略：先等 800ms 等自动关闭动画完成，再图找图判断，开着才关，关完验证
  var stillOpen = uiOperator.findElement(actionName, 2000);
  if (stillOpen) {
    logger.info(TAG, "排序弹窗未关闭，点击关闭");
    var closeBtn = uiOperator.findElement("sort_button", 2000);
    if (closeBtn) {
      uiOperator.clickElement(closeBtn);
      sleep(600);
      // 验证：如果还在，说明刚才那下可能反而打开了，再关一次
      if (uiOperator.findElement(actionName, 1000)) {
        logger.info(TAG, "排序弹窗仍在，再次关闭");
        closeBtn = uiOperator.findElement("sort_button", 1000);
        if (closeBtn) { uiOperator.clickElement(closeBtn); sleep(500); }
      }
    }
  } else {
    logger.info(TAG, "排序弹窗已关闭");
  }
  sleep(500);
  return true;
};

/**
 * 搜索 → 排序 → 关闭弹出框 → 打开第一个视频
 * @param {string} keyword
 * @param {string} sortBy - "latest" 或 "most_liked"
 * @returns {boolean}
 */
SearchBaseHandler.searchSortAndOpenFirstResult = function (keyword, sortBy) {
  if (!this._openSearch()) return false;
  if (!this._inputKeyword(keyword)) return false;
  if (!this._clickSuggestion(keyword)) {
    if (!this._submitSearch()) return false;
  }
  sleep(3000);
  this._clickVideoTab();
  sleep(2000);
  if (sortBy) {
    if (!this._sortResults(sortBy)) {
      logger.warn(TAG, "排序失败，将以默认排序处理视频 (sortBy=" + sortBy + ")");
    }
    sleep(1500);
  }
  if (!this._clickSearchResult(0)) return false;
  sleep(2000);
  return true;
};

/**
 * 点击搜索按钮（备用）
 */
SearchBaseHandler._submitSearch = function () {
  return this.safeClick("search_button", 3);
};

/**
 * 点击第 index 个搜索结果
 * 通过选择器系统查找视频列表容器，再点击子项
 */
SearchBaseHandler._clickSearchResult = function (index) {
  var screenW = device.width;
  var screenH = device.height;

  function isVisible(el) {
    try {
      var b = el.bounds();
      if (!b) return false;
      var cx = b.centerX();
      var cy = b.centerY();
      return cx >= 0 && cy >= 0 && cx < screenW && cy < screenH;
    } catch (e) { return false; }
  }

  function tryClick(el) {
    if (el.clickable()) return el.click();
    var b = el.bounds();
    if (b) return press(b.centerX(), b.centerY(), 80);
    return false;
  }

  function findRecyclerView() {
    var rv = id("recycler_view").findOne(500);
    if (rv) return rv;
    var all = className("androidx.recyclerview.widget.RecyclerView").find();
    if (all.length === 0) all = className("android.support.v7.widget.RecyclerView").find();
    for (var i = 0; i < all.length; i++) {
      var b = all[i].bounds();
      if (b && b.height() > 200 && b.width() > 200) return all[i];
    }
    return null;
  }

  var maxScroll = 10;
  for (var scroll = 0; scroll < maxScroll; scroll++) {
    // 路径1: 选择器
    var items = uiOperator.findElements("search_video_list", 3000);
    var seenCount = 0;
    for (var i = 0; i < items.length; i++) {
      if (isVisible(items[i])) {
        if (seenCount === index) {
          if (tryClick(items[i])) {
            logger.info(TAG, "点击视频: 第" + (index+1) + "个(策略)"); sleep(2000);
            this.safeClick("off_video", 1);
            return true;
          }
          return false;
        }
        seenCount++;
      }
    }

    // 路径2: RecyclerView 兜底
    var rv = findRecyclerView();
    if (rv) {
      var children = rv.children();
      var cnt = 0;
      for (var c = 0; c < children.length; c++) {
        if (isVisible(children[c])) {
          if (cnt === index) {
            if (tryClick(children[c])) {
              logger.info(TAG, "点击视频: 第" + (index+1) + "个(兜底)"); sleep(2000);
              this.safeClick("off_video", 1);
              return true;
            }
            return false;
          }
          cnt++;
        }
      }
    }

    if (scroll < maxScroll - 1) { uiOperator.swipeUp(); sleep(2000); }
  }

  logger.warn(TAG, "目标视频 " + (index + 1) + " 未找到");
  return false;
};

/**
 * 返回上一页
 */
SearchBaseHandler._goBack = function () {
  back();
  sleep(1000);
};

/**
 * 容错返回：连续按返回键直到回到搜索视频列表页
 * 不管当前在评论列表页/个人主页/私信页/视频详情页，最终都能回到搜索结果列表
 *
 * 页面检测选择器（需在管理后台配置）：
 *   search_video_list  — 搜索视频列表存在 → 已在搜索页
 *   search_video_tab   — 视频 tab 存在 → 已在搜索页
 *   is_comment_view    — 在评论面板？
 *   is_user_view       — 在个人主页？
 *
 * @returns {boolean} 是否成功回到搜索列表页
 */
SearchBaseHandler._backToSearchResults = function () {
  var maxBacks = 5;
  for (var i = 0; i < maxBacks; i++) {
    if (uiOperator.isOnPage("search_result_list") || uiOperator.isOnPage("is_search_view")) {
      logger.info(TAG, "已在搜索列表页 (back " + i + " 次)");
      flowContext.enter("search");
      return true;
    }

    var page = uiOperator.detectPage();
    logger.info(TAG, "第 " + (i + 1) + " 次 back，当前位置: " + (page || "未知"));
    back();
    sleep(1000);
  }

  logger.warn(TAG, "back " + maxBacks + " 次后仍未回到搜索列表页");
  return false;
};

/**
 * 搜索关键词并打开第一个结果视频
 */
SearchBaseHandler.searchAndOpenFirstResult = function (keyword) {
  if (!this._openSearch()) return false;
  if (!this._inputKeyword(keyword)) return false;
  if (!this._clickSuggestion(keyword)) {
    if (!this._submitSearch()) return false;
  }
  sleep(3000);
  this._clickVideoTab();
  sleep(2000);
  if (!this._clickSearchResult(0)) return false;
  sleep(2000);
  return true;
};

/**
 * 互动逻辑（子类必须实现）
 * @param {string} content - 评论/私信内容
 * @param {Object} stats - 统计对象
 * @returns {boolean} 是否成功
 */
SearchBaseHandler._interactWithVideo = function (content, stats) {
  throw new Error("_interactWithVideo() not implemented");
};

// ==== KV 持久化（设备重启恢复状态）====

/**
 * 获取缓存目录 — 兼容 Android 10+ scoped storage
 * 复用 api-client.js 的路径策略: 优先 getExternalFilesDir, 回退 /sdcard/
 */
SearchBaseHandler._getCacheDir = function () {
  var dirs = this._getCacheDirCandidates();
  for (var i = 0; i < dirs.length; i++) {
    if (this._ensureCacheDir(dirs[i])) return dirs[i];
  }
  return dirs[0] || "/sdcard/dy_auto/cache";
};

SearchBaseHandler._getCacheDirCandidates = function () {
  var dirs = [];
  function add(dir) {
    if (dir && dirs.indexOf(dir) === -1) dirs.push(dir);
  }
  try {
    var intDir = context.getFilesDir();
    if (intDir) add(intDir.getAbsolutePath() + "/dy_auto_cache");
  } catch (e) {}
  try {
    var extDir = context.getExternalFilesDir(null);
    if (extDir) add(extDir.getAbsolutePath() + "/dy_auto_cache");
  } catch (e2) {}
  add("/sdcard/dy_auto/cache");
  return dirs;
};

SearchBaseHandler._ensureCacheDir = function (dir) {
  try {
    var f = new java.io.File(String(dir));
    if (!f.exists()) f.mkdirs();
    return f.exists() && f.isDirectory();
  } catch (e) {
    logger.warn(TAG, "缓存目录创建失败: " + dir + " err=" + e.message);
    return false;
  }
};

SearchBaseHandler._storageGet = function (key, defaultVal) {
  var dirs = this._getCacheDirCandidates();
  for (var i = 0; i < dirs.length; i++) {
    try {
      if (!this._ensureCacheDir(dirs[i])) continue;
      var path = dirs[i] + "/" + key + ".txt";
      if (files.exists(path)) {
        var parsed = parseInt(files.read(path).trim(), 10);
        return isNaN(parsed) ? defaultVal : parsed;
      }
    } catch (e) {
      logger.warn(TAG, "storageGet 读取失败: " + key + " err=" + e.message);
    }
  }
  return defaultVal;
};

SearchBaseHandler._storageSet = function (key, val) {
  var dirs = this._getCacheDirCandidates();
  var lastErr = "";
  for (var i = 0; i < dirs.length; i++) {
    try {
      if (!this._ensureCacheDir(dirs[i])) continue;
      var path = dirs[i] + "/" + key + ".txt";
      files.write(path, String(val));
      return true;
    } catch (e) {
      lastErr = e.message;
    }
  }
  logger.warn(TAG, "storageSet 写入失败: " + key + "=" + val + " err=" + lastErr);
  return false;
};


// ==== DM 序列发送方法 (search-dm / reply-comment 共用) ====

/**
 * 解析消息序列，返回 [{order, content, delay_ms}]
 * 优先级: dm_sequence_id(缓存+变体) > dm_messages(内联回退) > content > AI 生成
 * 支持变体轮替: cached.variants 存在时轮替选取，设备重启后从 KV 恢复索引
 */
SearchBaseHandler.resolveMessages = function (params) {
  // 1. dm_sequence_id — 查 poll 缓存 (含 variants, 优先于内联 dm_messages)
  if (params.dm_sequence_id) {
    var cached = this._dmSeqCache && this._dmSeqCache[params.dm_sequence_id];
    if (cached) {
      // 有变体 → 轮替选取
      if (cached.variants && cached.variants.length > 0) {
        var storageKey = "dm_variant_idx_" + params.dm_sequence_id;
        var idx = this._storageGet(storageKey, 0);
        var picked = cached.variants[idx % cached.variants.length];
        this._storageSet(storageKey, (idx + 1) % cached.variants.length);
        logger.info(TAG, "DM变体轮替: seq=" + params.dm_sequence_id + " idx=" + idx + "/" + cached.variants.length + " msg1=" + (picked[0] ? (picked[0].content || "").substring(0, 30) : ""));
        return picked;
      }
      // 无变体 → 返回缓存消息
      logger.info(TAG, "DM使用缓存消息(无变体): seq=" + params.dm_sequence_id);
      return cached.messages;
    }
    logger.warn(TAG, "DM序列模板缓存未命中: " + params.dm_sequence_id + "，回退到内联消息");
    // 缓存未命中时继续往下走，用 dm_messages 作为回退
  }
  // 2. dm_messages — 内联消息 (服务端展开的回退，或手动指定)
  if (params.dm_messages && params.dm_messages.length > 0) {
    logger.info(TAG, "DM使用内联消息(无dm_sequence_id): msgs=" + params.dm_messages.length);
    return params.dm_messages;
  }
  // 3. content — 单条消息
  if (params.content) {
    return [{order: 1, content: params.content, delay_ms: 0}];
  }
  var count = params.count || 1;
  var videoText = "";
  try { videoText = this._extractVideoText ? this._extractVideoText() : ""; } catch (e) {}
  if (count > 1 && videoText) {
    var seq = aiAnalyzer.generateVideoDMSequence(videoText, count);
    if (seq && seq.length > 0) return seq;
  }
  var single = videoText ? aiAnalyzer.generateVideoDM(videoText) : "";
  return single ? [{order: 1, content: single, delay_ms: 0}] : [];
};

/**
 * 变量替换 — 不存在的 key → 空字符串
 */
SearchBaseHandler.applyVariables = function (template, vars) {
  return template.replace(/\{\{(\w+)\}\}/g, function (_, key) {
    return vars[key] || "";
  });
};

/**
 * 发送消息序列通用循环（拟人输入 + 延迟）
 */
SearchBaseHandler._sendMessageSequence = function (messages, stats, keyword) {
  var sentCount = 0;
  var antiDetect = require("../core/anti-detect");
  antiDetect._skipDisabled = true;
  try {
    for (var i = 0; i < messages.length; i++) {
    var msg = messages[i];
    var content = this.applyVariables(msg.content, {keyword: keyword || ""});
    var inputOk = this.safeInput("dm_input", content);
    if (!inputOk) {
      logger.warn(TAG, "DM序列[" + (i + 1) + "/" + messages.length + "]输入失败，跳过本条");
      continue;
    }
    sleep(500);
    var sendBtn = uiOperator.findElement("dm_send", 3000);
    if (!sendBtn) {
      logger.warn(TAG, "DM序列[" + (i + 1) + "/" + messages.length + "]发送按钮未找到，本条未发送");
      continue;
    }
    uiOperator.clickElement(sendBtn);
    sleep(1000);
    var sendFailed = !!uiOperator.findElement("dm_send_failed", 2000, true);
    if (sendFailed) {
      logger.warn(TAG, "DM序列[" + (i + 1) + "/" + messages.length + "]发送失败，停止向该用户发送后续私信");
      break;
    }
    sentCount++;
    var extraDelay = msg.delay_ms != null ? msg.delay_ms : (Math.floor(Math.random() * 3000) + 2000);
    sleep(extraDelay);
    stats.details.push("dm_sent[" + (i + 1) + "/" + messages.length + "]: "
      + content.substring(0, 30));
    }
  } finally {
    antiDetect._skipDisabled = false;
  }
  return sentCount;
};

module.exports = SearchBaseHandler;
```

## handlers\comment-base.js

```javascript
// device/handlers/comment-base.js
// 视频+评论统一基类 — reply-comment 和 search-collect 的公共骨架
// 继承 SearchBaseHandler，子类只需实现 _processComments()

var SearchBaseHandler = require("./search-base");
var uiOperator = require("../core/ui-operator");
var aiAnalyzer = require("../core/ai-analyzer");
var antiDetect = require("../core/anti-detect");
var apiClient = require("../core/api-client");
var commentUtils = require("./comment-utils");
var logger = require("../utils/logger");
var flowContext = require("../core/flow-context");
// Lazy-load to break circular: task-executor → reply-comment → comment-base → task-executor

var TAG = "评论基类";

var CommentBaseHandler = Object.create(SearchBaseHandler);

/**
 * 子类可覆盖的配置
 */
CommentBaseHandler._config = {
  videoTimeoutMs: 120000,   // 单视频超时 ms，0=不限
  interVideoDelay: 2000,    // 视频间等待 ms
  maxVideoCount: Infinity,  // video_count=-1 时的上限
  defaultVideoCount: 5,     // 未指定 video_count 时的默认值
};

/**
 * 执行入口 — 搜索 → 视频循环 → 逐视频处理评论
 * 子类必须实现 _processComments(params, stats, videoIndex)
 */
CommentBaseHandler.execute = function (params) {
  var keyword = params.keyword;
  var videoCount = (params.video_count === -1) ? this._config.maxVideoCount : (params.video_count || this._config.defaultVideoCount);
  var sortBy = params.sort_by || "";

  aiAnalyzer.useTemplate(params.prompt_template_id);

  if (!keyword) {
    return { success: false, error: "缺少关键词" };
  }

  logger.info(TAG, "关键词='" + keyword + "', 视频=" + videoCount + ", 排序=" + sortBy);

  var taskId = params.task_id || "";
  function _reportProgress(step, detail, prog) {
    if (taskId) { try { apiClient.reportProgress(taskId, step, detail, prog); } catch (e) {} }
  }

  // 子类钩子：搜索前准备（如 resolveDestination）
  this._beforeSearch(params);

  if (!this.ensureAppActive()) {
    return { success: false, error: "打开抖音失败" };
  }

  // 搜索导航
  _reportProgress("搜索: " + keyword, "开始搜索", 0);
  if (!this._openSearch()) return { success: false, error: "打开搜索页失败" };
  if (!this._inputKeyword(keyword)) return { success: false, error: "输入关键词失败" };
  sleep(1000);
  if (!this._clickSuggestion(keyword)) {
    if (!this._submitSearch()) return { success: false, error: "提交搜索失败" };
  }
  sleep(2000);
  this._clickVideoTab();
  sleep(1000);

  if (sortBy) {
    this._sortResults(sortBy);
    sleep(800);
  }

  var stats = this._initStats(params);

  // 视频循环
  for (var v = 0; v < videoCount; v++) {
    if (require("../core/task-executor").isCancelled()) {
      logger.info(TAG, "任务已取消，停止处理视频");
      break;
    }

    logger.info(TAG, "=== 视频 " + (v + 1) + "/" + videoCount + " ===");
    _reportProgress("视频 " + (v + 1) + "/" + videoCount, "关键词: " + keyword, v / videoCount);

    // 进入视频
    if (v === 0) {
      if (!this._clickSearchResult(0)) break;
      sleep(2000);
    } else {
      uiOperator.swipeUp();
      sleep(this._config.interVideoDelay);
    }

    // 等待视频页加载
    if (!this._waitForVideoPage(params, v)) continue;

    // 预检评论数
    if (!this._shouldProcessVideo(params, v)) {
      this._onVideoSkipped(params, stats, v);
      continue;
    }

    // 打开评论区
    if (!this._ensureCommentsOpen(params, v)) continue;

    // 处理评论 — 子类实现
    var processResult = this._processComments(params, stats, v);
    if (processResult === "break") break;

    // 关闭评论区 + 切视频
    this._closeComments();

    stats.videos_processed = (stats.videos_processed || 0) + 1;
    antiDetect.maybePause();
  }

  logger.info(TAG, "完成. " + JSON.stringify(stats));
  return { success: true, result: stats };
};

/**
 * 搜索前准备（子类可覆盖）
 */
CommentBaseHandler._beforeSearch = function (params) {
  // default: no-op
};

/**
 * 初始化统计对象（子类可覆盖）
 */
CommentBaseHandler._initStats = function (params) {
  return { videos_processed: 0, success_count: 0, fail_count: 0, skipped: 0, details: [] };
};

/**
 * 等待进入视频页
 */
CommentBaseHandler._waitForVideoPage = function (params, videoIndex) {
  var timeout = this._config.videoTimeoutMs;
  var startTime = Date.now();

  for (var wait = 0; wait < 5; wait++) {
    if (timeout > 0 && Date.now() - startTime > timeout) {
      logger.warn(TAG, "视频 " + (videoIndex + 1) + " 等待超时，跳过");
      return false;
    }
    var commentBtn = uiOperator.findElement("video_comment_btn", 2000);
    if (commentBtn) return true;
    logger.info(TAG, "等待进入视频页 (" + (wait + 1) + "/5)");
  }
  logger.warn(TAG, "未进入视频详情页，跳过");
  return false;
};

/**
 * 预检评论数，返回 true 继续处理
 */
CommentBaseHandler._shouldProcessVideo = function (params, videoIndex) {
  var commentBtn = uiOperator.findElement("video_comment_btn", 2000);
  if (!commentBtn) return false;

  var cc = commentUtils.preCheckCommentCount(commentBtn);
  logger.info(TAG, "视频 " + (videoIndex + 1) + " 评论数: " + (cc.count >= 0 ? cc.count : "未知"));

  if (cc.count === 0) {
    logger.info(TAG, "该视频无评论，跳过");
    return false;
  }
  return true;
};

/**
 * 视频被跳过时的处理（子类可覆盖）
 */
CommentBaseHandler._onVideoSkipped = function (params, stats, videoIndex) {
  // default: no-op
};

/**
 * 打开评论区
 */
CommentBaseHandler._ensureCommentsOpen = function (params, videoIndex) {
  return commentUtils.openComments();
};

/**
 * 关闭评论区
 */
CommentBaseHandler._closeComments = function () {
  this.safeClick("comment_off_btn", 2);
  sleep(400);
  if (uiOperator.isOnPage("is_comment_view")) {
    logger.info(TAG, "评论区未关闭，back 兜底");
    back();
    sleep(500);
  }
};

/**
 * 处理评论 — 子类必须实现
 * @param {Object} params — 任务参数
 * @param {Object} stats — 统计对象
 * @param {number} videoIndex — 当前视频索引
 * @returns {string|undefined} "break" 终止视频循环，否则继续
 */
CommentBaseHandler._processComments = function (params, stats, videoIndex) {
  throw new Error("_processComments() not implemented");
};

module.exports = CommentBaseHandler;
```

## handlers\nurture.js

```javascript
// device/handlers/nurture.js
var BaseHandler = require("./base-handler");
var uiOperator = require("../core/ui-operator");
var antiDetect = require("../core/anti-detect");
var aiAnalyzer = require("../core/ai-analyzer");
var commentUtils = require("./comment-utils");
var logger = require("../utils/logger");
var flowContext = require("../core/flow-context");
var taskExecutor = require("../core/task-executor");

var TAG = "养号";

/**
 * 养号 Handler
 * V2 params:
 *   - sub_tasks: Array<{ type: string, count: number, content_template_id?: string }>
 *   - completion_mode: "all" | "any"
 *   - duration: number (最大时长，分钟)
 *   - keyword_matrix: string[] (可选，AI 扩展的关键词矩阵，用于内容语义过滤)
 * Legacy params:
 *   - duration: number (养号时长，分钟)
 *   - actions: Array<{ type: string, weight: number }>
 */
var NurtureHandler = Object.create(BaseHandler);

NurtureHandler.execute = function (params) {
  // V2 format: sub_tasks + completion_mode
  if (params.sub_tasks) {
    return this._executeV2(params);
  }
  // Legacy format: duration + actions
  return this._legacyExecute(params);
};

NurtureHandler._executeV2 = function (params) {
  var subTasks = params.sub_tasks;
  var completionMode = params.completion_mode || "all";
  var maxDuration = (params.duration || 60) * 60 * 1000;
  var startTime = Date.now();

  // Store keyword matrix for content filtering
  this._keywordMatrix = params.keyword_matrix || [];

  // 加载服务端提示词模板
  aiAnalyzer.useTemplate(params.prompt_template_id);

  logger.info(TAG, "开始养号 V2, 子任务数=" + subTasks.length + ", 模式=" + completionMode +
    (this._keywordMatrix.length > 0 ? ", 关键词=" + this._keywordMatrix.length + "个" : ""));

  if (!this.ensureAppActive()) {
    return { success: false, error: "Failed to open Douyin" };
  }

  // Initialize progress for each sub-task
  var progress = subTasks.map(function (st) {
    return {
      type: st.type,
      target: st.count,
      done: 0,
      contentTemplateId: st.content_template_id || null,
    };
  });

  while (Date.now() - startTime < maxDuration) {
    if (taskExecutor.isCancelled()) {
      logger.info(TAG, "任务已取消，停止养号");
      break;
    }
    // Find incomplete sub-tasks
    var pending = progress.filter(function (p) { return p.done < p.target; });
    if (pending.length === 0) {
      logger.info(TAG, "所有子任务已完成");
      break;
    }

    // Randomly pick one incomplete sub-task
    var task = pending[Math.floor(Math.random() * pending.length)];

    // 执行前确保在推荐页（防止误触跳转后所有操作都在错误页面）
    this._ensureOnFeed();

    try {
      this._executeSubTask(task);
      task.done++;
    } catch (e) {
      logger.error(TAG, "子任务 '" + task.type + "' 出错: " + e.message);
    }

    // Log progress
    var progressSummary = progress.map(function (p) {
      return p.type + ":" + p.done + "/" + p.target;
    }).join(" ");
    logger.info(TAG, "进度: " + progressSummary);

    // Check completion condition
    if (completionMode === "any") {
      var anyDone = progress.some(function (p) { return p.done >= p.target; });
      if (anyDone) {
        logger.info(TAG, "任一子任务完成，结束养号");
        break;
      }
    }

    antiDetect.humanSwipeUp();
  }

  // Build stats
  var stats = { success_count: 0 };
  progress.forEach(function (p) {
    stats[p.type] = { target: p.target, done: p.done };
    if (p.type === "like" || p.type === "comment" || p.type === "follow") {
      stats.success_count += p.done;
    }
  });

  logger.info(TAG, "养号 V2 完成: " + JSON.stringify(stats));
  return { success: true, result: stats };
};

NurtureHandler._executeSubTask = function (task) {
  switch (task.type) {
    case "browse":
      this._browseFeed();
      break;
    case "watch":
      this._watchVideo();
      break;
    case "like":
      this._likeCurrentVideo();
      break;
    case "comment":
      this._commentOnVideo(task.contentTemplateId);
      break;
    case "follow":
      this._followCurrentUser();
      break;
    default:
      this._browseFeed();
  }
};

NurtureHandler._browseFeed = function () {
  this._ensureOnFeed();
  // 浏览推荐页：快速扫一眼，大部分 2-5 秒，偶尔多停一会
  var watchTime = this._humanDuration(2000, 8000, 4000);
  logger.debug(TAG, "浏览推荐页 " + Math.round(watchTime / 1000) + "s");
  sleep(watchTime);
};

NurtureHandler._watchVideo = function () {
  // 先检测是否是广告 — 广告直接跳过
  if (this._isAdContent()) {
    logger.info(TAG, "检测到广告，直接跳过");
    return;
  }

  // 检测内容互动数据来判断质量
  var quality = this._assessContentQuality();
  var watchTime;

  if (quality === "high") {
    // 精彩内容：看得久，30-60 秒，偶尔模拟看评论
    watchTime = this._humanDuration(25000, 60000, 40000);
    logger.debug(TAG, "精彩内容，深度观看 " + Math.round(watchTime / 1000) + "s");
  } else if (quality === "medium") {
    // 普通内容：15-30 秒
    watchTime = this._humanDuration(12000, 30000, 20000);
    logger.debug(TAG, "普通内容，正常观看 " + Math.round(watchTime / 1000) + "s");
  } else {
    // 无亮点内容：3-10 秒快速划走
    watchTime = this._humanDuration(3000, 10000, 5000);
    logger.debug(TAG, "无亮点内容，快速划走 " + Math.round(watchTime / 1000) + "s");
  }

  sleep(watchTime);

  // 精彩内容有概率模拟看评论区（停留更久）
  if (quality === "high" && Math.random() < 0.3) {
    var commentPause = Math.floor(Math.random() * 5000 + 3000);
    logger.debug(TAG, "模拟浏览评论区 " + Math.round(commentPause / 1000) + "s");
    sleep(commentPause);
  }
};

/**
 * 生成拟人化的观看时长 — 基于对数正态分布
 * 大部分时间偏短，偶尔有长停留，符合真实用户行为
 * @param {number} min - 最小时长(ms)
 * @param {number} max - 最大时长(ms)
 * @param {number} median - 中位数(ms)，控制主体集中位置
 * @returns {number} 拟人化的时长(ms)
 */
NurtureHandler._humanDuration = function (min, max, median) {
  // 对数正态分布：ln(N(mu, sigma)) 产生右偏分布
  var mu = Math.log(median);
  var sigma = 0.5; // 控制离散程度，0.3-0.6 较自然
  // Box-Muller 变换生成正态随机数
  var u1 = Math.random();
  var u2 = Math.random();
  var z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  var value = Math.exp(mu + sigma * z);
  // 限制在 [min, max] 范围内
  return Math.max(min, Math.min(max, Math.round(value)));
};

/**
 * 检测当前屏幕是否为广告内容
 * @returns {boolean}
 */
NurtureHandler._isAdContent = function () {
  try {
    // 常见广告标识文本
    var adTexts = [
      "广告", "推广", "赞助", "购物", "立即购买", "查看详情",
      "立即下载", "免费领取", "限时优惠", "立即抢购", "点击购买",
      "小黄车", "商品橱窗", "去购买", "马上抢",
    ];
    for (var i = 0; i < adTexts.length; i++) {
      var el = textContains(adTexts[i]).findOne(2000);
      if (el) {
        logger.info(TAG, "发现广告标识: " + adTexts[i]);
        return true;
      }
    }
    // 检查是否在购物/商品页面（右下角有购物车图标）
    var shopBtn = desc("购物车").findOne(2000);
    if (shopBtn) {
      logger.info(TAG, "发现购物车标识，判定为广告");
      return true;
    }
    // 检查带货标签
    var sellTags = descContains("购物车").findOne(2000);
    if (sellTags) {
      logger.info(TAG, "发现带货标签，判定为广告");
      return true;
    }
  } catch (e) {
    // 检测失败不影响正常流程
  }
  return false;
};

/**
 * 检查当前视频内容是否与关键词矩阵相关
 * 先做本地关键词匹配，匹配不到再用 AI 语义分析
 * @param {string} videoText - 视频文本内容
 * @returns {boolean} true=相关或无关键词过滤, false=不相关
 */
NurtureHandler._isKeywordRelevant = function (videoText) {
  if (!this._keywordMatrix || this._keywordMatrix.length === 0) return true;
  if (!videoText || videoText.length < 2) return true;

  var t = videoText.toLowerCase();

  // 本地关键词匹配 — 快速判断
  for (var i = 0; i < this._keywordMatrix.length; i++) {
    if (t.indexOf(this._keywordMatrix[i].toLowerCase()) !== -1) {
      logger.debug(TAG, "本地命中关键词: " + this._keywordMatrix[i]);
      return true;
    }
  }

  // 本地未命中，用 AI 做语义分析
  var keywords = this._keywordMatrix.join("、");
  var prompt = "判断以下抖音视频内容是否与下列关键词相关。\n\n" +
    "关键词：" + keywords + "\n\n" +
    "内容：" + videoText.substring(0, 300) + "\n\n" +
    "只回答一个JSON：{\"related\": true/false, \"reason\": \"简短原因\"}";

  var content = aiAnalyzer._callAI(prompt, 100, 0.1);
  if (!content) {
    logger.warn(TAG, "关键词语义分析失败，默认放行");
    return true;
  }

  try {
    var jsonMatch = content.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      var data = JSON.parse(jsonMatch[0]);
      logger.info(TAG, "关键词相关性: " + (data.related ? "相关" : "不相关") + " - " + (data.reason || ""));
      return !!data.related;
    }
  } catch (e) {
    logger.warn(TAG, "关键词语义分析解析失败: " + e.message);
  }
  return true;
};

/**
 * 评估当前视频内容质量 — 基于可见的互动数据
 * @returns {"high" | "medium" | "low"}
 */
NurtureHandler._assessContentQuality = function () {
  try {
    // 尝试读取点赞数（控件 id 可能随版本变化）
    var likeCountEl = id("com.ss.android.ugc.aweme:id/like_count").findOne(2000);
    if (likeCountEl) {
      var likeText = likeCountEl.text() || "";
      var likeNum = this._parseCount(likeText);
      // 高赞内容判定：万级以上
      if (likeNum >= 10000) return "high";
      if (likeNum >= 1000) return "medium";
    }

    // 尝试读取评论数
    var commentCountEl = id("com.ss.android.ugc.aweme:id/comment_count").findOne(2000);
    if (commentCountEl) {
      var commentText = commentCountEl.text() || "";
      var commentNum = this._parseCount(commentText);
      if (commentNum >= 1000) return "high";
      if (commentNum >= 100) return "medium";
    }
  } catch (e) {
    // 读取失败时降级为随机判定
  }

  // 无法读取数据时，用概率模拟：20% 高、50% 中、30% 低
  var r = Math.random();
  if (r < 0.2) return "high";
  if (r < 0.7) return "medium";
  return "low";
};

/**
 * 解析抖音互动数字文本（支持 "1.2万"、"3.5亿" 等格式）
 * @param {string} text - 数字文本
 * @returns {number}
 */
NurtureHandler._parseCount = function (text) {
  if (!text) return 0;
  text = text.replace(/,/g, "").trim();
  if (text.indexOf("w") !== -1 || text.indexOf("万") !== -1) {
    return Math.round(parseFloat(text) * 10000);
  }
  if (text.indexOf("亿") !== -1) {
    return Math.round(parseFloat(text) * 100000000);
  }
  var num = parseInt(text, 10);
  return isNaN(num) ? 0 : num;
};

/**
 * 确保在推荐页 — 如果误触跳转到其他页面，返回推荐页
 * 使用选择器系统检测点赞按钮（推荐页特征），避免硬编码 ID 失效
 * 支持最多重试 5 次，每次优先 safeClick("back_btn")，失败则回退系统 back()
 */
NurtureHandler._ensureOnFeed = function () {
  var maxRetries = 5;
  for (var attempt = 0; attempt < maxRetries; attempt++) {
    try {
      // 检测是否在推荐页
      if (uiOperator.isOnPage("feed")) { flowContext.enter("feed"); return; }

      // 检测是否在有底部 tab 的主页面（首页/朋友/消息/我的）
      var homeTab = text("首页").findOne(2000);
      if (homeTab) {
        // 在主页但不在推荐视频流，点击"首页" tab
        logger.info(TAG, "在主页面，点击首页 tab（第" + (attempt + 1) + "次）");
        homeTab.parent().click();
        sleep(2000);
        continue;
      }

      logger.info(TAG, "不在推荐页（第" + (attempt + 1) + "次），尝试返回");

      // 优先使用选择器系统的 back_btn
      var backed = this.safeClick("back_btn", 1);
      if (!backed) {
        // 选择器找不到，回退到系统 back() — 万能兜底
        logger.info(TAG, "back_btn 未找到，使用系统 back()");
        back();
      }
      sleep(1500);
    } catch (e) {
      logger.warn(TAG, "页面检测异常: " + e.message);
      back(); // 异常时也尝试系统 back
      sleep(1000);
    }
  }
  logger.warn(TAG, maxRetries + " 次尝试后仍未回到推荐页");
};

NurtureHandler._likeCurrentVideo = function () {
  if (this._isAdContent()) {
    logger.info(TAG, "广告内容，跳过点赞");
    return;
  }
  var videoText = this._extractVideoText();
  if (!this._isKeywordRelevant(videoText)) {
    logger.info(TAG, "内容与关键词不相关，跳过点赞");
    return;
  }
  if (!aiAnalyzer.checkHealthRelevance(videoText)) {
    logger.info(TAG, "内容与大健康不相关，跳过点赞");
    return;
  }
  var clicked = this.safeClick("like_button", 2);
  if (clicked) {
    logger.info(TAG, "点赞成功");
  }
};

NurtureHandler._commentOnVideo = function (templateId) {
  if (this._isAdContent()) {
    logger.info(TAG, "广告内容，跳过评论");
    return;
  }
  var videoText = this._extractVideoText();
  if (!this._isKeywordRelevant(videoText)) {
    logger.info(TAG, "内容与关键词不相关，跳过评论");
    return;
  }
  // 1. AI 生成评论
  var content = aiAnalyzer.generateVideoComment(videoText);
  if (!content) {
    logger.warn(TAG, "AI 生成评论失败，跳过评论");
    return;
  }
  logger.info(TAG, "AI 生成评论: '" + content.substring(0, 20) + "'");

  // 预检评论数：零评论视频点评论按钮会直接唤起键盘，跳过
  var commentBtn = uiOperator.findElement("video_comment_btn", 2000);
  var cc = commentUtils.preCheckCommentCount(commentBtn);
  logger.info(TAG, "评论按钮 desc: '" + cc.rawDesc + "'");
  logger.info(TAG, "评论数: " + (cc.count >= 0 ? cc.count : "未知"));
  if (cc.count === 0) {
    logger.info(TAG, "该视频无评论，跳过评论");
    return;
  }

  // 2. 点击评论入口按钮，打开评论面板
  var opened = this.safeClick("video_comment_btn", 3);
  if (!opened) {
    logger.warn(TAG, "评论入口按钮未找到");
    return;
  }
  sleep(1500);

  // 3. 点击评论输入框，弹出键盘
  var inputClicked = this.safeClick("video_comment_input", 3);
  if (!inputClicked) {
    logger.warn(TAG, "评论输入框未找到");
    back();
    sleep(500);
    return;
  }
  sleep(1000);

  // 4. 输入评论内容
  var inputResult = this.safeInput("video_comment_input", content);
  if (!inputResult) {
    logger.warn(TAG, "输入评论内容失败");
    back();
    sleep(500);
    return;
  }
  sleep(500);

  // 5. 通过键盘回车提交评论
  sleep(500);
  this.submitViaKeyboard("comment_submit");
  sleep(1000);
  logger.info(TAG, "评论成功");

  // 6. 关闭评论面板
  this.safeClick("back_btn", 2);
  sleep(800);
};

NurtureHandler._followCurrentUser = function () {
  if (this._isAdContent()) {
    logger.info(TAG, "广告内容，跳过关注");
    return;
  }
  var videoText = this._extractVideoText();
  if (!this._isKeywordRelevant(videoText)) {
    logger.info(TAG, "内容与关键词不相关，跳过关注");
    return;
  }
  if (!aiAnalyzer.checkHealthRelevance(videoText)) {
    logger.info(TAG, "内容与大健康不相关，跳过关注");
    return;
  }
  var clicked = this.safeClick("follow_button", 2);
  if (clicked) {
    logger.info(TAG, "关注成功");
  }
};

// --- Legacy support ---
NurtureHandler._legacyExecute = function (params) {
  var duration = params.duration || 30;
  var actions = params.actions || [
    { type: "browse_feed", weight: 70 },
    { type: "like", weight: 20 },
    { type: "follow", weight: 10 },
  ];

  logger.info(TAG, "开始养号(旧版) " + duration + " 分钟");

  if (!this.ensureAppActive()) {
    return { success: false, error: "Failed to open Douyin" };
  }

  var startTime = Date.now();
  var endTime = startTime + duration * 60 * 1000;
  var stats = { videos_watched: 0, likes: 0, follows: 0, errors: 0 };

  while (Date.now() < endTime) {
    this._ensureOnFeed();
    var action = this._weightedRandom(actions);
    try {
      switch (action.type) {
        case "browse_feed":
          this._browseFeed();
          break;
        case "like":
          this._likeCurrentVideo();
          break;
        case "follow":
          this._followCurrentUser();
          break;
        default:
          this._browseFeed();
      }
    } catch (e) {
      logger.error(TAG, "养号操作 '" + action.type + "' 出错: " + e.message);
      stats.errors++;
    }
    antiDetect.humanSwipeUp();
    stats.videos_watched++;
  }

  stats.success_count = stats.likes + stats.follows;
  logger.info(TAG, "养号完成. 统计: " + JSON.stringify(stats));
  return { success: true, result: stats };
};

NurtureHandler._weightedRandom = function (actions) {
  var totalWeight = actions.reduce(function (sum, a) { return sum + a.weight; }, 0);
  var random = Math.random() * totalWeight;
  var cumulative = 0;
  for (var i = 0; i < actions.length; i++) {
    cumulative += actions[i].weight;
    if (random < cumulative) return actions[i];
  }
  return actions[0];
};

module.exports = NurtureHandler;
```

## handlers\search-like.js

```javascript
// device/handlers/search-like.js
var SearchBaseHandler = require("./search-base");
var apiClient = require("../core/api-client");
var logger = require("../utils/logger");

var TAG = "SEARCH_LIKE";

/**
 * 搜索点赞 Handler
 * params:
 *   - keyword: string (搜索关键词)
 *   - count: number (点赞数量)
 */
var SearchLikeHandler = Object.create(SearchBaseHandler);

/**
 * 对当前视频点赞
 */
SearchLikeHandler._interactWithVideo = function (content, stats) {
  var params = this._params || {};
  var clicked = this.safeClick("like_button", 2);
  if (clicked) {
    logger.info(TAG, "Liked video");
    stats.details.push("liked");
    try { apiClient.incrementStats(params.account_id, "search_like", 1); } catch (e) {}
    return true;
  }
  logger.warn(TAG, "Failed to like video");
  return false;
};

module.exports = SearchLikeHandler;
```

## handlers\search-comment.js

```javascript
// device/handlers/search-comment.js
var SearchBaseHandler = require("./search-base");
var aiAnalyzer = require("../core/ai-analyzer");
var uiOperator = require("../core/ui-operator");
var commentUtils = require("./comment-utils");
var apiClient = require("../core/api-client");
var logger = require("../utils/logger");

var TAG = "搜索评论";

/**
 * 搜索评论 Handler
 * params:
 *   - keyword: string (搜索关键词)
 *   - count: number (评论数量)
 *   - content: string (评论内容，可选，留空则 AI 根据视频内容生成)
 */
var SearchCommentHandler = Object.create(SearchBaseHandler);

/**
 * 对当前视频发表评论
 * 优先使用 params.content，留空则 AI 根据视频内容自动生成
 */
SearchCommentHandler._interactWithVideo = function (content, stats) {
  // 如果没有提供评论内容，提取视频文本并 AI 生成
  if (!content) {
    var videoText = this._extractVideoText();
    content = aiAnalyzer.generateVideoComment(videoText);
    if (!content) {
      logger.warn(TAG, "AI 生成评论失败，跳过");
      return false;
    }
    logger.info(TAG, "AI 生成评论: '" + content.substring(0, 30) + "'");
  }

  // 0. 确认进入视频详情页
  if (!uiOperator.isOnPage("is_video_view")) {
    logger.info(TAG, "未检测到视频详情页，尝试点击屏幕中心进入");
    press(Math.round(device.width * 0.5), Math.round(device.height * 0.5), 80);
    sleep(2000);
  }
  if (!uiOperator.isOnPage("is_video_view")) {
    logger.warn(TAG, "未进入视频详情页");
    return false;
  }
  var commentBtn = uiOperator.findElement("video_comment_btn", 3000);
  if (!commentBtn) {
    logger.warn(TAG, "评论入口按钮未找到");
    return false;
  }

  // 预检评论数：零评论视频点评论按钮会直接唤起键盘，跳过
  var cc = commentUtils.preCheckCommentCount(commentBtn);
  logger.info(TAG, "评论按钮 desc: '" + cc.rawDesc + "'");
  logger.info(TAG, "评论数: " + (cc.count >= 0 ? cc.count : "未知"));
  if (cc.count === 0) {
    logger.info(TAG, "该视频无评论，跳过");
    return false;
  }

  // 1. 点击评论入口按钮，打开评论面板
  var commentClicked = uiOperator.clickElement(commentBtn);
  if (!commentClicked) {
    logger.warn(TAG, "评论入口按钮点击失败");
    return false;
  }
  sleep(1500);

  // 2. 点击评论输入框，弹出键盘
  var inputClicked = this.safeClick("video_comment_input", 3);
  if (!inputClicked) {
    logger.warn(TAG, "评论输入框未找到");
    back();
    return false;
  }
  sleep(1000);

  // 3. 输入评论内容
  var inputResult = this.safeInput("video_comment_input", content);
  if (!inputResult) {
    logger.warn(TAG, "输入评论内容失败");
    back();
    return false;
  }
  sleep(500);

  // 4. 通过键盘回车发送
  sleep(500);
  this.submitViaKeyboard("comment_submit");
  sleep(1000);

  // 5. 关闭评论面板
  this.safeClick("back_btn", 2);
  sleep(800);

  logger.info(TAG, "评论成功: '" + content.substring(0, 20) + "'");
  stats.details.push("commented: " + content.substring(0, 30));
  try { apiClient.incrementStats((this._params || {}).account_id, "search_comment", 1); } catch (e) {}
  return true;
};

module.exports = SearchCommentHandler;
```

## handlers\search-collect.js

```javascript
// device/handlers/search-collect.js
var CommentBaseHandler = require("./comment-base");
var uiOperator = require("../core/ui-operator");
var aiAnalyzer = require("../core/ai-analyzer");
var apiClient = require("../core/api-client");
var logger = require("../utils/logger");
var commentUtils = require("./comment-utils");

var TAG = "采集";

var SearchCollectHandler = Object.create(CommentBaseHandler);

SearchCollectHandler._config = { videoTimeoutMs: 0, interVideoDelay: 1500, maxVideoCount: 200 };

SearchCollectHandler.execute = function (params) {
  if (params.share_links && params.share_links.length > 0) {
    return this._executeShareLinks(params);
  }
  return CommentBaseHandler.execute.call(this, params);
};

SearchCollectHandler._beforeSearch = function (params) {
  this._currentDest = aiAnalyzer.resolveDestination(params.keyword);
};

SearchCollectHandler._initStats = function (params) {
  return { success_count: 0, fail_count: 0, details: [],
    _taskId: params.task_id || "", _keyword: params.keyword || "" };
};

SearchCollectHandler._shouldProcessVideo = function (params, videoIndex) {
  // 残留在评论区则先退出
  if (uiOperator.isOnPage("is_comment_view")) {
    logger.info(TAG, "[耗时] 检测到评论面板残留，back 回到视频页");
    back();
    sleep(800);
  }
  return CommentBaseHandler._shouldProcessVideo.call(this, params, videoIndex);
};

SearchCollectHandler._closeComments = function () {
  this.safeClick("comment_off_btn", 2);
  sleep(400);
  if (uiOperator.isOnPage("is_comment_view")) {
    logger.info(TAG, "评论区未关闭，back 兜底");
    back();
    sleep(500);
  }
};

SearchCollectHandler._processComments = function (params, stats, videoIndex) {
  var keyword = params.keyword;
  var taskId = params.task_id || "";
  var maxComments = (params.count === -1) ? Infinity : (params.count || 50);
  var maxAgeDays = (params.max_age_days === -1) ? Infinity : (params.max_age_days || 30);
  var now = new Date();
  var cutoff = (maxAgeDays === Infinity) ? new Date(0) : new Date(now.getTime() - maxAgeDays * 24 * 60 * 60 * 1000);

  var dataSourceType = uiOperator.findElement("is_shopping_cart", 500) ? 1 : 0;
  logger.info(TAG, "[耗时] 数据来源类型: " + (dataSourceType === 1 ? "带货视频" : "普通视频"));

  var collected = 0;
  var visitedUsers = {};
  var seenComments = {};
  var consecutiveEmpty = 0;
  var consecutiveOld = 0;
  var scroll = 0;
  var reopenFailed = false;
  var t0 = Date.now();

  while (true) {
    if (consecutiveEmpty >= 5) {
      logger.info(TAG, "[耗时] 连续 " + consecutiveEmpty + " 轮无有效评论, 停止");
      break;
    }
    if (consecutiveOld >= 5) {
      logger.info(TAG, "[耗时] 连续 " + consecutiveOld + " 轮评论日期均超过 " + maxAgeDays + " 天, 停止");
      break;
    }

    var tScroll = Date.now();
    var items = uiOperator.findElements("comment_list", 2000);
    if (items.length === 0) { logger.info(TAG, "[耗时] 第 " + scroll + " 次滑动无评论项"); break; }
    logger.info(TAG, "[耗时] ══ 第 " + scroll + " 轮滚动, 可见 " + items.length + " 条评论 (查找耗时 " + (Date.now() - tScroll) + "ms)");

    var validThisScroll = 0;
    var oldThisScroll = 0;
    var localSkipped = 0;
    var aiSkipped = 0;
    var dupSkipped = 0;
    var tScrollStart = Date.now();

    for (var i = 0; i < items.length; i++) {
      if (collected >= maxComments) break;
      var tItem = Date.now();
      var comment = commentUtils.parseCommentItem(items[i], this);
      if (!comment) { logger.debug(TAG, "  [" + i + "] 解析失败 (" + (Date.now() - tItem) + "ms)"); continue; }

      if (!commentUtils.localPreFilter(comment.text)) {
        localSkipped++;
        logger.debug(TAG, "  [" + i + "] 本地淘汰(纯表情/短文本): " + comment.nickname);
        continue;
      }
      var localCheck = aiAnalyzer._localRelevanceCheck(comment.text);
      if (localCheck === false) {
        localSkipped++;
        logger.info(TAG, "  [" + i + "] 本地淘汰(exclude): " + comment.nickname);
        continue;
      }

      var commentDate = commentUtils.parseTime(comment.time);
      if (!commentDate || commentDate < cutoff) {
        oldThisScroll++;
        logger.debug(TAG, "  [" + i + "] 过期: " + comment.nickname);
        continue;
      }

      var dedupKey = comment.nickname + "|" + comment.text.substring(0, 80);
      if (seenComments[dedupKey]) { dupSkipped++; continue; }
      seenComments[dedupKey] = true;

      comment._keyword = keyword;
      var tAI = Date.now();
      if (!this._aiQualify(comment)) { aiSkipped++; logger.info(TAG, "  [" + i + "] AI淘汰: " + comment.nickname); continue; }
      validThisScroll++;

      logger.info(TAG, "  [" + i + "] ★符合: " + comment.nickname);
      var commentData = this._collectCommentData(items[i], comment);

      var userData = null;
      var needReopen = false;
      if (!visitedUsers[comment.nickname]) {
        visitedUsers[comment.nickname] = true;
        try {
          userData = this._collectUserData(items[i]);
        } catch (e) { logger.warn(TAG, "用户数据采集失败: " + e.message); }
        needReopen = true;
      }

      this._reportCollection(taskId, keyword, commentData, userData, dataSourceType);
      collected++;

      if (needReopen) {
        if (!this._openComments()) {
          logger.warn(TAG, "[耗时] 重新打开评论区失败，停止本视频采集");
          reopenFailed = true;
          break;
        }
        items = uiOperator.findElements("comment_list", 2000);
      }
    }

    if (reopenFailed) {
      logger.info(TAG, "[耗时] 评论区重开失败，停止 (已采集 " + collected + " 条)");
      break;
    }
    if (collected >= maxComments) {
      logger.info(TAG, "[耗时] 已采集 " + collected + " 条, 达到目标");
      break;
    }

    logger.info(TAG, "[耗时] ══ 第 " + scroll + " 轮完成: 符合=" + validThisScroll + " AI淘汰=" + aiSkipped + " 过期=" + oldThisScroll + " 本地淘汰=" + localSkipped + " 重复=" + dupSkipped);

    if (validThisScroll === 0 && oldThisScroll === 0) {
      consecutiveEmpty = aiSkipped > 0 ? 0 : consecutiveEmpty + 1;
      consecutiveOld = 0;
    } else if (validThisScroll === 0 && oldThisScroll > 0) {
      consecutiveEmpty = 0;
      consecutiveOld++;
    } else {
      consecutiveEmpty = 0;
      consecutiveOld = 0;
    }

    scroll++;
    uiOperator.swipeUp();
    sleep(500);

    if (uiOperator.findElement("is_comment_end", 500)) {
      logger.info(TAG, "[耗时] 评论已到底(is_comment_end), 停止 (第 " + scroll + " 次滚动)");
      break;
    }
  }

  logger.info(TAG, "[耗时] 视频采集完成: " + collected + " 条 (总耗时 " + (Date.now() - t0) + "ms)");
  stats.details.push("collected: " + collected);
  stats.success_count += collected;
};

SearchCollectHandler._openComments = function () {
  return commentUtils.openComments();
};

SearchCollectHandler._aiQualify = function (comment) {
  if (!comment || !comment.text) return false;
  try {
    var result = aiAnalyzer.analyzeComment({
      searchKeyword: (comment._keyword || ""),
      nickname: comment.nickname,
      commentText: comment.text,
    });
    if (result && typeof result.score === "number") return result.score >= 40;
    return result && result.qualified === true;
  } catch (e) { logger.warn(TAG, "AI分析失败: " + e.message); return false; }
};

SearchCollectHandler._collectCommentData = function (item, comment) {
  var timeStr = comment.time || "";
  var parsed = commentUtils.parseTime(timeStr);
  var isoTime = parsed ? parsed.toISOString() : timeStr;

  var data = {
    nickname: comment.nickname, content: comment.text, time_str: isoTime,
    reply_count: "", like_count: "", dislike_count: "", location: "", is_author: comment.isAuthor || false,
  };
  var dest = this._currentDest;
  if (dest) {
    data.intended_province = dest.province || "";
    data.intended_city = dest.city || "";
    data.intended_attraction = dest.attraction || "";
  }
  var extraFields = {
    "comment_reply_count": "reply_count", "comment_like_count": "like_count",
    "comment_dislike_count": "dislike_count", "comment_location": "location"
  };
  for (var actionName in extraFields) {
    var el = this._findChildBySelector(item, actionName);
    if (el) data[extraFields[actionName]] = this._extractChildValue(el, actionName, "");
  }
  if (data.location) data.location = data.location.replace(/^[·•・\s]+/, "");
  return data;
};

SearchCollectHandler._collectUserData = function (item) {
  var avatarEl = this._findChildBySelector(item, "comment_author_avatar");
  if (!avatarEl) { logger.warn(TAG, "头像未找到"); return null; }
  if (avatarEl.isImage || avatarEl.isCoordinate) { logger.warn(TAG, "头像为虚拟元素"); return null; }

  var avatarBase64 = commentUtils._cropCircularAvatar(avatarEl);

  try {
    var b = avatarEl.bounds();
    if (avatarEl.clickable()) {
      avatarEl.click();
    } else if (b) {
      press(b.centerX(), b.centerY(), 80);
    }
  } catch (e) { logger.warn(TAG, "头像点击失败"); return null; }
  sleep(1700);

  var data = commentUtils.collectProfileData({ uploadAvatar: false });

  if (avatarBase64 && data && data.douyin_id) {
    try { apiClient.uploadUserAvatar(data.douyin_id, avatarBase64); } catch (e) {}
  }

  back(); sleep(300);
  return data;
};

SearchCollectHandler._reportCollection = function (taskId, keyword, commentData, userData, dataSourceType) {
  var payload = { task_id: taskId, keyword: keyword, comment: commentData, data_source_type: dataSourceType || 0 };
  if (userData) payload.user = userData;
  var result = apiClient.collectReport(payload);
  if (result && result.comment_saved) logger.debug(TAG, "已上报: " + commentData.nickname);
  try { apiClient.incrementStats((this._params || {}).account_id, "collect", 1); } catch (e) {}
};

SearchCollectHandler.execute = function (params) {
  if (params.share_links && params.share_links.length > 0) {
    return this._executeShareLinks(params);
  }
  return CommentBaseHandler.execute.call(this, params);
};

SearchCollectHandler._executeShareLinks = function (params) {
  var links = params.share_links;
  var taskId = params.task_id || "";
  logger.info(TAG, "分享链接采集: " + links.length + " 个链接, 关键词='" + (params.keyword || "") + "'");
  var linkStats = { success_count: 0, fail_count: 0, details: [], _taskId: taskId, _keyword: params.keyword || "" };

  for (var li = 0; li < links.length; li++) {
    var link = (links[li] || "").trim();
    if (!link) continue;
    logger.info(TAG, "第 " + (li + 1) + "/" + links.length + " 个链接: " + link.substring(0, 40) + "...");

    if (!this._openSearch()) { linkStats.fail_count++; continue; }
    var urlMatch = link.match(/https?:\/\/v\.douyin\.com\/[A-Za-z0-9_?=&%]+\/?/);
    var pasteText = urlMatch ? urlMatch[0] : link;
    if (!this._inputKeyword(pasteText)) { linkStats.fail_count++; continue; }
    sleep(300);
    if (!this._submitSearch()) { linkStats.fail_count++; continue; }
    sleep(2000);
    if (!uiOperator.isOnPage("is_video_view")) {
      logger.info(TAG, "未自动跳转视频页，尝试点击搜索结果");
      this._clickSearchResult(0);
      sleep(1700);
    }

    if (!CommentBaseHandler._shouldProcessVideo.call(this, params, 0)) { linkStats.fail_count++; }
    else if (commentUtils.openComments()) {
      this._processComments(params, linkStats, 0);
    } else { linkStats.fail_count++; }

    this.safeClick("comment_off_btn", 2);
    sleep(400);
    this._backToSearchResults();
  }
  logger.info(TAG, "链接采集完成: " + JSON.stringify(linkStats));
  return { success: true, result: linkStats };
};


module.exports = SearchCollectHandler;
```

## handlers\search-dm.js

```javascript
// device/handlers/search-dm.js
var SearchBaseHandler = require("./search-base");
var aiAnalyzer = require("../core/ai-analyzer");
var apiClient = require("../core/api-client");
var logger = require("../utils/logger");

var TAG = "搜索私信";

/**
 * 搜索私信 Handler
 * params:
 *   - keyword: string (搜索关键词 — 用于搜索用户)
 *   - count: number (私信数量)
 *   - content: string (私信内容，可选，留空则 AI 根据视频内容生成)
 */
var SearchDMHandler = Object.create(SearchBaseHandler);

/**
 * 打开搜索结果后，进入用户主页并发送私信序列
 * 支持 DM 序列模板、单条内容、AI 生成
 */
SearchDMHandler._interactWithVideo = function (content, stats) {
  var params = this._params || {};
  var messages = this.resolveMessages(params);
  if (!messages || messages.length === 0) {
    logger.warn(TAG, "无法获取私信内容，跳过");
    return false;
  }

  // 1. 点击视频作者头像进入主页
  var avatarClicked = this.safeClick("video_author_avatar", 2);
  if (!avatarClicked) {
    logger.warn(TAG, "未找到作者头像");
    return false;
  }
  sleep(2000);

  // 2. 点击私信按钮
  var messageClicked = this.safeClick("dm_entry_btn", 3);
  if (!messageClicked) {
    logger.warn(TAG, "私信按钮未找到");
    return false;
  }
  sleep(1500);

  // 3. 发送消息序列
  var sentCount = this._sendMessageSequence(messages, stats, params.keyword);
  if (sentCount <= 0) {
    logger.warn(TAG, "私信序列没有成功发送任何消息");
    return false;
  }
  try { apiClient.incrementStats(params.account_id, "search_dm", 1); } catch (e) {}
  return true;
};

module.exports = SearchDMHandler;
```

## handlers\reply-comment.js

```javascript
// device/handlers/reply-comment.js
var CommentBaseHandler = require("./comment-base");
var aiAnalyzer = require("../core/ai-analyzer");
var uiOperator = require("../core/ui-operator");
var selectorLoader = require("../core/selector-loader");
var antiDetect = require("../core/anti-detect");
var apiClient = require("../core/api-client");
var logger = require("../utils/logger");
var commentUtils = require("./comment-utils");

var TAG = "评论回复";
var flowContext = require("../core/flow-context");

var ReplyCommentHandler = Object.create(CommentBaseHandler);

ReplyCommentHandler._config = { videoTimeoutMs: 120000, interVideoDelay: 2500, defaultVideoCount: 3 };

ReplyCommentHandler._beforeSearch = function (params) {
  this._dest = aiAnalyzer.resolveDestination(params.keyword);
};

ReplyCommentHandler._initStats = function (params) {
  return { videos_processed: 0, success_count: 0, fail_count: 0, skipped: 0,
    follow_count: 0, dm_count: 0, details: [] };
};

ReplyCommentHandler._onVideoSkipped = function (params, stats, videoIndex) {
  stats.videos_processed++;
};

ReplyCommentHandler._ensureCommentsOpen = function (params, videoIndex) {
  var videoStartTime = Date.now();
  var VIDEO_TIMEOUT = this._config.videoTimeoutMs;
  for (var retry = 0; retry < 2; retry++) {
    if (Date.now() - videoStartTime > VIDEO_TIMEOUT) break;
    this.safeClick("video_comment_btn", 2);
    sleep(2000);
    if (uiOperator.isOnPage("is_comment_view")) {
      flowContext.enter("comment");
      return true;
    }
    logger.info(TAG, "评论区未打开，重试 (" + (retry + 1) + "/2)");
  }
  logger.warn(TAG, "评论区打开失败，跳过此视频");
  return false;
};

ReplyCommentHandler._processComments = function (params, stats, videoIndex) {
  var keyword = params.keyword;
  var content = params.content || "";
  var count = (params.count === -1) ? Infinity : (params.count || 5);
  var maxAgeDays = (params.max_age_days === -1) ? Infinity : (params.max_age_days || 5);
  var maxFollows = params.max_follows || 20;
  var maxDMs = params.max_dms || 10;
  var taskId = params.task_id || "";
  var dest = this._dest;
  var VIDEO_TIMEOUT = this._config.videoTimeoutMs;

  // 当有 DM 序列时，扩展视频超时以容纳 cooldown
  var hasDMSequence = !!(params.dm_sequence_id || (params.dm_messages && params.dm_messages.length > 0));
  var dmCooldownMs = params.inter_user_cooldown_ms || (Math.floor(Math.random() * 100000) + 100000);
  if (hasDMSequence && dmCooldownMs > 0) {
    var maxDMsThisTask = params.max_dms || 10;
    VIDEO_TIMEOUT = Math.max(VIDEO_TIMEOUT, maxDMsThisTask * dmCooldownMs + 60000);
  }

  function _reportProgress(step, detail, prog) {
    if (taskId) { try { apiClient.reportProgress(taskId, step, detail, prog); } catch (e) {} }
  }

  // 日DM计数器
  function _getServerDate() {
    // 优先用服务端日期（main.js catchUpPoll 设置）
    if (SearchBaseHandler._serverDate) return SearchBaseHandler._serverDate;
    var d = new Date();
    return d.getFullYear() + "-" + (d.getMonth() + 1) + "-" + d.getDate();
  }

  function _getDailyDMCount() {
    var dateKey = _getServerDate();
    return SearchBaseHandler._storageGet("dm_daily_" + dateKey, 0);
  }

  function _incrementDailyDMCount() {
    var dateKey = _getServerDate();
    var current = SearchBaseHandler._storageGet("dm_daily_" + dateKey, 0);
    SearchBaseHandler._storageSet("dm_daily_" + dateKey, current + 1);

    // 清理3天前过期计数器
    try {
      var cacheDir = SearchBaseHandler._getCacheDir();
      var flist = files.listDir(cacheDir);
      var cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - 3);
      var cutoffKey = "dm_daily_" + cutoff.getFullYear() + "-" + (cutoff.getMonth() + 1) + "-" + cutoff.getDate();
      for (var fi = 0; fi < flist.length; fi++) {
        if (flist[fi].indexOf("dm_daily_") === 0 && flist[fi] < cutoffKey) {
          try { files.remove(cacheDir + "/" + flist[fi]); } catch (e) {}
        }
      }
    } catch (e) {}

    return current + 1;
  }


  function _getDailyReplyCount() {
    var dateKey = _getServerDate();
    return SearchBaseHandler._storageGet("reply_daily_" + dateKey, 0);
  }

  function _incrementDailyReplyCount() {
    var dateKey = _getServerDate();
    var current = SearchBaseHandler._storageGet("reply_daily_" + dateKey, 0);
    SearchBaseHandler._storageSet("reply_daily_" + dateKey, current + 1);
    return current + 1;
  }

  function _getDailyFollowCount() {
    var dateKey = _getServerDate();
    return SearchBaseHandler._storageGet("follow_daily_" + dateKey, 0);
  }

  function _incrementDailyFollowCount() {
    var dateKey = _getServerDate();
    var current = SearchBaseHandler._storageGet("follow_daily_" + dateKey, 0);
    SearchBaseHandler._storageSet("follow_daily_" + dateKey, current + 1);
    return current + 1;
  }

  // 用服务端每日计数初始化本地计数器，保证日志与服务端同步
  function _syncDailyCounters() {
    var dateKey = _getServerDate();
    logger.info(TAG, "开始同步每日计数 (date=" + dateKey + " srvReply=" + params.server_today_reply + " srvFollow=" + params.server_today_follow + " srvDM=" + params.server_today_dm + ")");
    var synced = 0;
    if (params.server_today_reply != null) {
      var localReply = SearchBaseHandler._storageGet("reply_daily_" + dateKey, 0);
      SearchBaseHandler._storageSet("reply_daily_" + dateKey, Math.max(localReply, params.server_today_reply));
      synced++;
    }
    if (params.server_today_follow != null) {
      var localFollow = SearchBaseHandler._storageGet("follow_daily_" + dateKey, 0);
      SearchBaseHandler._storageSet("follow_daily_" + dateKey, Math.max(localFollow, params.server_today_follow));
      synced++;
    }
    if (params.server_today_dm != null) {
      var localDM = SearchBaseHandler._storageGet("dm_daily_" + dateKey, 0);
      SearchBaseHandler._storageSet("dm_daily_" + dateKey, Math.max(localDM, params.server_today_dm));
      synced++;
    }
    if (synced === 0) {
      logger.warn(TAG, "每日计数同步失败: server_today_* 均为 null，params 缺少服务端注入字段");
    }
  }
  _syncDailyCounters();
  var videoStartTime = Date.now();
  var processed = 0;
  var totalRead = 0;
  var emptyStreak = 0;
  var noNewStreak = 0;
  var seenComments = {};

  function _commentKey(comment) {
    var nick = comment && comment.nickname ? comment.nickname : "";
    var text = comment && comment.text ? comment.text : "";
    var time = comment && comment.time ? comment.time : "";
    return nick + "|" + text + "|" + time;
  }

  function _hasCommentEndMarker() {
    try {
      if (!selectorLoader._cache || !selectorLoader._cache.is_comment_end) return false;
      return !!uiOperator.findElement("is_comment_end", 500);
    } catch (e) {
      return false;
    }
  }

  var items = uiOperator.findElements("comment_list", 3000);

  while (processed < count) {
    if (items.length === 0) {
      emptyStreak++;
      if (emptyStreak >= 2) {
        logger.info(TAG, "评论列表连续为空，已到底");
        break;
      }
    } else {
      emptyStreak = 0;
    }
    if (Date.now() - videoStartTime > VIDEO_TIMEOUT) {
      logger.warn(TAG, "视频 " + (videoIndex + 1) + " 处理超时 (" +
        Math.round((Date.now() - videoStartTime) / 1000) + "s)，强制跳过");
      break;
    }

    var newThisRound = 0;
    for (var i = 0; i < items.length && processed < count; i++) {
      if (Date.now() - videoStartTime > VIDEO_TIMEOUT) {
        logger.warn(TAG, "评论处理超时，跳出内循环");
        break;
      }
      try {
      var comment = this._parseCommentItem(items[i]);
      if (!comment) { stats.skipped++; totalRead++; continue; }

      var commentKey = _commentKey(comment);
      if (seenComments[commentKey]) continue;
      seenComments[commentKey] = true;
      newThisRound++;

      if (comment.nickname === "unknown" || !comment.text ||
          comment.text.indexOf("发条评论") !== -1) {
        stats.skipped++; totalRead++; continue;
      }

      if (comment.isAuthor) {
        logger.info(TAG, "跳过作者评论: " + comment.nickname);
        stats.skipped++; totalRead++; continue;
      }

      if (!this._filterByTime([comment], maxAgeDays).length) {
        stats.skipped++; totalRead++; continue;
      }

      if (!commentUtils.localPreFilter(comment.text)) {
        logger.debug(TAG, "跳过无意义评论（纯表情/短文本）: " + comment.text.substring(0, 20));
        stats.skipped++; totalRead++;
        continue;
      }

      var canReply = true;
      try {
        var claimResult = apiClient.claimCommentReply(comment.nickname, comment.text);
        canReply = claimResult && claimResult.claimed;
      } catch (e) {}
      if (!canReply) {
        logger.info(TAG, "评论已被回复过（全局去重）: " + comment.nickname);
        stats.skipped++; totalRead++;
        continue;
      }

      logger.info(TAG, "分析 " + (processed + 1) + "/" + count +
        ": [" + comment.nickname + "] " + comment.text.substring(0, 30));

      var analysis = aiAnalyzer.analyzeComment({
        searchKeyword: keyword,
        nickname: comment.nickname,
        commentText: comment.text,
      });

      if (!analysis) {
        stats.skipped++; totalRead++;
        continue;
      }

      logger.info(TAG, "分数=" + analysis.score + ", 层级=" + analysis.tier +
        ", 意图=" + (analysis.dimensions ? analysis.dimensions.intent : "未知"));

      if (analysis.score < aiAnalyzer.SCORE_THRESHOLD) {
        logger.info(TAG, "分数 " + analysis.score + " 低于阈值，跳过");
        stats.skipped++; totalRead++;
        continue;
      }

      if (analysis.dimensions && analysis.dimensions.lead_quality) {
        var lq = analysis.dimensions.lead_quality;
        if (lq.is_bot || lq.is_competitor) {
          logger.info(TAG, "检测到水军/同行，跳过");
          stats.skipped++; totalRead++;
          continue;
        }
      }

      // 回复
      logger.debug(TAG, "回复: '" + analysis.reply.substring(0, 30) + "...'");
      if (comment.replyBtn) {
        logger.info(TAG, "点击回复按钮...");
        comment.replyBtn.click();
        sleep(1000);
      } else {
        logger.info(TAG, "无回复按钮，直接输入");
      }
      logger.info(TAG, "开始输入回复...");
      if (this._replyToComment(analysis.reply, comment.nickname)) {
        stats.success_count++;
        try { apiClient.incrementStats(params.account_id, "reply_comment", 1); } catch (e) {}
        var dailyReply = _incrementDailyReplyCount();
        logger.info(TAG, "当日回复: " + dailyReply + "/" + (params.server_daily_limit_reply != null ? params.server_daily_limit_reply : (params.max_daily_reply || 200)));
        try { apiClient.saveCommentAIReply(comment.nickname, comment.text, analysis.reply, taskId, dest ? dest.province : null, dest ? dest.city : null, dest ? dest.attraction : null); } catch (e) {}
        try {
          var commentReport = {
            nickname: comment.nickname, content: comment.text,
             time_str: commentUtils.toBeijingTime(comment.time), is_author: comment.isAuthor || false,
            reply_count: "", like_count: "", ai_reply: analysis.reply,
          };
          if (dest) {
            commentReport.intended_province = dest.province || "";
            commentReport.intended_city = dest.city || "";
            commentReport.intended_attraction = dest.attraction || "";
          }
          apiClient.collectReport({ task_id: taskId, keyword: keyword, comment: commentReport, data_source_type: 0 });
        } catch (e) {}
      } else {
        stats.fail_count++;
        try { apiClient.releaseCommentReply(comment.nickname, comment.text); } catch (e) {}
        totalRead++;
        continue;
      }

      stats.details.push({
        video: videoIndex + 1, nickname: comment.nickname,
        comment: comment.text,
        score: analysis.score, tier: analysis.tier,
        intent: analysis.dimensions ? analysis.dimensions.intent : "unknown",
        reply: analysis.reply,
      });

      // 关注+私信
      sleep(Math.floor(Math.random() * 500 + 800));
      var shouldFollow = analysis.tier === "high" || analysis.tier === "medium";
      var shouldDM = analysis.tier === "high" || analysis.tier === "medium";
      var canFollow = shouldFollow && stats.follow_count < maxFollows;
      var canDM = shouldDM && stats.dm_count < maxDMs;
      // 协调 per-task maxDMs 与日上限（-1 = 不限）
      var maxDaily = params.max_daily_dm || 75;
      if (maxDaily !== -1) {
        var todayRemaining = maxDaily - _getDailyDMCount();
        if (canDM && todayRemaining <= 0) {
          logger.warn(TAG, "当日DM已达上限(" + maxDaily + ")，跳过私信");
          canDM = false;
        }
      }
      if (canFollow || canDM) {
        if (this._enterCommenterProfile(comment.commentAuthorAvatarEl, comment.nickname)) {
          var profileStart = Date.now();
          var PROFILE_TIMEOUT = hasDMSequence
            ? Math.max(30000, (dmCooldownMs || 0) + 15000)
            : 30000;

          var isPrivate = !!uiOperator.findElement("user_is_private", 2000);
          if (isPrivate) {
            logger.info(TAG, "私密账号，跳过关注，仅尝试私信");
            canFollow = false;
          }
          {
            var userData = this._collectProfileData();
            if (userData) {
              var lastDetail = stats.details[stats.details.length - 1];
              if (lastDetail) lastDetail.user = userData;
              userData._keyword = keyword;
              userData._taskId = taskId;
              if (dest) {
                userData._intended_province = dest.province || "";
                userData._intended_city = dest.city || "";
                userData._intended_attraction = dest.attraction || "";
              }
              try { apiClient.saveUserProfile(userData); } catch (e) {}
              try { apiClient.collectReport({
                task_id: taskId, keyword: keyword,
                comment: { nickname: comment.nickname, content: comment.text, time_str: commentUtils.toBeijingTime(comment.time), is_author: comment.isAuthor || false },
                user: userData, data_source_type: 0,
              }); } catch (e) {}
            }
            if (Date.now() - profileStart < PROFILE_TIMEOUT && canFollow && this._followUser()) {
              stats.follow_count++;
              try { apiClient.incrementStats(params.account_id, "follow", 1); } catch (e) {}
              var dailyFollow = _incrementDailyFollowCount();
              logger.info(TAG, "当日关注: " + dailyFollow + "/" + (params.server_daily_limit_follow != null ? params.server_daily_limit_follow : (params.max_daily_follow || 100)));
            }
            sleep(Math.floor(Math.random() * 500 + 800));

            // DM cooldown: 发送前等待冷却时间，序列和单条共用
            if (canDM && this._lastDMSendTime) {
              var cooldownRemaining = (dmCooldownMs || 0) - (Date.now() - this._lastDMSendTime);
              if (cooldownRemaining > 0) {
                logger.info(TAG, "DM冷却等待 " + Math.round(cooldownRemaining / 1000) + "s");
              var chunkMs = 30000;
              var waited = 0;
              while (waited < cooldownRemaining) {
                var step = Math.min(chunkMs, cooldownRemaining - waited);
                sleep(step);
                waited += step;
                if (waited < cooldownRemaining) {
                  try { device.wakeUpIfNeeded(); } catch(e) {}
                }
              }
              }
            }

            if (Date.now() - profileStart < PROFILE_TIMEOUT && canDM) {
              var dmContent = "";
              var dmIntent = "other";
              try {
                dmIntent = (analysis.dimensions && analysis.dimensions.intent) || "other";
                if (!hasDMSequence) {
                  var aiDM = aiAnalyzer.generateDM({
                    searchKeyword: keyword, nickname: comment.nickname,
                    commentText: comment.text, tier: dmIntent,
                    intendedCity: (dest && (dest.city || dest.attraction || dest.province)) || "",
                  });
                  if (aiDM) dmContent = aiDM;
                }
              } catch (e) {}
              if (!hasDMSequence && !dmContent && content) dmContent = content;
              if (hasDMSequence || dmContent) {
                var recipientId = (userData && userData.douyin_id) || "";
                if (recipientId) {
                  var dmClaimResult = apiClient.claimDMRecipient({
                    account_id: params.account_id,
                    recipient_douyin_id: recipientId,
                    recipient_nickname: comment.nickname,
                  });
                  if (dmClaimResult && dmClaimResult.claimed) {
                    var sent, reportedContent;
                    // DM 序列模板 vs 单条私信
                    if (hasDMSequence) {
                      var seqMsgs = this.resolveMessages(params);
                      if (!seqMsgs || !seqMsgs.map) { seqMsgs = []; }
                      var dmBtnOk = this.safeClick("dm_entry_btn", 3);
                      if (dmBtnOk) { sleep(1500); }
                      if (dmBtnOk && seqMsgs.length > 0) {
                        var seqSent = this._sendMessageSequence(seqMsgs, stats, keyword);
                        sent = seqSent > 0;
                        reportedContent = seqMsgs.map(function(m){return m.content;}).join(" | ");
                        if (sent) { try { apiClient.incrementStats(params.account_id, "search_dm", 1); } catch (e) {} }
                      } else {
                        sent = false;
                        reportedContent = dmContent;
                      }
                    } else {
                      sent = this._sendDM(dmContent);
                      reportedContent = dmContent;
                    }
                    if (sent) {
                      apiClient.reportDMSend({
                        conversation_id: dmClaimResult.conversation_id,
                        stage: dmIntent, intent: dmIntent, keyword: keyword, content: reportedContent,
                      });
                      stats.dm_count++;
                      if (!hasDMSequence) { try { apiClient.incrementStats(params.account_id, "search_dm", 1); } catch (e) {} }
                      if (hasDMSequence) {
                        this._lastDMSendTime = Date.now();
                        var dailyCount = _incrementDailyDMCount();
                        logger.info(TAG, "当日DM: " + dailyCount + "/" + (params.server_daily_limit_dm != null ? params.server_daily_limit_dm : (params.max_daily_dm || 75)));
                      }
                    } else {
                      apiClient.releaseDMRecipient({ conversation_id: dmClaimResult.conversation_id });
                    }
                  } else {
                    logger.info(TAG, "用户 " + comment.nickname + " 已被其他设备 DM，跳过");
                  }
                } else {
                  var fbNick = comment.nickname || "unknown";
                  var fbHash = 0;
                  for (var hi = 0; hi < fbNick.length; hi++) {
                    fbHash = ((fbHash << 5) - fbHash) + fbNick.charCodeAt(hi); fbHash |= 0;
                  }
                  var fallbackId = "fb_" + Math.abs(fbHash).toString(16);
                  dmClaimResult = apiClient.claimDMRecipient({
                    account_id: params.account_id,
                    recipient_douyin_id: fallbackId,
                    recipient_nickname: comment.nickname,
                  });
                  if (dmClaimResult && dmClaimResult.claimed) {
                    var sent2, reportedContent2;
                    if (hasDMSequence) {
                      var seqMsgs2 = this.resolveMessages(params);
                      if (!seqMsgs2 || !seqMsgs2.map) { seqMsgs2 = []; }
                      var dmBtnOk2 = this.safeClick("dm_entry_btn", 3);
                      if (dmBtnOk2) { sleep(1500); }
                      if (dmBtnOk2 && seqMsgs2.length > 0) {
                        var seqSent2 = this._sendMessageSequence(seqMsgs2, stats, keyword);
                        sent2 = seqSent2 > 0;
                        reportedContent2 = seqMsgs2.map(function(m){return m.content;}).join(" | ");
                        if (sent2) { try { apiClient.incrementStats(params.account_id, "search_dm", 1); } catch (e) {} }
                      } else {
                        sent2 = false;
                        reportedContent2 = dmContent;
                      }
                    } else {
                      sent2 = this._sendDM(dmContent);
                      reportedContent2 = dmContent;
                    }
                    if (sent2) {
                      apiClient.reportDMSend({
                        conversation_id: dmClaimResult.conversation_id,
                        stage: dmIntent, intent: dmIntent, keyword: keyword, content: reportedContent2,
                      });
                      stats.dm_count++;
                      if (!hasDMSequence) { try { apiClient.incrementStats(params.account_id, "search_dm", 1); } catch (e) {} }
                      if (hasDMSequence) {
                        this._lastDMSendTime = Date.now();
                        var dailyCount = _incrementDailyDMCount();
                        logger.info(TAG, "当日DM: " + dailyCount + "/" + (params.server_daily_limit_dm != null ? params.server_daily_limit_dm : (params.max_daily_dm || 75)));
                      }
                    } else {
                      apiClient.releaseDMRecipient({ conversation_id: dmClaimResult.conversation_id });
                    }
                  }
                }
              }
              sleep(Math.floor(Math.random() * 500 + 800));
            }
          }

          if (Date.now() - profileStart > PROFILE_TIMEOUT) {
            logger.warn(TAG, "主页操作超时 (" + Math.round((Date.now() - profileStart) / 1000) + "s)，强制返回");
          }

          this._returnToComments();
          var onComment = uiOperator.isOnPage("is_comment_view");
          if (!onComment) {
            back(); sleep(800);
            this._openComments();
            sleep(1500);
            onComment = uiOperator.isOnPage("is_comment_view");
          }
          if (!onComment) {
            logger.warn(TAG, "返回评论区失败，跳过后续评论");
            processed = count;
            break;
          }
          uiOperator.swipeUp();
          sleep(800);
          items = uiOperator.findElements("comment_list", 3000);
          videoStartTime = Date.now();
          i = -1;
        } else {
          logger.warn(TAG, "进入主页失败，跳过关注+私信");
          this._dismissKeyboard();
        }
      }
      sleep(1000);

      processed++;
      totalRead++;
      _reportProgress("视频 " + (videoIndex + 1) + "/" + params.video_count,
        "已回复 " + stats.success_count + " 条，跳过 " + stats.skipped + " 条",
        (videoIndex + processed / count) / (params.video_count || 3));
      antiDetect.maybePause();
      } catch (e) {
        logger.error(TAG, "处理评论异常: " + e.message + "，跳过继续");
        stats.skipped++; totalRead++;
        try { this._returnToComments(); } catch (e2) {}
      }
    }

    if (newThisRound === 0) {
      noNewStreak++;
      if (_hasCommentEndMarker()) {
        logger.info(TAG, "评论已到底(is_comment_end)，停止（可见" + items.length + "条/已读" + totalRead + "条）");
        break;
      }
      if (noNewStreak >= 3) {
        logger.info(TAG, "连续" + noNewStreak + "轮未发现新评论，停止（可见" + items.length + "条/已读" + totalRead + "条）");
        break;
      }
    } else {
      noNewStreak = 0;
    }

    if (processed < count) {
      if (_hasCommentEndMarker()) {
        logger.info(TAG, "评论已到底(is_comment_end)，停止（已读" + totalRead + "条）");
        break;
      }
      uiOperator.swipeUp();
      sleep(1500);
      items = uiOperator.findElements("comment_list", 3000);
    }
  }
};

/**
 * 打开评论区 — 点击视频评论入口按钮
 */
ReplyCommentHandler._openComments = function () {
  return commentUtils.openComments();
};

/**
 * 读取评论列表
 * 使用 findElements 直接获取所有评论控件（不走 children）
 * 支持滑动加载更多评论
 * @param {number} maxCount - 最多读取数量
 * @returns {Array} [{ nickname, text, time, element }]
 */
ReplyCommentHandler._readComments = function (maxCount) {
  var comments = [];

  try {
    // 等待评论面板打开
    sleep(1000);

    // 使用 findElements 直接获取评论控件数组
    var items = uiOperator.findElements("comment_list", 5000);
    if (!items || items.length === 0) {
      logger.warn(TAG, "评论列表未找到或为空");
      return comments;
    }
    logger.info(TAG, "评论列表: " + items.length + " 条");

    // 滑动加载更多直到满足数量要求
    var maxScroll = 10;
    var lastProcessed = 0; // 已处理到的下标，避免重复解析
    for (var scroll = 0; scroll < maxScroll && comments.length < maxCount; scroll++) {
      for (var i = lastProcessed; i < items.length && comments.length < maxCount; i++) {
        var comment = this._parseCommentItem(items[i]);
        if (comment) {
          comments.push(comment);
        }
      }
      lastProcessed = items.length;

      if (comments.length < maxCount) {
        logger.info(TAG, "已读取 " + comments.length + "/" + maxCount + " 条，滑动加载更多...");
        uiOperator.swipeUp();
        sleep(1500);
        items = uiOperator.findElements("comment_list", 3000);
      }
    }
  } catch (e) {
    logger.error(TAG, "读取评论出错: " + e.message);
  }

  return comments;
};

/**
 * 解析单条评论
 * 使用服务端下发的选择器策略查找子元素
 * @param {UiObject} item - 评论项元素
 * @returns {Object|null} { nickname, text, time, element }
 */
ReplyCommentHandler._parseCommentItem = function (item) {
  var result = commentUtils.parseCommentItem(item, this);
  if (result) result.element = item;  // 保持向后兼容
  return result;
};


/**
 * 按时效筛选评论
 * @param {Array} comments
 * @param {number} maxAgeDays
 * @returns {Array} 筛选后的评论
 */
ReplyCommentHandler._filterByTime = function (comments, maxAgeDays) {
  return commentUtils.filterByTime(comments, maxAgeDays);
};

/**
 * 解析评论时间
 * 支持格式:
 * - "刚刚"
 * - "X分钟前", "X小时前", "X天前"
 * - "MM-DD", "YYYY-MM-DD"
 * @param {string} timeStr
 * @returns {Date|null}
 */
ReplyCommentHandler._parseTime = function (timeStr) {
  return commentUtils.parseTime(timeStr);
};

/**
 * 回复评论
 * 流程: 点回复(键盘唤起+输入框聚焦) → input()模拟打字 → 图找图发送
 */
ReplyCommentHandler._replyToComment = function (replyText, nickname) {
  // 1. 点回复按钮 → 键盘唤起，输入框自动获得焦点
  // if (!this.safeClick("comment_reply_button", 3)) {
  //   logger.warn(TAG, "回复按钮未找到");
  //   return false;
  // }
  // sleep(1000);

  // 2. 输入文字：input() 直接模拟键盘打字（输入框已聚焦，比 setText/粘贴都可靠）
  // 安全裁剪：AI 可能误加前缀
  var cleanText = replyText;
  // 裁剪「回复 @昵称」
  if (nickname) {
    var prefix = "回复 @" + nickname;
    if (cleanText.indexOf(prefix) === 0) {
      cleanText = cleanText.substring(prefix.length).replace(/^\s*/, "");
    }
  }
  // 裁剪 AI 误输出的元格式「评论'xxx' → 回复：'yyy'」，只保留 yyy 部分
  var arrowIdx = cleanText.indexOf("→ 回复：");
  if (arrowIdx !== -1) {
    cleanText = cleanText.substring(arrowIdx + 5).replace(/^['\"\s]+/, "").replace(/['\"]+$/, "");
  }
  var pasted = false;
  try {
    var focusedNode = className("EditText").focused(true).findOne(500);
    if (focusedNode) {
        focusedNode.setText(" ");
        sleep(200);
        for (var di = 0; di < 5; di++) { shell("input keyevent 67", false); }
        sleep(100);
    }
    // 分块模拟真人打字：2-3 个词一起敲、单字单独敲，块间随机延迟
    var pos = 0;
    while (pos < cleanText.length) {
      var chunkSize = Math.random() < 0.4 ? 1 : (Math.floor(Math.random() * 2) + 2);  // 40% 单字, 60% 2-3字
      chunkSize = Math.min(chunkSize, cleanText.length - pos);
      var chunk = cleanText.substring(pos, pos + chunkSize);
      input(chunk);
      pos += chunkSize;
      sleep(Math.floor(Math.random() * 250 + 150));  // 150-400ms 块间停顿
    }
    pasted = true;
    logger.debug(TAG, "input 输入成功: " + cleanText.substring(0, 20) + "'");
  } catch (e) {
    logger.warn(TAG, "input 异常: " + e.message);
  }

  // 3. 兜底：剪贴板 + keyevent 279 粘贴
  if (!pasted) {
    try {
      setClip(cleanText);
      sleep(200);
      shell("input keyevent 279", false);
      sleep(500);
      pasted = true;
    } catch (e) { /* ignore */ }
  }

  // 4. 兜底：setText
  if (!pasted) {
    try {
      var et = className("EditText").findOne(1000);
      if (et) { et.setText(replyText); pasted = true; }
    } catch (e2) { /* ignore */ }
  }

  if (!pasted) {
    logger.warn(TAG, "输入失败");
    back(); sleep(500);
    return false;
  }
  sleep(500);

  // 5. 以图找图点击发送按钮（comment_submit 使用 image 策略）
  var sent = false;
  var sendBtn = uiOperator.findElement("comment_submit", 3000);
  if (sendBtn) {
    uiOperator.clickElement(sendBtn);
    sleep(1200);
    sent = true;
    logger.debug(TAG, "回复已发送(图找图): " + replyText.substring(0, 20) + "'");
  }

  // 兜底：回车发送
  if (!sent) {
    logger.info(TAG, "comment_submit 未找到，尝试回车发送");
    try { shell("input keyevent 66", false); } catch (e) { /* ignore */ }
    back();
    sleep(1200);
    sent = true;  // Enter 后假定发送成功（无法验证）
  }

  return sent;
};

/**
 * 关闭输入键盘
 */
/**
 * 安全关闭键盘 — 仅在非评论区页面使用 back
 * 评论区用 back 会关闭评论面板，所以评论面板内不调用此方法
 */
ReplyCommentHandler._dismissKeyboard = function () {
  // 如果在评论面板，不用 back（会退出评论）
  if (uiOperator.findElement("is_comment_view", 300)) {
    return;
  }
  // 在视频详情页/个人主页/私信页，back 安全
  try { back(); sleep(500); } catch (e) { /* ignore */ }
};

/**
 * 进入评论者主页
 * @param {string} nickname - 评论者昵称
 * @returns {boolean}
 */
ReplyCommentHandler._enterCommenterProfile = function (commentAuthorAvatarEl, nickname) {
  // 先判断目标评论者昵称是否可见（昵称可见=头像在同一行可见）
  var nameVisible = false;
  try { nameVisible = !!text(nickname).findOne(500); } catch (e) {}
  if (!nameVisible) {
    logger.info(TAG, "头像不可见，评论列表内轻量下拉拉回");
    var rv = uiOperator.findElement("comment_list", 1000);
    // 在列表中间区域小幅下拉，避开顶部（顶部下拉=关闭评论区）
    if (rv && !rv.isImage && !rv.isCoordinate) {
      try {
        var rvb = rv.bounds();
        var rvcx = rvb.centerX();
        for (var si = 0; si < 4; si++) {
          var sd = Math.floor(Math.random() * 200 + 400);
          gestures([0, sd, [rvcx, rvb.top + rvb.height() * 0.40],
                           [rvcx + Math.floor(Math.random() * 20 + 10), rvb.top + rvb.height() * 0.70]]);
          sleep(400);
          // 昵称出现了就停
          try { if (text(nickname).findOne(300)) break; } catch (e) {}
          if (!uiOperator.findElement("is_comment_view", 300)) break;
        }
      } catch (e) {}
    } else {
      // 兜底：找不到 comment_list，全屏中部小幅下拉
      for (var sj = 0; sj < 2; sj++) {
        var sc = device.width / 2;
        var sd2 = Math.floor(Math.random() * 200 + 400);
        gestures([0, sd2, [sc, device.height * 0.45],
                         [sc + Math.floor(Math.random() * 20 + 10), device.height * 0.70]]);
        sleep(400);
        try { if (text(nickname).findOne(300)) break; } catch (e) {}
        if (!uiOperator.findElement("is_comment_view", 300)) break;
      }
    }
  }

  // 点击头像进入主页
  var avatarClicked = this.safeClick("comment_author_avatar", 2);
  if (avatarClicked) {
    sleep(2000);
    if (uiOperator.isOnPage("is_user_view")) {
      flowContext.enter("profile");
      return true;
    }
    logger.warn(TAG, "点击头像后未检测到主页，回退重试");
  }

  // 降级：找该昵称文本
  try {
    var nameEl = text(nickname).findOne(3000);
    if (nameEl) {
      nameEl.parent().click();
      sleep(2000);
      if (uiOperator.isOnPage("is_user_view")) {
        flowContext.enter("profile");
        return true;
      }
    }
  } catch (e) {
    logger.warn(TAG, "点击昵称失败: " + e.message);
  }
  return false;
};

/**
 * 关注用户 — 拟人化操作，避免被检测
 * 进入主页后：浏览一下 → 随机延迟 → 点关注 → 验证
 */
ReplyCommentHandler._followUser = function () {
  try {
    // 1. 随机停留，给主页加载时间
    sleep(Math.floor(Math.random() * 1000 + 1000));
    // 30% 概率拟人浏览主页（轻滑一下看作品，用 gestures 不会误触发点击）
    if (Math.random() < 0.3) {
      var bwx = device.width * (0.35 + Math.random() * 0.2);
      var bwy1 = device.height * (0.45 + Math.random() * 0.05);
      var bwy2 = device.height * (0.25 + Math.random() * 0.1);
      var bwd = Math.floor(Math.random() * 200 + 300);
      gestures([0, bwd, [bwx, bwy1], [bwx + Math.floor(Math.random() * 20 + 10), bwy2]]);
      sleep(Math.floor(Math.random() * 800 + 600));
    }

    // 2. 确保回到主页顶部（关注/私信按钮在顶部）
    var backToTop = false;
    for (var si = 0; si < 4; si++) {
      if (uiOperator.findElement("user_nickname", 1000)) {
        backToTop = true;
        break;
      }
      var btx = device.width / 2;
      var btd = Math.floor(Math.random() * 200 + 400);
      gestures([0, btd, [btx, device.height * (Math.random() * 0.1 + 0.20)],
                       [btx + Math.floor(Math.random() * 20 + 10), device.height * (Math.random() * 0.1 + 0.75)]]);
      sleep(Math.floor(Math.random() * 200 + 300));
    }
    if (!backToTop) {
      logger.warn(TAG, "下拉回顶未检测到 user_nickname，可能影响关注/私信按钮可见性");
    }
    sleep(Math.floor(Math.random() * 400 + 400));

    // 3. 找关注按钮 — 用随机按压时长模拟真人（80~180ms）
    var followed = false;
    var followBtn = uiOperator.findElement("follow_button", 3000);
    if (followBtn) {
      // 图找图/坐标返回的是虚拟元素，控件返回的是 UiObject，统一取坐标
      var fbx, fby;
      if (followBtn.isImage || followBtn.isCoordinate) {
        fbx = followBtn.x; fby = followBtn.y;
      } else {
        try { var fb = followBtn.bounds(); if (fb) { fbx = fb.centerX(); fby = fb.centerY(); } } catch (e) {}
      }
      if (!fbx) { fbx = device.width / 2; fby = device.height * 0.3; }

      // 随机延迟后点击（真人不会一到主页就秒点关注）
      sleep(Math.floor(Math.random() * 1500 + 500));
      press(fbx, fby, Math.floor(Math.random() * 100 + 80));
      sleep(Math.floor(Math.random() * 1000 + 1000));

      // 验证：图找图检测关注成功
      if (uiOperator.findElement("is_follow", 2000)) {
        followed = true;
      }

      // 可能被风控，换随机时长重试
      if (!followed) {
        sleep(Math.floor(Math.random() * 600 + 400));
        press(fbx, fby, Math.floor(Math.random() * 100 + 80));
        sleep(Math.floor(Math.random() * 1000 + 1000));
        if (uiOperator.findElement("is_follow", 2000)) followed = true;
      }
    }

    if (followed) {
      logger.info(TAG, "关注成功");
    } else {
      logger.warn(TAG, "关注按钮未找到（可能已关注）");
    }
    return followed;
  } catch (e) {
    logger.warn(TAG, "关注流程异常: " + (e.message || e));
    return false;
  }
};

/**
 * 采集用户主页数据 — 抖音号/获赞/粉丝/作品/性别/年龄/IP/是否私密
 * 调用时机：已在个人主页时采集，不 back（调用方负责返回评论区）
 */
ReplyCommentHandler._collectProfileData = function () {
  return commentUtils.collectProfileData({ uploadAvatar: false });
};

/**
 * 发送私信
 * @param {string} content - 私信内容
 */
ReplyCommentHandler._sendDM = function (content) {
  // 1. 进入私信页：点 dm_entry_btn
  var messageClicked = this.safeClick("dm_entry_btn", 3);
  if (!messageClicked) {
    logger.warn(TAG, "私信按钮未找到");
    return false;
  }
  sleep(1500);
  flowContext.enter("dm");

  // 2. 点击 dm_input 触发键盘，输入框自动获得焦点
  if (!this.safeClick("dm_input", 2)) {
    logger.warn(TAG, "dm_input 未找到");
    return false;
  }
  sleep(800);

  // 3. 清空+拟人输入
  var pasted = false;
  try {
    // 用无障碍直接清空输入框（不依赖焦点，不要 shell 键）
    var dmEdit = className("EditText").focused(true).findOne(1000);
    if (dmEdit) {
      dmEdit.setText("");
      sleep(300);
      logger.info(TAG, "DM 输入框已清空");
    } else {
      logger.warn(TAG, "DM 输入框未找到");
    }
    // 拟人：随机敲1字符 → 删除 → 逐块输入AI内容
    var dummyChars = "abcdefghijklmnopqrstuvwxyz";
    var dummy = dummyChars.charAt(Math.floor(Math.random() * dummyChars.length));
    input(dummy);
    sleep(Math.floor(Math.random() * 150 + 100));
    // 用无障碍删除随机字符（比 shell 可靠）
    if (dmEdit) { dmEdit.setText(" "); sleep(200); }
    var pos = 0;
    while (pos < content.length) {
      var chunkSize = Math.random() < 0.4 ? 1 : (Math.floor(Math.random() * 2) + 2);
      chunkSize = Math.min(chunkSize, content.length - pos);
      input(content.substring(pos, pos + chunkSize));
      pos += chunkSize;
      sleep(Math.floor(Math.random() * 150 + 80));
    }
    pasted = true;
    logger.info(TAG, "私信 input 输入成功: '" + content.substring(0, 20) + "'");
  } catch (e) {
    logger.warn(TAG, "私信 input 异常: " + e.message);
  }

  // 4. 兜底：剪贴板粘贴
  if (!pasted) {
    try {
      setClip(content);
      sleep(200);
      shell("input keyevent 279", false);
      sleep(500);
      pasted = true;
    } catch (e) { /* ignore */ }
  }

  if (!pasted) {
    logger.warn(TAG, "私信输入失败");
    back(); sleep(500);
    return false;
  }

  // 5. 等几十毫秒让输入生效，然后点击发送
  sleep(Math.floor(Math.random() * 150 + 100));
  var sent = uiOperator.findElement("dm_send", 3000);
  if (sent) {
    uiOperator.clickElement(sent);
    sleep(800);
  } else {
    logger.warn(TAG, "私信发送按钮未找到，取消发送");
    return false;
  }

  logger.info(TAG, "私信已发送: '" + content.substring(0, 20) + "'");
  return true;
};

ReplyCommentHandler._returnToComments = function () {
  var maxBacks = 5;
  for (var i = 0; i < maxBacks; i++) {
    // 已在评论面板 → 完成
    if (uiOperator.isOnPage("is_comment_view")) {
      logger.info(TAG, "回到评论区 (back " + i + " 次)");
      flowContext.enter("comment");
      return;
    }

    // 在个人主页 → back
    if (uiOperator.isOnPage("is_user_view")) {
      logger.info(TAG, "在个人主页，back 到评论区");
      back(); sleep(800);
      continue;
    }

    // 在私信页 → back
    if (uiOperator.isOnPage("is_dm_view")) {
      logger.info(TAG, "在私信页，back 到个人主页");
      back(); sleep(800);
      continue;
    }

    // 已确认是视频详情页 → 判断上下文
    if (uiOperator.isOnPage("is_video_view")) {
      if (flowContext.is("profile")) {
        // 从个人主页误触进来的 → back
        logger.info(TAG, "检测到误触（profile→video），back");
        back(); sleep(500);
        flowContext.enter("profile");
        continue;
      }
      // 搜索流中的视频 → 打开评论区
      logger.info(TAG, "在视频页，打开评论区 (back " + i + " 次)");
      this._openComments();
      return;
    }

    // 未知页面，back 重试
    logger.info(TAG, "第 " + (i + 1) + " 次 back，未知页面");
    back();
    sleep(1000);
  }

  logger.warn(TAG, "无法回到评论区，兜底打开");
  this._openComments();
};

module.exports = ReplyCommentHandler;
```
