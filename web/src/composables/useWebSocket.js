// 前端组合式业务状态：封装 useWebSocket 相关轮询、弹窗、分页或连接状态。
import { ref, onUnmounted } from 'vue'

/**
 * @param {string|Function} urlOrFn — WebSocket URL or function that returns one
 * @param {Object} options
 * @param {Function} [options.onMessage] — called with parsed JSON message
 * @param {number} [options.reconnectDelay=5000]
 */
export function useWebSocket(urlOrFn, { onMessage, reconnectDelay = 5000 } = {}) {
  const connected = ref(false)
  let ws = null
  let timer = null

  function connect() {
    const url = typeof urlOrFn === 'function' ? urlOrFn() : urlOrFn
    if (!url) return

    cleanup()

    ws = new WebSocket(url)
    ws.onopen = () => { connected.value = true }
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        onMessage?.(msg)
      } catch { /* ignore malformed messages */ }
    }
    ws.onclose = () => {
      connected.value = false
      ws = null
      timer = setTimeout(connect, reconnectDelay)
    }
    ws.onerror = () => {
      ws?.close()
    }
  }

  function send(data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }

  function disconnect() {
    cleanup()
    connected.value = false
  }

  function cleanup() {
    if (timer) { clearTimeout(timer); timer = null }
    if (ws) { ws.onclose = null; ws.close(); ws = null }
  }

  onUnmounted(cleanup)

  return { connected, connect, send, disconnect }
}
