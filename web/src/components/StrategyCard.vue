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
  { value: 'chain', label: '链式查找', fields: 'chain' },
]

const CONDITION_TYPES = [
  { value: 'text', label: '文本', placeholder: '例如：评论' },
  { value: 'id', label: '资源 ID', placeholder: 'com.ss.android.ugc.aweme:id/title' },
  { value: 'desc', label: '描述', placeholder: '例如：按钮' },
  { value: 'className', label: '类名', placeholder: 'android.widget.TextView' },
]

const showAdvanced = ref(false)

const isMultiCondition = computed(() =>
  !!(props.strategy.conditions && props.strategy.conditions.length > 0)
)

const typeConfig = computed(() =>
  STRATEGY_TYPES.find(t => t.value === props.strategy.type) || STRATEGY_TYPES[0]
)

const canHaveMatchMode = computed(() =>
  ['text', 'id', 'desc', 'className'].includes(props.strategy.type) && !isMultiCondition.value
)

function updateField(key, value) {
  emit('update', { ...props.strategy, [key]: value })
}

function onTypeChange(newType) {
  const base = { type: newType }
  if (newType === 'coordinate') {
    base.x_percent = props.strategy.x_percent || 50
    base.y_percent = props.strategy.y_percent || 50
  } else if (newType === 'chain') {
    base.steps = props.strategy.steps || [{ type: 'text', value: '' }]
  } else if (newType === 'image') {
    base.template = props.strategy.template || ''
    base.threshold = props.strategy.threshold || 0.8
  } else {
    base.value = props.strategy.value || ''
  }
  emit('update', base)
}

// --- Multi-condition helpers ---

function toggleConditionMode() {
  if (isMultiCondition.value) {
    const first = props.strategy.conditions[0]
    const { conditions, logic, ...rest } = props.strategy
    rest.type = first.type || 'text'
    rest.value = first.value || ''
    rest.match_mode = first.match_mode || 'exact'
    emit('update', rest)
  } else {
    const firstCond = {
      type: props.strategy.type || 'text',
      value: props.strategy.value || '',
      match_mode: props.strategy.match_mode || 'exact',
    }
    const { match_mode, value, type, ...rest } = props.strategy
    rest.conditions = [firstCond]
    rest.logic = 'and'
    emit('update', rest)
  }
}

function setLogic(val) {
  emit('update', { ...props.strategy, logic: val })
}

function addCondition() {
  const conds = [...(props.strategy.conditions || []), { type: 'text', value: '', match_mode: 'exact' }]
  emit('update', { ...props.strategy, conditions: conds })
}

function removeCondition(index) {
  const conds = props.strategy.conditions.filter((_, i) => i !== index)
  if (conds.length === 0) {
    toggleConditionMode()
    return
  }
  emit('update', { ...props.strategy, conditions: conds })
}

function updateCondition(index, key, value) {
  const conds = props.strategy.conditions.map((c, i) =>
    i === index ? { ...c, [key]: value } : c
  )
  emit('update', { ...props.strategy, conditions: conds })
}

function onCondTypeChange(index, newType) {
  const conds = props.strategy.conditions.map((c, i) =>
    i === index ? { type: newType, value: '', match_mode: 'exact' } : c
  )
  emit('update', { ...props.strategy, conditions: conds })
}

