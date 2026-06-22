// device/core/flow-context.js
// 流程上下文状态机 — 纯运行时，结果驱动
// 与 pageDetector(isOnPage/detectPage) 配合使用：
//   第一层 pageDetector → "我现在看到的是什么页面？"
//   第二层 flowContext → "我是在什么业务环节来到这个页面的？"

var flowContext = {
  _current: "idle",

  // 入参：state 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 enter 对应业务流程的处理结果。
  enter: function (state) {
    this._current = state;
  },

  // 设备业务函数：处理 is 对应的抖音自动化动作、状态或安全边界。
  // 入参：state 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 is 对应业务流程的处理结果。
  is: function (state) {
    return this._current === state;
  },

  // 设备业务函数：处理 reset 对应的抖音自动化动作、状态或安全边界。
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 reset 对应业务流程的处理结果。
  reset: function () {
    this._current = "idle";
  },
};

module.exports = flowContext;
