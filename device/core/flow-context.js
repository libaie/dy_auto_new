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
