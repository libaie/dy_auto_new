// Shared cancellation state must not depend on the executor or its handlers.
// A token belongs to one execution attempt. Keeping it by reference also
// preserves cancellation received after dequeue but before execute() starts.
var current = { cancelled: false };

module.exports = {
  reset: function (token) { current = token || { cancelled: false }; return current; },
  cancel: function () { current.cancelled = true; },
  isCancelled: function () { return current.cancelled === true; },
};
