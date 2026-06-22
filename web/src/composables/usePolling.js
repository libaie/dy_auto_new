// 前端组合式业务状态：封装 usePolling 相关轮询、弹窗、分页或连接状态。
import { onMounted, onUnmounted } from 'vue'

/**
 * @param {Function} fetchFn — async function to call on each tick
 * @param {number} [interval=10000] — polling interval in ms
 */
// 前端业务函数：协调 usePolling 对应的页面流程、接口调用或状态转换。
// 入参：fetchFn、interval 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 usePolling 对应业务流程的处理结果。
export function usePolling(fetchFn, interval = 10000) {
  let timer = null

  // 前端业务函数：协调 start 对应的页面流程、接口调用或状态转换。
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 start 对应业务流程的处理结果。
  function start() {
    stop()
    timer = setInterval(fetchFn, interval)
  }

  // 前端业务函数：协调 stop 对应的页面流程、接口调用或状态转换。
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 stop 对应业务流程的处理结果。
  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  // 前端业务函数：协调 handleVisibilityChange 对应的页面流程、接口调用或状态转换。
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 handleVisibilityChange 对应业务流程的处理结果。
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
