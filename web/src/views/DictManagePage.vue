<template>
  <div class="dict-manage">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-white tracking-tight">系统字典管理</h1>
      <p class="text-sm text-slate-400 mt-1.5">管理字典分类和下拉选项值，创建、编辑、删除分类及选项</p>
    </div>

    <!-- Category Tabs -->
    <div class="flex gap-2 mb-8 flex-wrap items-center">
      <button
        v-for="cat in categories" :key="cat.id"
        @click="currentCat = cat.key"
        class="cat-tab group"
        :class="currentCat === cat.key ? 'cat-tab--active' : ''"
      >
        <span class="cat-tab-label">{{ cat.label }}</span>
        <span class="cat-tab-count">{{ cat.item_count ?? 0 }}</span>
        <!-- Edit/Delete controls -->
        <span class="cat-tab-actions">
          <button @click.stop="startEditCat(cat)" class="cat-tab-action" title="编辑分类">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
          </button>
          <button @click.stop="confirmDeleteCat(cat)" class="cat-tab-action cat-tab-action--danger" title="删除分类">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
          </button>
        </span>
      </button>

      <!-- Inline add category form -->
      <div v-if="addingCat" class="cat-add-form">
        <input v-model="newCatLabel" @keyup.enter="addCategory" placeholder="分类名称"
               class="cat-add-input" ref="catLabelInput" />
        <input v-model="newCatKey" placeholder="key (可选)"
               class="cat-add-input cat-add-input--key" @keyup.enter="addCategory" />
        <button @click="addCategory" class="cat-add-btn cat-add-btn--confirm" title="确认">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>
        </button>
        <button @click="cancelAddCat" class="cat-add-btn cat-add-btn--cancel" title="取消">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
      </div>
      <button v-else @click="startAddCat" class="cat-add-trigger">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
        新增分类
      </button>
    </div>

    <!-- Edit Category Modal -->
    <Teleport to="body">
      <transition name="modal">
        <div v-if="editingCat" class="modal-overlay" @click.self="cancelEditCat">
          <div class="modal-card">
            <div class="modal-header">
              <h3 class="modal-title">编辑分类</h3>
              <button @click="cancelEditCat" class="modal-close" title="关闭">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
              </button>
            </div>
            <div class="modal-body">
              <div class="form-group">
                <label class="form-label">Key <span class="form-hint">唯一标识，不可与其他分类重复</span></label>
                <input v-model="editCatKey" class="form-input" placeholder="e.g. series_genre" />
              </div>
              <div class="form-group">
                <label class="form-label">显示名称</label>
                <input v-model="editCatLabel" class="form-input" placeholder="e.g. 系列类型" @keyup.enter="saveCategory" />
              </div>
            </div>
            <div class="modal-footer">
              <button @click="cancelEditCat" class="btn btn--secondary">取消</button>
              <button @click="saveCategory" class="btn btn--primary">保存修改</button>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>

    <!-- Delete Confirmation Modal -->
    <Teleport to="body">
      <transition name="modal">
        <div v-if="deletingCat" class="modal-overlay" @click.self="deletingCat = null">
          <div class="modal-card modal-card--sm">
            <div class="modal-header">
              <h3 class="modal-title text-red-400">删除分类</h3>
            </div>
            <div class="modal-body">
              <p class="text-slate-300 text-sm">确定要删除分类 <span class="text-white font-semibold">「{{ deletingCat.label }}」</span> 吗？</p>
              <p class="text-slate-500 text-xs mt-2">该分类下的所有选项将被级联删除，此操作不可撤销。</p>
            </div>
            <div class="modal-footer">
              <button @click="deletingCat = null" class="btn btn--secondary">取消</button>
              <button @click="doDeleteCat" class="btn btn--danger">确认删除</button>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>

    <!-- Item List Card -->
    <div class="list-card">
      <!-- Add item row -->
      <div class="list-add-row">
        <input v-model="newLabel" @keyup.enter="addItem" placeholder="输入选项显示名称后回车添加"
               class="list-add-input list-add-input--label" />
        <input v-model="newValue" placeholder="value (可选)"
               class="list-add-input list-add-input--value" @keyup.enter="addItem" />
        <button @click="addItem" class="btn btn--primary btn--sm" :disabled="!newLabel.trim()">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
          添加
        </button>
      </div>

      <!-- Empty state -->
      <div v-if="items.length === 0" class="list-empty">
        <svg class="w-10 h-10 text-slate-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>
        <p class="text-slate-500 text-sm">此分类暂无选项</p>
        <p class="text-slate-600 text-xs mt-1">在上方输入框中添加第一个选项</p>
      </div>

      <!-- Item list -->
      <div v-else class="list-body">
        <transition-group name="item">
          <div v-for="item in items" :key="item.id" class="list-item">
            <!-- Sort handle -->
            <span class="list-item-grip" title="拖拽排序">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8h16M4 16h16"/></svg>
            </span>

            <!-- Value -->
            <code class="list-item-value">{{ item.value }}</code>

            <!-- Editable label -->
            <input
              :value="item.label"
              @blur="e => saveLabel(item, e.target.value)"
              @keyup.enter="e => e.target.blur()"
              class="list-item-input"
            />

            <!-- Status toggle -->
            <button
              @click="toggleItem(item)"
              class="list-item-toggle"
              :class="item.enabled ? 'list-item-toggle--on' : 'list-item-toggle--off'"
              :title="item.enabled ? '已启用，点击禁用' : '已禁用，点击启用'"
            >
              <span class="list-item-toggle-dot"></span>
              <span class="list-item-toggle-label">{{ item.enabled ? '启用' : '禁用' }}</span>
            </button>

            <!-- Delete -->
            <button @click="removeItem(item)" class="list-item-delete" title="删除此选项">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
            </button>
          </div>
        </transition-group>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import {
  listCategories, createCategory, updateCategory, deleteCategory,
  listAllItems, createItem, updateItem, deleteItem,
} from '../api/referenceData.js'

