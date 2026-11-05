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
  _generation: 0,
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
    this._generation++;
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
    var generation = ++this._generation;
    var serverUrl = config.serverUrl;
    var deviceSecret = config.deviceSecret;
    var deviceId = config.deviceId;
    function isCurrentConnection() {
      return !self._stopped && self._generation === generation &&
        config.serverUrl === serverUrl && config.deviceSecret === deviceSecret;
    }
    // Secret NOT in URL — sent as first auth message after connect
    var wsUrl = serverUrl.replace("http://", "ws://") + "/api/device/ws/status";

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
          if (!isCurrentConnection()) {
            try { ws.close(1000, "retired"); } catch (e) {}
            return;
          }
          logger.info(TAG, "已连接，发送认证消息");
          self._ws = ws;
          self._connected = true;
          self._reconnectDelay = 3000;

          // Send auth as first message (not in URL)
          var authMsg = JSON.stringify({
            type: "auth",
            device_id: deviceId,
            secret: deviceSecret,
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
          if (!isCurrentConnection()) return;
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
          if (!isCurrentConnection()) return;
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
          if (!isCurrentConnection()) return;
          var msg = t.getMessage() || "";
          var code = response ? response.code() : 0;
          logger.warn(TAG, "连接失败: code=" + code + " err=" + msg);
          self._cleanup();
          self._scheduleReconnect();
        },
      });

      client.newWebSocket(request, listener);
    } catch (e) {
      if (!isCurrentConnection()) return;
      logger.error(TAG, "创建 WS 失败: " + e.message);
      this._scheduleReconnect();
    }
  },

  _startPing: function () {
    var self = this;
    var generation = this._generation;
    if (this._pingTimer) clearInterval(this._pingTimer);
    this._pingTimer = setInterval(function () {
      if (self._stopped || self._generation !== generation) return;
      if (self._ws) {
        try {
          self._ws.send("ping");
        } catch (e) {
          if (self._generation !== generation) return;
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
    var generation = this._generation;
    if (this._stopped) return;
    if (this._reconnectTimer) return;
    logger.info(TAG, this._reconnectDelay / 1000 + " 秒后重连...");
    this._reconnectTimer = setTimeout(function () {
      if (self._stopped || self._generation !== generation) return;
      self._reconnectTimer = null;
      self._connect();
    }, this._reconnectDelay);
    this._reconnectDelay = Math.min(this._reconnectDelay * 1.5, 60000);
  },
};

module.exports = deviceWs;
