# 选择器策略卡片构建器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the JSON textarea strategy editor with a visual card-based builder, keeping a JSON toggle for power users.

**Architecture:** New `StrategyCard.vue` component renders individual strategy cards with type-specific fields. `SelectorsPage.vue` manages a `strategyList` ref array with bidirectional sync to the JSON string. Mode toggle switches between form builder and raw JSON textarea. No new dependencies — up/down arrows for reordering, HTML5 file input for image templates.

**Tech Stack:** Vue 3 `<script setup>`, Tailwind CSS, HeadlessUI (already in project)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `web/src/components/StrategyCard.vue` | **Create** | Single strategy card: type dropdown, dynamic fields, reorder arrows, delete, validation display |
| `web/src/views/SelectorsPage.vue` | **Modify** | Mode toggle, strategyList state, bidirectional sync, card list rendering, updated handleSave with form-mode validation |

No backend changes. No API changes. JSON data structure unchanged.

---

### Task 1: Create StrategyCard.vue Component

**Files:**
- Create: `web/src/components/StrategyCard.vue`

This component renders one strategy card. It receives a strategy object and emits updates. The parent owns the list; this component owns nothing.

- [ ] **Step 1: Create the component file with props, emits, and type config**

```vue
<!-- web/src/components/StrategyCard.vue -->
<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  strategy: { type: Object, required: true },
  index: { type: Number, required: true },
  totalCount: { type: Number, required: true },
  actionName: { type: String, default: '' },
})

const emit = defineEmits(['update', 'delete', 'move-up', 'move-down'])

// Type definitions with Chinese labels and field config
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
  // Preserve common fields, reset type-specific ones
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
</script>
```

- [ ] **Step 2: Add the template for the card**

Append to the same file, after the `</script>` tag:

```vue
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
```

- [ ] **Step 3: Add the image file select handler to the script**

Add this function inside the `<script setup>` block, after the `onTypeChange` function:

```javascript
async function onImageFileSelect(e) {
  const file = e.target.files?.[0]
  if (!file) return
  // Upload via existing API
  const { uploadTemplate } = await import('../api/selectors.js')
  try {
    const res = await uploadTemplate(file, props.actionName || 'template')
    updateField('template', res.data.filename)
  } catch (err) {
    // Show error via parent or inline — for now just alert
    alert('上传失败: ' + (err.response?.data?.detail || err.message))
  }
  // Reset file input so same file can be re-selected
  e.target.value = ''
}
```

- [ ] **Step 4: Verify the component renders without errors**

Run the dev server and check that the component file has no syntax errors:
```bash
cd d:/devWorkspace/jsProjects/dy_auto/web && npx vite build --mode development 2>&1 | tail -5
```
Expected: Build succeeds (no compile errors in the new component).

- [ ] **Step 5: Commit**

```bash
git add web/src/components/StrategyCard.vue
git commit -m "feat: add StrategyCard component for visual strategy editing"
```

---

### Task 2: Refactor SelectorsPage.vue — State and Mode Switching

**Files:**
- Modify: `web/src/views/SelectorsPage.vue`

This task adds the state management for form mode and the bidirectional sync logic. No UI changes yet — just data layer.

- [ ] **Step 1: Add StrategyCard import and new state variables**

In the imports section, add after the existing component imports:

```javascript
import StrategyCard from '../components/StrategyCard.vue'
```

After the `existingTemplates` ref (line ~113), add:

```javascript
// --- Strategy builder state ---
const editMode = ref('form') // 'form' | 'json'
const strategyList = ref([]) // Array of strategy objects (form mode)
const strategyError = ref(null) // Validation error for strategies
```

- [ ] **Step 2: Add form↔JSON conversion functions**

After the state declarations, add:

