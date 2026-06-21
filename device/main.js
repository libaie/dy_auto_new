// 设备端主入口，负责拉取任务、调度处理器并把执行结果回传后端。
var config = require("./config");
var apiClient = require("./core/api-client");
var selectorLoader = require("./core/selector-loader");
var promptTemplateLoader = require("./core/prompt-template-loader");
var taskExecutor = require("./core/task-executor");
var taskTimeout = require("./core/task-timeout");
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
  var _needsRestart = false;  // watchdog 触发后拒绝新任务，防止双任务并发操作 UI
  var _knownTaskIds = {};       // taskId→true: 当前运行中+已入队的 task id，防重复派发
  var _recentlyFinished = [];   // 最近完成的 task id (最多 20 个)，防网络重放
  var MAX_RECENT = 20;
  _mainLoopRuntime.isIdle = function () { return !_taskBusy && _taskQueue.length === 0 && !_needsRestart; };
  _mainLoopRuntime.catchUpPoll = function () { catchUpPoll(); };

  function _isDuplicateTask(taskId) {
    if (_knownTaskIds[taskId]) return true;
    for (var i = 0; i < _recentlyFinished.length; i++) {
      if (_recentlyFinished[i] === taskId) return true;
    }
    return false;
  }

  function handleTask(task) {
    if (!task || !task.id) return;
    if (_isDuplicateTask(task.id)) {
      logger.info(TAG, "忽略重复任务: " + task.id + " (已在队列/执行中/近期完成)");
      return;
    }
    _knownTaskIds[task.id] = true;
    _taskQueue.push(task);
    processTaskQueue();
  }

  function processTaskQueue() {
    if (_needsRestart || _taskBusy || _taskQueue.length === 0) return;
    _taskBusy = true;
    _idleTicks = 0;
    var task = _taskQueue.shift();

    // Watchdog: 10min 超时 → 取消任务，进入维护状态
    // 不释放 busy 锁 → 旧线程最终退出后 finally 块释放 → 防止双任务并发操作 UI
    var TASK_TIMEOUT_MS = taskTimeout.getTaskTimeoutMs(task);
    var _completed = false;
    var _watchdog = setTimeout(function () {
      if (!_completed) {
        logger.error(TAG, "任务超时 (" + (TASK_TIMEOUT_MS / 60000) + "min): " + task.id + "，取消任务，设备进入维护状态");
        taskExecutor.cancel(task.id);
        _needsRestart = true;
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

        var reportResult = apiClient.report(task.id, result.status, result.result, uiSnapshot, task.lease_id);
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
        // 去重维护: 无论何种退出路径，从活跃集移除并加入最近完成集
        delete _knownTaskIds[task.id];
        _recentlyFinished.push(task.id);
        if (_recentlyFinished.length > MAX_RECENT) _recentlyFinished.shift();
        if (!_completed) {
          _completed = true;
          _taskBusy = false;
          if (!_needsRestart) {
            processTaskQueue();
            if (_taskQueue.length === 0 && !_taskBusy) {
              catchUpPoll();
            }
          } else {
            logger.error(TAG, "任务 " + task.id + " 被 watchdog 强杀后线程退出，设备状态不可靠，拒绝新任务，建议重启设备");
          }
        }
      }
    });
  }

  function applyDMSequences(dmSequences) {
    SearchBaseHandler.applyDMSequences(dmSequences || []);
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
    return SearchBaseHandler.syncDMSequences();
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
      _handleCancelledTask(taskId);
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
   * 处理服务端取消投递 — 区分"正在运行"和"已不在运行"两种情况。
   * 正在运行时 handler 会在 isCancelled() 检测后 report CANCELLED；
   * 已不在运行时（设备重启/任务已结束）需立即 ack，否则
   * check_cancelled_running 会持续投递，设备卡在取消循环拿不到新任务。
   */
  function _handleCancelledTask(taskId) {
    logger.info(TAG, "收到服务端取消任务: " + taskId);
    var currentTaskId = taskExecutor.getCurrentTaskId();
    if (currentTaskId === taskId) {
      // Task is running — flag it; handler will exit via isCancelled() and report
      taskExecutor.cancel(taskId);
    } else {
      // Task not running — ack immediately so server clears device_id
      logger.info(TAG, "任务未在运行，直接确认取消: " + taskId);
      try {
        apiClient.report(taskId, "cancelled", { error: "Ack server cancel (task not running)" });
      } catch (e) {
        logger.warn(TAG, "确认取消上报失败: " + e.message);
      }
    }
  }

  /**
   * catch-up poll — 捕获离线期间积累的任务
   */
  function catchUpPoll() {
    try {
      var response = apiClient.poll();
      if (!response) return;

      applyPollSideData(response);

      if (response.cancelled_task_id) {
        _handleCancelledTask(response.cancelled_task_id);
      }

      if (response.task) {
        logger.info(TAG, "catch-up: 发现待执行任务: " + response.task.id);
        if (response.task.params && response.task.params.dm_sequence_id) {
          syncDMSequences();
        }
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