function addStep() {
  const steps = [...(props.strategy.steps || []), { type: 'text', value: '' }]
  emit('update', { ...props.strategy, steps })
}
function addNavStep(nav) {
  const step = nav === 'parent' ? { nav: 'parent' } : { nav, type: 'text', value: '' }
  const steps = [...(props.strategy.steps || []), step]
  emit('update', { ...props.strategy, steps })
}
function removeStep(index) {
  const steps = props.strategy.steps.filter((_, i) => i !== index)
  emit('update', { ...props.strategy, steps })
}
function updateStep(index, key, value) {
  const steps = props.strategy.steps.map((s, i) =>
    i === index ? { ...s, [key]: value } : s
  )
  emit('update', { ...props.strategy, steps })
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

      <!-- Type selector (hidden in multi-condition mode) -->
      <select
        v-if="!isMultiCondition"
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
      <div v-if="typeConfig.fields === 'value' && !isMultiCondition">
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

      <!-- match_mode dropdown (single-condition text/id/desc/className only) -->
      <div v-if="canHaveMatchMode" class="mt-2">
        <label class="text-xs text-slate-400 mb-1 block">匹配模式</label>
        <select
          :value="strategy.match_mode || 'exact'"
          @change="updateField('match_mode', $event.target.value)"
          class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 focus:border-purple-500/50 focus:outline-none"
        >
          <option value="exact">精确匹配</option>
          <option value="contains">包含</option>
        </select>
      </div>

      <!-- Toggle: single <-> multi condition -->
      <div v-if="['text','id','desc','className'].includes(strategy.type) || isMultiCondition" class="mt-2">
        <button
          type="button"
          class="text-xs text-purple-400 hover:text-purple-300 transition-colors"
          @click="toggleConditionMode"
        >
          {{ isMultiCondition ? '← 切换为单条件' : '→ 切换为多条件组合（AND/OR）' }}
        </button>
      </div>

      <!-- Multi-condition mode -->
      <div v-if="isMultiCondition" class="mt-3 space-y-3">
        <!-- AND/OR toggle -->
        <div class="flex items-center gap-2">
          <span class="text-xs text-slate-400">逻辑关系：</span>
          <button
            type="button"
            :class="(strategy.logic || 'and') === 'and'
              ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30'
              : 'text-slate-500 hover:text-slate-300 border-transparent'"
            class="px-3 py-1 text-xs font-medium rounded-lg border transition-colors"
            @click="setLogic('and')"
          >
            并且 (AND)
          </button>
          <button
            type="button"
            :class="(strategy.logic || 'and') === 'or'
              ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
              : 'text-slate-500 hover:text-slate-300 border-transparent'"
            class="px-3 py-1 text-xs font-medium rounded-lg border transition-colors"
            @click="setLogic('or')"
          >
            或者 (OR)
          </button>
        </div>

        <!-- Condition rows -->
        <div
          v-for="(cond, ci) in strategy.conditions"
          :key="ci"
          class="p-3 rounded-lg border border-white/10 bg-white/[0.03] space-y-2"
        >
          <div class="flex items-center gap-2">
            <span class="text-xs text-slate-500 font-mono w-5">#{{ ci + 1 }}</span>
            <select
              :value="cond.type"
              @change="onCondTypeChange(ci, $event.target.value)"
              class="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-xs text-slate-200 focus:border-purple-500/50 focus:outline-none"
            >
              <option v-for="ct in CONDITION_TYPES" :key="ct.value" :value="ct.value">
                {{ ct.label }}
              </option>
            </select>
            <button
              type="button"
              class="ml-auto text-slate-500 hover:text-red-400 transition-colors"
              @click="removeCondition(ci)"
              title="删除此条件"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          </div>
          <input
            :value="cond.value"
            @input="updateCondition(ci, 'value', $event.target.value)"
            :placeholder="CONDITION_TYPES.find(ct => ct.value === cond.type)?.placeholder || ''"
            class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none"
          />
          <select
            :value="cond.match_mode || 'exact'"
            @change="updateCondition(ci, 'match_mode', $event.target.value)"
            class="w-full rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-xs text-slate-200 focus:border-purple-500/50 focus:outline-none"
          >
            <option value="exact">精确匹配</option>
            <option value="contains">包含</option>
          </select>
        </div>

        <button
          type="button"
          class="w-full py-2 border border-dashed border-white/20 rounded-lg text-sm text-slate-400 hover:text-purple-300 hover:border-purple-500/30 transition-colors"
          @click="addCondition"
        >
          + 添加条件
        </button>
      </div>

            <!-- chain: step builder -->
      <div v-if="typeConfig.fields === 'chain'" class="space-y-2">
        <div class="flex items-center justify-between">
          <label class="text-xs text-slate-400">链式步骤</label>
          <span class="text-xs text-slate-500">filter=同元素 | parent=父 | child=子[0] | sibling=兄弟[0] （[0]内为索引，0=第1个）</span>
        </div>
        <div
          v-for="(step, si) in (strategy.steps || [])"
          :key="si"
          class="space-y-1.5 p-2 rounded-lg border border-white/10 bg-white/[0.03]"
        >
          <div class="flex items-center gap-2">
            <span class="text-xs text-slate-500 font-mono w-5">#{{ si + 1 }}</span>
            <!-- nav mode -->
            <select
              :value="step.nav || 'filter'"
              @change="updateStep(si, 'nav', $event.target.value)"
              class="rounded-lg border border-white/10 px-2 py-1 text-xs focus:border-purple-500/50 focus:outline-none"
              :class="(step.nav || 'filter') === 'parent' ? 'bg-amber-500/10 text-amber-300' : (step.nav || 'filter') === 'child' ? 'bg-emerald-500/10 text-emerald-300' : (step.nav || 'filter') === 'sibling' ? 'bg-cyan-500/10 text-cyan-300' : 'bg-white/5 text-slate-200'"
            >
              <option value="filter">filter 过滤</option>
              <option value="parent">parent 父节点</option>
              <option value="child">child 子节点</option>
              <option value="sibling">sibling 兄弟节点</option>
            </select>
            <!-- type + value (hidden for parent nav) -->
            <template v-if="(step.nav || 'filter') !== 'parent'">
              <select
                :value="step.type"
                @change="updateStep(si, 'type', $event.target.value)"
                class="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-xs text-slate-200 focus:border-purple-500/50 focus:outline-none"
              >
                <option value="className">类名</option>
                <option value="id">资源 ID</option>
                <option value="text">文本</option>
                <option value="desc">描述</option>
                <option value="classNameContains">类名包含</option>
                <option value="idContains">ID 包含</option>
                <option value="textContains">文本包含</option>
                <option value="descContains">描述包含</option>
              </select>
              <input
                :value="step.value"
                @input="updateStep(si, 'value', $event.target.value)"
                placeholder="值"
                class="flex-1 rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-xs text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none font-mono"
              />
              <input
                v-if="(step.nav || 'filter') === 'child' || (step.nav || 'filter') === 'sibling'"
                type="number" min="0"
                :value="step.index || 0"
                @input="updateStep(si, 'index', Number($event.target.value))"
                class="w-12 rounded-lg border border-white/10 bg-white/5 px-1 py-1 text-xs text-slate-200 text-center" placeholder="#"
                title="索引从0开始：0=第1个, 1=第2个, 2=第3个..."
              />
            </template>
            <span v-else class="flex-1 text-xs text-slate-500">不需要参数</span>
          </div>
          <button type="button" class="w-full text-xs text-slate-500 hover:text-red-400" @click="removeStep(si)">删除此步骤</button>
        </div>
        <div class="flex gap-2">
          <button type="button" class="flex-1 py-1.5 border border-dashed border-white/20 rounded-lg text-xs text-slate-400 hover:text-purple-300" @click="addStep">
            + filter 步骤
          </button>
          <button type="button" class="px-3 py-1.5 border border-dashed border-amber-500/20 rounded-lg text-xs text-amber-400 hover:text-amber-300" @click="addNavStep('parent')">
            + 父节点
          </button>
          <button type="button" class="px-3 py-1.5 border border-dashed border-cyan-500/20 rounded-lg text-xs text-cyan-400 hover:text-cyan-300" @click="addNavStep('sibling')">
            + 兄弟
          </button>
          <button type="button" class="px-3 py-1.5 border border-dashed border-emerald-500/20 rounded-lg text-xs text-emerald-400 hover:text-emerald-300" @click="addNavStep('child')">
            + 子节点
          </button>
        </div>
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
        点击位置偏移
      </button>
      <div v-if="showAdvanced" class="mt-2 space-y-2">
        <p class="text-xs text-slate-500 leading-relaxed">
          相对控件<strong class="text-slate-400">中心点</strong>的偏移量，按<strong class="text-slate-400">控件自身宽高百分比</strong>计算，不受分辨率影响。<br/>
          不填=点中心 &middot; 正数=右/下 &middot; 负数=左/上 &middot; 例如填 <code class="text-purple-400">150</code> 向右偏移 1.5 倍控件宽
        </p>
        <div class="flex gap-3">
          <div class="flex-1">
            <label class="text-xs text-slate-400 mb-1 block">水平偏移 %</label>
            <input
              type="number"
              :value="strategy.x_percent"
              @input="updateField('x_percent', $event.target.value !== '' ? Number($event.target.value) : undefined)"
              placeholder="0"
              class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none"
            />
          </div>
          <div class="flex-1">
            <label class="text-xs text-slate-400 mb-1 block">垂直偏移 %</label>
            <input
              type="number"
              :value="strategy.y_percent"
              @input="updateField('y_percent', $event.target.value !== '' ? Number($event.target.value) : undefined)"
              placeholder="0"
              class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