```javascript
// --- Strategy form ↔ JSON sync ---
const VALID_TYPES = new Set(['text', 'id', 'desc', 'className', 'package', 'coordinate', 'image'])

function strategiesToList(jsonStr) {
  try {
    const arr = JSON.parse(jsonStr)
    if (!Array.isArray(arr)) return { ok: false, error: '不是 JSON 数组' }
    for (const s of arr) {
      if (!s.type || !VALID_TYPES.has(s.type)) {
        return { ok: false, error: `未知策略类型: ${s.type}` }
      }
    }
    return { ok: true, list: arr }
  } catch (e) {
    return { ok: false, error: 'JSON 解析失败: ' + e.message }
  }
}

function listToStrategies(list) {
  return list.map((s, i) => {
    const out = { ...s, priority: i + 1 }
    // Clean up undefined fields
    if (out.x_percent === undefined) delete out.x_percent
    if (out.y_percent === undefined) delete out.y_percent
    return out
  })
}

function syncFormToJson() {
  form.strategies = JSON.stringify(listToStrategies(strategyList.value), null, 2)
}

function syncJsonToForm() {
  const result = strategiesToList(form.strategies)
  if (result.ok) {
    strategyList.value = result.list
    strategyError.value = null
    return true
  } else {
    strategyError.value = result.error
    return false
  }
}
```

- [ ] **Step 3: Add strategy card event handlers**

```javascript
// --- Strategy card handlers ---
function addStrategy() {
  strategyList.value.push({ type: 'text', value: '' })
  syncFormToJson()
}

function removeStrategy(idx) {
  strategyList.value.splice(idx, 1)
  syncFormToJson()
}

function updateStrategy(idx, newStrategy) {
  strategyList.value[idx] = newStrategy
  syncFormToJson()
}

function moveStrategyUp(idx) {
  if (idx <= 0) return
  const list = strategyList.value
  ;[list[idx - 1], list[idx]] = [list[idx], list[idx - 1]]
  syncFormToJson()
}

function moveStrategyDown(idx) {
  const list = strategyList.value
  if (idx >= list.length - 1) return
  ;[list[idx], list[idx + 1]] = [list[idx + 1], list[idx]]
  syncFormToJson()
}
```

- [ ] **Step 4: Update openCreateDialog and openEditDialog to initialize strategyList**

Update `openCreateDialog`:

```javascript
function openCreateDialog() {
  isEditing.value = false
  form.action_name = ''
  form.platform_version = ''
  form.strategies = '[]'
  formError.value = null
  strategyError.value = null
  strategyList.value = []
  editMode.value = 'form'
  existingTemplates.value = []
  showFormDialog.value = true
}
```

Update `openEditDialog`:

```javascript
function openEditDialog(sel) {
  isEditing.value = true
  form.action_name = sel.action_name
  form.platform_version = sel.platform_version || ''
  form.strategies = JSON.stringify(sel.strategies || [], null, 2)
  formError.value = null
  strategyError.value = null
  editMode.value = 'form'
  existingTemplates.value = []
  // Initialize strategy list from existing data
  const result = strategiesToList(form.strategies)
  if (result.ok) {
    strategyList.value = result.list
  } else {
    // Fallback to JSON mode if parse fails
    strategyList.value = []
    editMode.value = 'json'
    strategyError.value = result.error
  }
  loadExistingTemplates(sel.strategies || [])
  showFormDialog.value = true
}
```

- [ ] **Step 5: Update handleSave to use mode-aware parsing**

Replace the current `handleSave` function's strategy parsing block (the `let parsedStrategies` section):

```javascript
async function handleSave() {
  if (!form.action_name.trim()) {
    formError.value = 'action_name 不能为空'
    return
  }

  let parsedStrategies
  if (editMode.value === 'form') {
    // Validate form-mode strategies
    const errors = validateStrategies(strategyList.value)
    if (errors.length > 0) {
      strategyError.value = errors[0]
      return
    }
    parsedStrategies = listToStrategies(strategyList.value)
  } else {
    // JSON mode: parse textarea
    try {
      parsedStrategies = JSON.parse(form.strategies)
      if (!Array.isArray(parsedStrategies)) {
        formError.value = 'strategies 必须是 JSON 数组'
        return
      }
    } catch {
      formError.value = 'strategies JSON 格式不正确'
      return
    }
  }

  // ... rest of save logic unchanged ...
```

Add the validation function:

