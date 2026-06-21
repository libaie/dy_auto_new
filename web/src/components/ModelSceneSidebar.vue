<!-- 管理端通用组件：提供业务页面复用的展示、反馈或交互能力。 -->
<template>
  <nav class="scene-sidebar" aria-label="AI 模型场景">
    <div class="scene-summary">
      视频生产链路就绪: {{ readyCount }}/{{ scenes.length }}
    </div>
    <button
      v-for="scene in scenes"
      :key="scene.key"
      @click="$emit('select-scene', scene)"
      :aria-current="activeScene === scene.key ? 'true' : undefined"
      class="scene-item"
      :class="{ 'scene-item--active': activeScene === scene.key }"
    >
      <span class="scene-status-dot" :class="'status--' + statusClass(scene.key)" :aria-label="statusLabel(scene.key)"></span>
      <span class="scene-label">{{ scene.label }}</span>
      <span class="scene-count">{{ modelCount(scene.key) }}</span>
    </button>
  </nav>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  scenes: { type: Array, required: true },
  activeScene: { type: String, default: null },
  models: { type: Array, default: () => [] },
  sceneStatus: { type: Object, default: () => ({}) },
})

defineEmits(['select-scene'])

function modelCount(key) {
  const scene = props.scenes.find(s => s.key === key)
  if (!scene) return 0
  return props.models.filter(m => m.model_type === scene.model_type).length
}

function statusClass(key) {
  return props.sceneStatus[key] || 'red'
}

function statusLabel(key) {
  const map = { green: '就绪', amber: '待配置', red: '未配置' }
  return map[props.sceneStatus[key]] || '未知'
}

const readyCount = computed(() =>
  Object.values(props.sceneStatus).filter(s => s === 'green').length
)
</script>

<style scoped>
.scene-sidebar {
  width: 240px;
  flex-shrink: 0;
  border-right: 1px solid var(--border-color, #2a3040);
  padding: 12px 0;
  overflow-y: auto;
}

.scene-summary {
  padding: 8px 16px 12px;
  font-size: 13px;
  color: var(--text-secondary, #94a3b8);
  border-bottom: 1px solid var(--border-color, #2a3040);
  margin-bottom: 8px;
}

.scene-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 16px;
  border: none;
  background: transparent;
  color: var(--text-primary, #e2e8f0);
  font-size: 14px;
  cursor: pointer;
  text-align: left;
  transition: background-color 150ms ease;
}

.scene-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.scene-item--active {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}

.scene-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status--green { background: #22c55e; }
.status--amber { background: #eab308; }
.status--red { background: #ef4444; }

.scene-label {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.scene-count {
  font-size: 12px;
  color: var(--text-secondary, #94a3b8);
  background: rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 1px 8px;
  min-width: 20px;
  text-align: center;
}
</style>
