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

  // 设备业务函数：处理 is 对应的抖音自动化动作、状态或安全边界。
  is: function (state) {
    return this._current === state;
  },

  // 设备业务函数：处理 reset 对应的抖音自动化动作、状态或安全边界。
  reset: function () {
    this._current = "idle";
  },
};

module.exports = flowContext;