```javascript
function validateStrategies(list) {
  if (list.length === 0) return ['至少需要一个查找策略']
  const errors = []
  for (let i = 0; i < list.length; i++) {
    const s = list[i]
    const prefix = `策略 #${i + 1}: `
    if (['text', 'id', 'desc', 'className', 'package'].includes(s.type)) {
      if (!s.value || !s.value.trim()) errors.push(prefix + '查找值不能为空')
    } else if (s.type === 'coordinate') {
      if (s.x_percent == null || s.x_percent < 0 || s.x_percent > 100) errors.push(prefix + 'X 坐标需在 0-100 之间')
      if (s.y_percent == null || s.y_percent < 0 || s.y_percent > 100) errors.push(prefix + 'Y 坐标需在 0-100 之间')
    } else if (s.type === 'image') {
      if (!s.template || !s.template.trim()) errors.push(prefix + '模板文件名不能为空')
    }
  }
  return errors
}
```

- [ ] **Step 6: Add mode switch handler**

```javascript
function switchMode(mode) {
  if (mode === editMode.value) return
  if (mode === 'json') {
    // Form → JSON: sync from strategyList
    syncFormToJson()
    editMode.value = 'json'
    strategyError.value = null
  } else {
    // JSON → Form: parse JSON into strategyList
    if (syncJsonToForm()) {
      editMode.value = 'form'
    }
    // If syncJsonToForm fails, strategyError is set, stay in JSON mode
  }
}
```

- [ ] **Step 7: Verify the page still builds without errors**

```bash
cd d:/devWorkspace/jsProjects/dy_auto/web && npx vite build --mode development 2>&1 | tail -5
```
Expected: Build succeeds.

- [ ] **Step 8: Commit**

```bash
git add web/src/views/SelectorsPage.vue
git commit -m "feat: add strategy builder state management and mode switching"
```

---

### Task 3: Replace textarea with card builder UI

**Files:**
- Modify: `web/src/views/SelectorsPage.vue`

This task replaces the JSON textarea in the dialog with the card builder and mode tabs.

- [ ] **Step 1: Replace the strategies textarea section with mode tabs + card builder**

Find the current strategies section (the `<div>` containing the textarea with id `sel-strategies`) and replace the entire block from the `<label>` through the `<details>` tooltip section with:

```vue
                  <!-- strategies -->
                  <div>
                    <div class="flex items-center justify-between mb-2">
                      <label class="flex items-center gap-1.5 text-sm font-medium text-slate-300">
                        选择策略
                        <span class="text-red-400">*</span>
                      </label>
                      <!-- Mode tabs -->
                      <div class="flex rounded-lg border border-white/10 overflow-hidden">
                        <button
                          type="button"
                          :class="[
                            'px-3 py-1 text-xs font-medium transition-colors',
                            editMode === 'form'
                              ? 'bg-purple-500/20 text-purple-300'
                              : 'text-slate-400 hover:text-slate-200',
                          ]"
                          @click="switchMode('form')"
                        >
                          表单模式
                        </button>
                        <button
                          type="button"
                          :class="[
                            'px-3 py-1 text-xs font-medium transition-colors border-l border-white/10',
                            editMode === 'json'
                              ? 'bg-purple-500/20 text-purple-300'
                              : 'text-slate-400 hover:text-slate-200',
                          ]"
                          @click="switchMode('json')"
                        >
                          JSON
                        </button>
                      </div>
                    </div>

                    <!-- Form mode: card builder -->
                    <div v-if="editMode === 'form'">
                      <!-- Empty state -->
                      <div
                        v-if="strategyList.length === 0"
                        class="text-center py-8 text-slate-500 text-sm border-2 border-dashed border-white/10 rounded-lg"
                      >
                        点击下方按钮添加第一个查找策略
                      </div>

                      <!-- Strategy cards -->
                      <div v-else class="space-y-3">
                        <StrategyCard
                          v-for="(s, idx) in strategyList"
                          :key="idx"
                          :strategy="s"
                          :index="idx"
                          :total-count="strategyList.length"
                          :action-name="form.action_name"
                          @update="updateStrategy(idx, $event)"
                          @delete="removeStrategy(idx)"
                          @move-up="moveStrategyUp(idx)"
                          @move-down="moveStrategyDown(idx)"
                        />
                      </div>

                      <!-- Add button -->
                      <button
                        type="button"
                        class="mt-3 w-full rounded-lg border-2 border-dashed border-white/10 py-2 text-sm text-slate-400 hover:border-purple-500/40 hover:text-purple-300 transition-colors"
                        @click="addStrategy"
                      >
                        + 添加策略
                      </button>
                    </div>

                    <!-- JSON mode: textarea -->
                    <div v-else>
                      <textarea
                        id="sel-strategies"
                        v-model="form.strategies"
                        rows="8"
                        required
                        class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 font-mono"
                        placeholder='[{"type":"text","value":"赞","priority":1}]'
                      />
                      <p class="mt-1 text-xs text-slate-500">
                        JSON 数组，每个策略包含 type、value、priority 等字段
                      </p>
                    </div>

                    <!-- Validation error -->
                    <p v-if="strategyError" class="mt-2 text-xs text-red-400">{{ strategyError }}</p>
                  </div>
