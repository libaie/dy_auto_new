// Shared cancellation state must not depend on the executor or its handlers.
var cancelled = false;

module.exports = {
  reset: function () { cancelled = false; },
  cancel: function () { cancelled = true; },
  isCancelled: function () { return cancelled; },
};
