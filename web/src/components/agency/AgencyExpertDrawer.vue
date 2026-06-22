<!-- 专家团队业务组件：展示或操作专家团队、审查、返修和创意补丁相关业务状态。 -->
<template>
  <aside
    v-if="expertId"
    ref="drawerRef"
    role="dialog"
    aria-modal="true"
    aria-labelledby="agency-expert-drawer-title"
    tabindex="-1"
    class="fixed inset-y-0 right-0 z-30 w-full max-w-xl overflow-y-auto border-l border-white/10 bg-zinc-950 p-5 text-zinc-100 shadow-2xl"
  >
    <div class="mb-5 flex items-start justify-between gap-4">
      <div>
        <div class="text-xs font-medium text-cyan-200">专家档案</div>
        <h2 id="agency-expert-drawer-title" class="mt-1 text-xl font-semibold text-white">
          {{ expertName(expertId, expert?.name) }}
        </h2>
        <div
          v-if="expert?.legacy"
          class="mt-2 inline-flex rounded border border-violet-300/30 bg-violet-400/10 px-2 py-1 text-xs text-violet-100"
        >
          历史审计角色
        </div>
      </div>
      <button class="rounded border border-white/10 px-3 py-2 text-sm text-cyan-200 hover:border-cyan-400/60 hover:text-cyan-100" @click="$emit('close')">关闭</button>
    </div>

    <div v-if="loading" class="rounded-md border border-white/10 bg-zinc-900 p-4 text-sm text-zinc-400">正在加载专家档案...</div>
    <div v-else-if="error" class="rounded-md border border-rose-500/40 bg-rose-950/40 p-4 text-sm text-rose-100">{{ error }}</div>
    <article v-else-if="expert">
      <dl class="grid gap-2 text-xs text-zinc-400">
        <div class="rounded-md border border-white/10 bg-zinc-900/80 p-3">
          <dt class="text-zinc-300">源文件</dt>
          <dd class="mt-1 break-all">{{ metadataText(expert.source_path, '已记录源文件') }}</dd>
        </div>
        <div class="rounded-md border border-white/10 bg-zinc-900/80 p-3">
          <dt class="text-zinc-300">源提交</dt>
          <dd class="mt-1 break-all">{{ metadataText(expert.source_commit, '已记录源提交') }}</dd>
        </div>
        <div class="rounded-md border border-white/10 bg-zinc-900/80 p-3">
          <dt class="text-zinc-300">内容哈希</dt>
          <dd class="mt-1 break-all">{{ metadataText(expert.sha256 || expert.source_sha256, '已记录校验信息') }}</dd>
        </div>
      </dl>
      <pre class="mt-4 max-h-[70vh] overflow-auto whitespace-pre-wrap rounded-md border border-white/10 bg-zinc-900 p-4 text-xs leading-5 text-zinc-200">{{ expert.markdown || '暂无专家正文。' }}</pre>
    </article>
  </aside>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { getAgencyExpert } from '../../api/agency.js'
import { expertName as knownExpertName } from './agencyExpertLabels.js'

const props = defineProps({
  expertId: { type: String, default: '' },
})

const emit = defineEmits(['close'])

const expert = ref(null)
const loading = ref(false)
const error = ref('')
const drawerRef = ref(null)
let escapeListenerActive = false
let requestSequence = 0

watch(() => props.expertId, async (id) => {
  const requestId = ++requestSequence
  const requestedId = id
  expert.value = null
  error.value = ''
  if (!id) {
    loading.value = false
    removeEscapeListener()
    return
  }

  addEscapeListener()
  await nextTick()
  drawerRef.value?.focus()

  loading.value = true
  try {
    const response = await getAgencyExpert(id)
    if (isCurrentRequest(requestId, requestedId)) {
      expert.value = response.data
    }
  } catch (err) {
    if (isCurrentRequest(requestId, requestedId)) {
      console.error('Agency expert load failed', err)
      error.value = '专家档案加载失败，请稍后重试。'
    }
  } finally {
    if (isCurrentRequest(requestId, requestedId)) {
      loading.value = false
    }
  }
}, { immediate: true })

onBeforeUnmount(() => {
  removeEscapeListener()
})

// 前端业务函数：协调 addEscapeListener 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 addEscapeListener 对应业务流程的处理结果。
function addEscapeListener() {
  if (escapeListenerActive || typeof document === 'undefined') return
  document.addEventListener('keydown', handleEscapeKeydown)
  escapeListenerActive = true
}

// 前端业务函数：协调 removeEscapeListener 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 removeEscapeListener 对应业务流程的处理结果。
function removeEscapeListener() {
  if (!escapeListenerActive || typeof document === 'undefined') return
  document.removeEventListener('keydown', handleEscapeKeydown)
  escapeListenerActive = false
}

// 前端业务函数：协调 handleEscapeKeydown 对应的页面流程、接口调用或状态转换。
// 入参：event 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 handleEscapeKeydown 对应业务流程的处理结果。
function handleEscapeKeydown(event) {
  if (event.key === 'Escape' && props.expertId) {
    emit('close')
  }
}

// 前端业务函数：协调 isCurrentRequest 对应的页面流程、接口调用或状态转换。
// 入参：requestId、requestedId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 isCurrentRequest 对应业务流程的处理结果。
function isCurrentRequest(requestId, requestedId) {
  return requestId === requestSequence && props.expertId === requestedId
}

// 前端业务函数：协调 expertName 对应的页面流程、接口调用或状态转换。
// 入参：id、fallback 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 expertName 对应业务流程的处理结果。
function expertName(id, fallback = '') {
  return knownExpertName(id, fallback)
}

// 前端业务函数：协调 metadataText 对应的页面流程、接口调用或状态转换。
// 入参：value、fallback 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 metadataText 对应业务流程的处理结果。
function metadataText(value, fallback) {
  return value ? fallback : '-'
}
</script>
