// 前端组合式业务状态：封装 useSavedPrompt 相关轮询、弹窗、分页或连接状态。
import { ref, watch } from 'vue'

const STORE_PREFIX = 'ai_prompt_'

/**
 * 持久化的 AI 提示词 ref — 自动同步到 localStorage
 * @param {string} key - 唯一标识，如 'template_generator', 'selector_regex'
 * @param {string} defaultValue - 默认值
 * @returns {import('vue').Ref<string>}
 */
// 入参：key、defaultValue 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 useSavedPrompt 对应业务流程的处理结果。
export function useSavedPrompt(key, defaultValue) {
  const storageKey = STORE_PREFIX + key
  let saved = defaultValue
  try {
    const raw = localStorage.getItem(storageKey)
    if (raw != null) saved = raw
  } catch (e) { /* ignore */ }

  const val = ref(saved)

  watch(val, (v) => {
    try { localStorage.setItem(storageKey, v || '') } catch (e) { /* ignore */ }
  }, { flush: 'sync' })

  return val
}