const categories = ref([])
const currentCat = ref('')
const items = ref([])
const newLabel = ref('')
const newValue = ref('')

const addingCat = ref(false)
const newCatKey = ref('')
const newCatLabel = ref('')
const catLabelInput = ref(null)
const editingCat = ref(null)
const editCatKey = ref('')
const editCatLabel = ref('')
const deletingCat = ref(null)

function startAddCat() {
  addingCat.value = true
  nextTick(() => catLabelInput.value?.focus())
}

async function loadCategories() {
  const { data } = await listCategories()
  if (data.ok) {
    categories.value = data.categories
    if (!currentCat.value && data.categories.length) {
      currentCat.value = data.categories[0].key
    }
  }
}

async function addCategory() {
  if (!newCatLabel.value.trim()) return
  const key = newCatKey.value.trim() || newCatLabel.value.trim()
  await createCategory({ key, label: newCatLabel.value.trim() })
  newCatKey.value = ''; newCatLabel.value = ''; addingCat.value = false
  await loadCategories()
}

function cancelAddCat() {
  newCatKey.value = ''; newCatLabel.value = ''; addingCat.value = false
}

function startEditCat(cat) {
  editingCat.value = cat
  editCatKey.value = cat.key
  editCatLabel.value = cat.label
}

function cancelEditCat() {
  editingCat.value = null
}

async function saveCategory() {
  if (!editingCat.value) return
  await updateCategory(editingCat.value.id, { key: editCatKey.value, label: editCatLabel.value })
  editingCat.value = null
  await loadCategories()
}

function confirmDeleteCat(cat) {
  deletingCat.value = cat
}

async function doDeleteCat() {
  if (!deletingCat.value) return
  const cat = deletingCat.value
  await deleteCategory(cat.id)
  if (currentCat.value === cat.key) currentCat.value = ''
  deletingCat.value = null
  await loadCategories()
  if (!currentCat.value && categories.value.length) {
    currentCat.value = categories.value[0].key
  }
}

async function load() {
  if (!currentCat.value) { items.value = []; return }
  const { data } = await listAllItems(currentCat.value)
  if (data.ok) items.value = data.items
}

async function addItem() {
  if (!newLabel.value.trim()) return
  await createItem({ category: currentCat.value, value: newValue.value || newLabel.value, label: newLabel.value })
  newLabel.value = ''; newValue.value = ''
  await load()
}

async function saveLabel(item, newLabel) {
  if (newLabel !== item.label) { await updateItem(item.id, { label: newLabel }); item.label = newLabel }
}

async function toggleItem(item) {
  await updateItem(item.id, { enabled: !item.enabled }); await load()
}

async function removeItem(item) {
  await deleteItem(item.id); await load()
}

watch(currentCat, load)
onMounted(async () => { await loadCategories(); await load() })
</script>