```

- [ ] **Step 2: Remove the old template upload section from the dialog**

The standalone template upload section (the `<div>` containing the file input with label "模板图片（图找图）") is no longer needed — image template upload is now integrated into the StrategyCard. Find and remove the entire template section from the dialog, from the label "模板图片（图找图）" through the template error `<p>` tag.

Also remove the standalone `templateFile`, `templatePreview`, `uploadingTemplate`, `templateError` state variables and the `onTemplateFileChange`, `handleUploadTemplate`, `clearTemplatePreview` functions — they are replaced by the StrategyCard's built-in image upload.

Keep `existingTemplates`, `loadExistingTemplates`, `removeExistingTemplate`, `cleanupExistingTemplates` — those are still used for previewing templates in edit mode.

- [ ] **Step 3: Verify the dev server renders correctly**

```bash
cd d:/devWorkspace/jsProjects/dy_auto/web && npx vite build --mode development 2>&1 | tail -5
```
Expected: Build succeeds. No unused import warnings for `uploadTemplate`, `listTemplates`, `deleteTemplate` if they were only used in the removed template section.

- [ ] **Step 4: Commit**

```bash
git add web/src/views/SelectorsPage.vue
git commit -m "feat: replace strategy textarea with card builder UI"
```

---

### Task 4: Clean up unused imports and verify end-to-end

**Files:**
- Modify: `web/src/views/SelectorsPage.vue`

- [ ] **Step 1: Remove unused imports**

Check if `uploadTemplate`, `listTemplates`, `deleteTemplate` are still used anywhere in the file. If the template section was fully removed and StrategyCard handles its own upload via dynamic import, remove these from the import statement:

```javascript
// Remove if no longer used:
// uploadTemplate,
// listTemplates,
// deleteTemplate,
```

Also remove `templateFile`, `templatePreview`, `uploadingTemplate`, `templateError`, `onTemplateFileChange`, `handleUploadTemplate`, `clearTemplatePreview` if they still exist.

- [ ] **Step 2: Build and verify no warnings**

```bash
cd d:/devWorkspace/jsProjects/dy_auto/web && npx vite build 2>&1 | tail -10
```
Expected: Production build succeeds with no warnings about unused variables.

- [ ] **Step 3: Commit**

```bash
git add web/src/views/SelectorsPage.vue
git commit -m "chore: clean up unused template upload code from SelectorsPage"
```

---

## Self-Review Checklist

**Spec coverage:**
- Mode toggle (form/JSON) — Task 3 Step 1
- Strategy cards with type-specific fields — Task 1
- Reorder via up/down arrows — Task 1 Step 2
- Auto-numbering #1, #2, #3 — Task 1 Step 2
- Priority auto-assignment on save — Task 2 Step 2 (`listToStrategies`)
- Type dropdown with 7 types — Task 1 Step 1 (`STRATEGY_TYPES`)
- coordinate type: x/y inputs — Task 1 Step 2
- image type: template + threshold — Task 1 Step 2
- image file upload in card — Task 1 Step 3
- Advanced x/y offset (collapsible) — Task 1 Step 2
- Validation on save — Task 2 Step 5
- Empty state — Task 3 Step 1
- Bidirectional sync — Task 2 Steps 2 + 6
- JSON parse error handling — Task 2 Step 2 (`strategiesToList`)
- Add strategy button — Task 3 Step 1
- Delete strategy — Task 1 Step 2
- Existing template preview in edit mode — preserved from current code

**No placeholders.** Every step has actual code.

**Type consistency:** `STRATEGY_TYPES`, `strategyList`, `editMode`, `strategyError`, `syncFormToJson`, `syncJsonToForm`, `validateStrategies`, `listToStrategies`, `strategiesToList` — all defined in Task 2, used in Task 3.

**No new dependencies.** Up/down arrows use SVG icons (already the project pattern). No drag-and-drop library.
