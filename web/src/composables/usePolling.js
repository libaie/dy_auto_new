import { onMounted, onUnmounted } from 'vue'

/**
 * @param {Function} fetchFn — async function to call on each tick
 * @param {number} [interval=10000] — polling interval in ms
 */
export function usePolling(fetchFn, interval = 10000) {
  let timer = null

  function start() {
    stop()
    timer = setInterval(fetchFn, interval)
  }

  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  function handleVisibilityChange() {
    if (document.hidden) {
      stop()
    } else {
      fetchFn()
      start()
    }
  }

  onMounted(() => {
    fetchFn()
    start()
    document.addEventListener('visibilitychange', handleVisibilityChange)
  })

  onUnmounted(() => {
    stop()
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  })

  return { start, stop }
}