<style scoped>
/* ===== Category Tabs ===== */
.cat-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 200ms ease;
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(71, 85, 105, 0.2);
  color: #cbd5e1;
  position: relative;
}
.cat-tab:hover {
  background: rgba(51, 65, 85, 0.6);
  border-color: rgba(71, 85, 105, 0.4);
  color: #e2e8f0;
}
.cat-tab--active {
  background: rgba(14, 165, 233, 0.12);
  border-color: rgba(14, 165, 233, 0.3);
  color: #38bdf8;
  box-shadow: 0 0 12px rgba(14, 165, 233, 0.08);
}
.cat-tab-count {
  font-size: 11px;
  opacity: 0.55;
  font-variant-numeric: tabular-nums;
  min-width: 8px;
}
.cat-tab-actions {
  display: none;
  gap: 2px;
  margin-left: 4px;
  align-items: center;
}
.cat-tab:hover .cat-tab-actions {
  display: inline-flex;
}
.cat-tab-action {
  padding: 2px 4px;
  border-radius: 4px;
  background: none;
  border: none;
  cursor: pointer;
  color: #94a3b8;
  transition: all 150ms;
  display: inline-flex;
  align-items: center;
}
.cat-tab-action:hover {
  color: #fbbf24;
  background: rgba(251, 191, 36, 0.1);
}
.cat-tab-action--danger:hover {
  color: #f87171;
  background: rgba(248, 113, 113, 0.1);
}

/* ===== Inline Add Category ===== */
.cat-add-form {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 10px;
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid rgba(14, 165, 233, 0.25);
  box-shadow: 0 0 10px rgba(14, 165, 233, 0.06);
}
.cat-add-input {
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(71, 85, 105, 0.3);
  border-radius: 6px;
  padding: 3px 8px;
  font-size: 13px;
  color: #e2e8f0;
  outline: none;
  width: 100px;
  transition: border-color 150ms;
}
.cat-add-input::placeholder { color: #64748b; }
.cat-add-input:focus { border-color: rgba(14, 165, 233, 0.5); }
.cat-add-input--key { width: 80px; }
.cat-add-btn {
  padding: 2px 6px;
  border-radius: 5px;
  border: none;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  transition: all 150ms;
}
.cat-add-btn--confirm {
  background: rgba(14, 165, 233, 0.15);
  color: #38bdf8;
}
.cat-add-btn--confirm:hover { background: rgba(14, 165, 233, 0.3); }
.cat-add-btn--cancel {
  background: none;
  color: #64748b;
}
.cat-add-btn--cancel:hover { color: #94a3b8; }

.cat-add-trigger {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 200ms;
  background: none;
  border: 1px dashed rgba(100, 116, 139, 0.4);
  color: #64748b;
}
.cat-add-trigger:hover {
  border-color: rgba(148, 163, 184, 0.6);
  color: #94a3b8;
}

/* ===== Modal ===== */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(4px);
}
.modal-card {
  background: rgba(15, 23, 42, 0.95);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(71, 85, 105, 0.3);
  border-radius: 16px;
  width: 420px;
  max-width: calc(100vw - 32px);
  box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5);
}
.modal-card--sm { width: 380px; }
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 0;
}
.modal-title {
  font-size: 16px;
  font-weight: 600;
  color: #f1f5f9;
}
.modal-close {
  padding: 4px;
  border-radius: 8px;
  border: none;
  background: none;
  color: #64748b;
  cursor: pointer;
  transition: all 150ms;
  display: flex;
}
.modal-close:hover { color: #e2e8f0; background: rgba(71, 85, 105, 0.2); }
.modal-body { padding: 20px 24px; }
.modal-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding: 0 24px 20px;
}

