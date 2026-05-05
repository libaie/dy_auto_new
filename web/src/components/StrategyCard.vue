<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  strategy: { type: Object, required: true },
  index: { type: Number, required: true },
  totalCount: { type: Number, required: true },
  actionName: { type: String, default: '' },
})

const emit = defineEmits(['update', 'delete', 'move-up', 'move-down'])

const STRATEGY_TYPES = [
  { value: 'text', label: '文本', placeholder: '例如：赞', fields: 'value' },
  { value: 'id', label: '资源 ID', placeholder: 'com.ss.android.ugc.aweme:id/like_btn', fields: 'value', mono: true },
  { value: 'desc', label: '描述', placeholder: '元素描述文字', fields: 'value' },
  { value: 'className', label: '类名', placeholder: 'android.widget.TextView', fields: 'value', mono: true },
  { value: 'package', label: '包名', placeholder: 'com.ss.android.ugc.aweme', fields: 'value', mono: true },
  { value: 'coordinate', label: '坐标', fields: 'xy' },
  { value: 'image', label: '图片匹配', fields: 'image' },
]

const showAdvanced = ref(false)

const typeConfig = computed(() =>
  STRATEGY_TYPES.find(t => t.value === props.strategy.type) || STRATEGY_TYPES[0]
)

function updateField(key, value) {
  emit('update', { ...props.strategy, [key]: value })
}

function onTypeChange(newType) {
  const base = { type: newType }
  if (newType === 'coordinate') {
    base.x_percent = props.strategy.x_percent || 50
    base.y_percent = props.strategy.y_percent || 50
  } else if (newType === 'image') {
    base.template = props.strategy.template || ''
    base.threshold = props.strategy.threshold || 0.8
  } else {
    base.value = props.strategy.value || ''
  }
  emit('update', base)
}

async function onImageFileSelect(e) {
  const file = e.target.files?.[0]
  if (!file) return
  const { uploadTemplate } = await import('../api/selectors.js')
  try {
    const res = await uploadTemplate(file, props.actionName || 'template')
    updateField('template', res.data.filename)
  } catch (err) {
    alert('上传失败: ' + (err.response?.data?.detail || err.message))
  }
  e.target.value = ''
}
</script>

<template>
  <div class="glass-card p-4 border border-white/10 hover:border-white/20 transition-colors">
    <!-- Header: handle + number + type + delete -->
    <div class="flex items-center gap-3 mb-3">
      <!-- Reorder arrows -->
      <div class="flex flex-col gap-0.5">
        <button
          type="button"
          :disabled="index === 0"
          class="text-slate-500 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
          @click="$emit('move-up')"
          title="上移（提高优先级）"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" /></svg>
        </button>
        <button
          type="button"
          :disabled="index === totalCount - 1"
          class="text-slate-500 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
          @click="$emit('move-down')"
          title="下移（降低优先级）"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
        </button>
      </div>

      <!-- Priority number -->
      <span class="text-xs font-mono text-slate-500 w-6 text-center">#{{ index + 1 }}</span>

      <!-- Type selector -->
      <select
        :value="strategy.type"
        @change="onTypeChange($event.target.value)"
        class="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200 focus:border-purple-500/50 focus:outline-none"
      >
        <option v-for="t in STRATEGY_TYPES" :key="t.value" :value="t.value">
          {{ t.label }}
        </option>
      </select>

      <!-- Spacer -->
      <div class="flex-1"></div>

      <!-- Delete -->
      <button
        type="button"
        class="text-slate-500 hover:text-red-400 transition-colors"
        @click="$emit('delete')"
        title="删除此策略"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
      </button>
    </div>

    <!-- Fields based on type -->
    <div class="space-y-2">
      <!-- text / id / desc / className / package: single value input -->
      <div v-if="typeConfig.fields === 'value'">
        <label class="text-xs text-slate-400 mb-1 block">查找值</label>
        <input
          :value="strategy.value"
          @input="updateField('value', $event.target.value)"
          :placeholder="typeConfig.placeholder"
          :class="[
            'w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none',
            typeConfig.mono && 'font-mono',
          ]"
        />
      </div>

      <!-- coordinate: x + y inputs -->
      <div v-else-if="typeConfig.fields === 'xy'" class="flex gap-3">
        <div class="flex-1">
          <label class="text-xs text-slate-400 mb-1 block">X 百分比 (0-100)</label>
          <input
            type="number"
            min="0"
            max="100"
            :value="strategy.x_percent"
            @input="updateField('x_percent', Number($event.target.value))"
            placeholder="50"
            class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none"
          />
        </div>
        <div class="flex-1">
          <label class="text-xs text-slate-400 mb-1 block">Y 百分比 (0-100)</label>
          <input
            type="number"
            min="0"
            max="100"
            :value="strategy.y_percent"
            @input="updateField('y_percent', Number($event.target.value))"
            placeholder="50"
            class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none"
          />
        </div>
      </div>

      <!-- image: template + threshold -->
      <div v-else-if="typeConfig.fields === 'image'" class="space-y-2">
        <div>
          <label class="text-xs text-slate-400 mb-1 block">模板图片</label>
          <div class="flex gap-2">
            <input
              :value="strategy.template"
              @input="updateField('template', $event.target.value)"
              placeholder="文件名，例如 like_btn.png"
              class="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 font-mono focus:border-purple-500/50 focus:outline-none"
            />
            <label class="btn-aurora rounded-lg px-3 py-2 text-sm font-medium cursor-pointer whitespace-nowrap">
              <span class="relative z-10">选择文件</span>
              <input
                type="file"
                accept=".png,.jpg,.jpeg"
                class="hidden"
                @change="onImageFileSelect"
              />
            </label>
          </div>
        </div>
        <div>
          <label class="text-xs text-slate-400 mb-1 block">
            匹配阈值: {{ (strategy.threshold || 0.8).toFixed(2) }}
          </label>
          <input
            type="range"
            min="0.5"
            max="1"
            step="0.05"
            :value="strategy.threshold || 0.8"
            @input="updateField('threshold', Number($event.target.value))"
            class="w-full accent-purple-500"
          />
          <div class="flex justify-between text-xs text-slate-600">
            <span>0.5（宽松）</span>
            <span>1.0（精确）</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Advanced: x/y offset (for non-coordinate types) -->
    <div v-if="typeConfig.fields !== 'xy'" class="mt-2">
      <button
        type="button"
        class="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1"
        @click="showAdvanced = !showAdvanced"
      >
        <svg
          class="w-3 h-3 transition-transform"
          :class="{ 'rotate-90': showAdvanced }"
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        ><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
        高级选项（可选偏移）
      </button>
      <div v-if="showAdvanced" class="mt-2 flex gap-3">
        <div class="flex-1">
          <label class="text-xs text-slate-400 mb-1 block">X 偏移 %</label>
          <input
            type="number"
            min="0"
            max="100"
            :value="strategy.x_percent"
            @input="updateField('x_percent', $event.target.value ? Number($event.target.value) : undefined)"
            placeholder="留空不偏移"
            class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none"
          />
        </div>
        <div class="flex-1">
          <label class="text-xs text-slate-400 mb-1 block">Y 偏移 %</label>
          <input
            type="number"
            min="0"
            max="100"
            :value="strategy.y_percent"
            @input="updateField('y_percent', $event.target.value ? Number($event.target.value) : undefined)"
            placeholder="留空不偏移"
            class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none"
          />
        </div>
      </div>
    </div>
  </div>
</template>
