<!-- 专家团队业务组件：展示或操作专家团队、审查、返修和创意补丁相关业务状态。 -->
<template>
  <section class="rounded-lg border border-white/10 bg-zinc-900/80 p-3">
    <div class="mb-3 flex items-center justify-between gap-3">
      <h2 class="text-sm font-semibold text-white">补丁队列</h2>
      <span class="text-xs text-zinc-500">{{ patches.length }} 项</span>
    </div>
    <div v-if="!patches.length" class="rounded border border-white/10 bg-zinc-950/60 p-4 text-sm text-zinc-400">
      暂无创作补丁。
    </div>
    <div v-else class="space-y-2">
      <button
        v-for="patch in patches"
        :key="patch.id"
        type="button"
        class="w-full rounded-md border p-3 text-left transition focus:outline-none focus:ring-2 focus:ring-cyan-300"
        :class="patch.id === selectedId ? 'border-cyan-300/60 bg-cyan-400/10' : 'border-white/10 bg-zinc-950/70 hover:border-white/20'"
        @click="$emit('select', patch)"
      >
        <div class="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div class="text-sm font-medium text-zinc-100">{{ patch.title || '未命名补丁' }}</div>
            <div class="mt-1 text-xs text-zinc-500">{{ stageLabel(patch.stage) }} · {{ patch.target_id || '未指定目标' }}</div>
          </div>
          <span class="rounded border border-white/10 px-2 py-0.5 text-[11px] text-zinc-300">{{ statusLabel(patch.status) }}</span>
        </div>
      </button>
    </div>
  </section>
</template>

<script setup>
defineProps({
  patches: { type: Array, default: () => [] },
  selectedId: { type: String, default: '' },
})

defineEmits(['select'])

// 前端业务函数：协调 statusLabel 对应的页面流程、接口调用或状态转换。
// 入参：status 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 statusLabel 对应业务流程的处理结果。
function statusLabel(status) {
  const labels = {
    proposed: '待处理',
    edited: '已编辑',
    approved: '已批准',
    applied: '已应用',
    rejected: '已拒绝',
  }
  return labels[status] || status || '未知'
}

// 入参：stage 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 stageLabel 对应业务流程的处理结果。
function stageLabel(stage) {
  const labels = {
    style_lock: '风格锁定',
    storyboard: '分镜脚本',
    image_stage: '图像生成',
    image_review: '图像审查',
    video_stage: '视频生成',
    video_review: '视频审查',
    compose_preflight: '合成预检',
    compose: '合成交付',
  }
  return labels[stage] || stage || '未知阶段'
}
</script>