/* ===== Form ===== */
.form-group { margin-bottom: 16px; }
.form-group:last-child { margin-bottom: 0; }
.form-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #cbd5e1;
  margin-bottom: 6px;
}
.form-hint {
  font-weight: 400;
  color: #64748b;
  margin-left: 6px;
}
.form-input {
  width: 100%;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid rgba(71, 85, 105, 0.3);
  color: #e2e8f0;
  font-size: 14px;
  outline: none;
  transition: border-color 150ms;
  box-sizing: border-box;
}
.form-input::placeholder { color: #475569; }
.form-input:focus { border-color: rgba(14, 165, 233, 0.5); }

/* ===== Buttons ===== */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: all 150ms;
}
.btn--sm { padding: 6px 12px; font-size: 13px; }
.btn--primary { background: #0284c7; color: #fff; }
.btn--primary:hover { background: #0369a1; }
.btn--primary:disabled { opacity: 0.4; cursor: not-allowed; }
.btn--secondary { background: rgba(71, 85, 105, 0.3); color: #cbd5e1; }
.btn--secondary:hover { background: rgba(71, 85, 105, 0.5); }
.btn--danger { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.25); }
.btn--danger:hover { background: rgba(239, 68, 68, 0.3); }

/* ===== List Card ===== */
.list-card {
  border-radius: 16px;
  border: 1px solid rgba(71, 85, 105, 0.15);
  overflow: hidden;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(12px);
}
.list-add-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(71, 85, 105, 0.12);
}
.list-add-input {
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(71, 85, 105, 0.2);
  color: #e2e8f0;
  font-size: 13px;
  outline: none;
  transition: border-color 150ms;
}
.list-add-input::placeholder { color: #475569; }
.list-add-input:focus { border-color: rgba(14, 165, 233, 0.45); }
.list-add-input--label { flex: 1; }
.list-add-input--value { width: 140px; }

.list-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
}

.list-body {
  max-height: 480px;
  overflow-y: auto;
}
.list-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 20px;
  transition: background 150ms;
  border-bottom: 1px solid rgba(71, 85, 105, 0.06);
}
.list-item:last-child { border-bottom: none; }
.list-item:hover { background: rgba(30, 41, 59, 0.35); }

.list-item-grip {
  color: #475569;
  flex-shrink: 0;
  cursor: grab;
  display: flex;
  opacity: 0;
  transition: opacity 150ms;
}
.list-item:hover .list-item-grip { opacity: 1; }

.list-item-value {
  font-size: 12px;
  color: #64748b;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  min-width: 80px;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  background: rgba(30, 41, 59, 0.4);
  padding: 2px 8px;
  border-radius: 5px;
  flex-shrink: 0;
}
.list-item-input {
  flex: 1;
  padding: 6px 10px;
  border-radius: 6px;
  background: transparent;
  border: 1px solid transparent;
  color: #e2e8f0;
  font-size: 13px;
  outline: none;
  transition: all 150ms;
}
.list-item-input:hover { background: rgba(30, 41, 59, 0.4); }
.list-item-input:focus {
  background: rgba(30, 41, 59, 0.7);
  border-color: rgba(14, 165, 233, 0.35);
}

/* Toggle switch */
.list-item-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 500;
  border: 1px solid;
  cursor: pointer;
  transition: all 200ms;
  background: none;
  flex-shrink: 0;
}
.list-item-toggle--on {
  color: #34d399;
  border-color: rgba(52, 211, 153, 0.25);
}
.list-item-toggle--on:hover { background: rgba(52, 211, 153, 0.08); }
.list-item-toggle--off {
  color: #475569;
  border-color: rgba(71, 85, 105, 0.2);
}
.list-item-toggle--off:hover { background: rgba(71, 85, 105, 0.1); color: #94a3b8; }
.list-item-toggle-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}
.list-item-toggle--on .list-item-toggle-dot {
  box-shadow: 0 0 6px currentColor;
}

.list-item-delete {
  padding: 5px;
  border-radius: 6px;
  border: none;
  background: none;
  color: #475569;
  cursor: pointer;
  transition: all 150ms;
  display: flex;
  opacity: 0;
  flex-shrink: 0;
}
.list-item:hover .list-item-delete { opacity: 1; }
.list-item-delete:hover { color: #f87171; background: rgba(239, 68, 68, 0.1); }

/* ===== Transitions ===== */
.modal-enter-active, .modal-leave-active {
  transition: opacity 200ms ease;
}
.modal-enter-active .modal-card, .modal-leave-active .modal-card {
  transition: transform 200ms ease, opacity 200ms ease;
}
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .modal-card { transform: scale(0.95) translateY(8px); opacity: 0; }
.modal-leave-to .modal-card { transform: scale(0.95) translateY(8px); opacity: 0; }

.item-enter-active { transition: all 250ms ease; }
.item-leave-active { transition: all 200ms ease; }
.item-enter-from { opacity: 0; transform: translateX(-12px); }
.item-leave-to { opacity: 0; transform: translateX(12px); }
</style>
