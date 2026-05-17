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