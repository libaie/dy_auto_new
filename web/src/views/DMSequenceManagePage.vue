<script setup>
import { ref, reactive, onMounted } from 'vue'
import { listDMSequences, createDMSequence, updateDMSequence, deleteDMSequence } from '../api/dmSequences.js'
import { useToastStore } from '../stores/toast.js'

const toast = useToastStore()
const loading = ref(false)
const sequences = ref([])
const showEditor = ref(false)
const editingId = ref(null)

const form = reactive({
  name: '',
  industry: '',
  messages: [{ order: 1, content: '', delay_ms: 3000 }],
})

function resetForm() {
  form.name = ''
  form.industry = ''
  form.messages = [{ order: 1, content: '', delay_ms: 3000 }]
  editingId.value = null
}

function addMessage() {
  if (form.messages.length >= 10) { toast.error('最多 10 条消息'); return }
  form.messages.push({ order: form.messages.length + 1, content: '', delay_ms: 3000 })
}

function removeMessage(idx) {
  if (form.messages.length <= 1) { toast.error('至少保留 1 条消息'); return }
  form.messages.splice(idx, 1)
  // Re-number
  form.messages.forEach(function (m, i) { m.order = i + 1 })
}

function moveUp(idx) {
  if (idx === 0) return
  var tmp = form.messages[idx - 1]
  form.messages[idx - 1] = form.messages[idx]
  form.messages[idx] = tmp
  form.messages.forEach(function (m, i) { m.order = i + 1 })
}

function moveDown(idx) {
  if (idx >= form.messages.length - 1) return
  var tmp = form.messages[idx + 1]
  form.messages[idx + 1] = form.messages[idx]
  form.messages[idx] = tmp
  form.messages.forEach(function (m, i) { m.order = i + 1 })
}

function openCreate() {
  resetForm()
  showEditor.value = true
}

function openEdit(seq) {
  form.name = seq.name
  form.industry = seq.industry || ''
  form.messages = JSON.parse(JSON.stringify(seq.messages))
  editingId.value = seq.id
  showEditor.value = true
}

async function handleSave() {
  var valid = form.messages.filter(function (m) { return m.content.trim() })
  if (!form.name.trim()) { toast.error('请输入模板名称'); return }
  if (valid.length === 0) { toast.error('请至少填写一条消息内容'); return }
  try {
    if (editingId.value) {
      await updateDMSequence(editingId.value, {
        name: form.name, industry: form.industry, messages: form.messages,
      })
      toast.success('已更新')
    } else {
      await createDMSequence({
        name: form.name, industry: form.industry, messages: form.messages,
      })
      toast.success('已创建')
    }
    showEditor.value = false
    fetchData()
  } catch (e) {
    toast.error(e?.response?.data?.detail || '保存失败')
  }
}

async function handleDelete(seq) {
  if (!confirm('确认删除序列模板 "' + seq.name + '"？')) return
  try {
    await deleteDMSequence(seq.id)
    toast.success('已删除')
    fetchData()
  } catch (e) {
    toast.error('删除失败')
  }
}

async function fetchData() {
  loading.value = true
  try {
    var res = await listDMSequences()
    sequences.value = res.data.sequences || []
  } catch (e) {
    toast.error('加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">DM 序列模板</h1>
        <p class="text-sm text-slate-400 mt-1">预设私信发送序列，控制内容和发送间隔</p>
      </div>
      <button @click="openCreate" class="bg-sky-500 hover:bg-sky-400 text-white px-4 py-2 rounded-lg transition cursor-pointer">
        + 新建模板
      </button>
    </div>

    <div v-if="loading" class="text-slate-400 text-center py-12">加载中...</div>
    <div v-else-if="sequences.length === 0" class="text-slate-500 text-center py-12">
      暂无私信序列模板，点击"新建模板"创建
    </div>
    <div v-else class="grid grid-cols-1 gap-4">
      <div v-for="s in sequences" :key="s.id"
           class="rounded-xl border border-gray-700/50 p-5" style="background: rgba(15,23,42,0.5); backdrop-filter: blur(8px)">
        <div class="flex justify-between items-start">
          <div>
            <h3 class="text-lg font-semibold text-white">{{ s.name }}</h3>
            <p class="text-sm text-slate-400 mt-1">{{ s.message_count }} 条消息
              <span v-if="s.industry" class="ml-2 px-2 py-0.5 rounded text-xs bg-white/5 text-slate-300">{{ s.industry }}</span>
            </p>
            <div class="mt-3 space-y-1">
              <div v-for="m in (s.messages || []).slice(0, 3)" :key="m.order" class="text-xs text-slate-400">
                <span class="text-slate-500 mr-1">{{ m.order }}.</span>
                {{ (m.content || '').substring(0, 50) }}{{ (m.content || '').length > 50 ? '...' : '' }}
                <span class="text-slate-600 ml-1">({{ m.delay_ms || 0 }}ms)</span>
              </div>
            </div>
          </div>
          <div class="flex gap-2">
            <button @click="openEdit(s)" class="text-sm text-sky-400 hover:text-sky-300 cursor-pointer px-2 py-1 rounded hover:bg-white/5 transition">编辑</button>
            <button @click="handleDelete(s)" class="text-sm text-red-400 hover:text-red-300 cursor-pointer px-2 py-1 rounded hover:bg-white/5 transition">删除</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Editor Dialog -->
    <div v-if="showEditor" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="showEditor = false">
      <div class="bg-slate-800 rounded-xl shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto p-6 border border-slate-700">
        <h2 class="text-lg font-bold text-white mb-4">{{ editingId ? '编辑模板' : '新建模板' }}</h2>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-1">模板名称</label>
            <input v-model="form.name" maxlength="100" class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-sky-500" placeholder="如：健康行业标准话术" />
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-1">行业标签（可选）</label>
            <input v-model="form.industry" maxlength="50" class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-sky-500" placeholder="如：健康" />
          </div>

          <div>
            <div class="flex justify-between items-center mb-2">
              <label class="text-sm font-medium text-slate-300">消息序列 ({{ form.messages.length }}/10)</label>
              <button @click="addMessage" v-if="form.messages.length < 10" class="text-xs text-sky-400 hover:text-sky-300 cursor-pointer">+ 添加消息</button>
            </div>
            <div class="space-y-3">
              <div v-for="(msg, idx) in form.messages" :key="idx" class="flex gap-2 items-start p-3 rounded-lg border border-white/5 bg-white/[0.03]">
                <div class="flex flex-col gap-1 text-slate-500 text-xs pt-2">
                  <button @click="moveUp(idx)" :disabled="idx === 0" class="hover:text-white disabled:opacity-30 disabled:cursor-default cursor-pointer">&#9650;</button>
                  <span class="text-center">{{ msg.order }}</span>
                  <button @click="moveDown(idx)" :disabled="idx >= form.messages.length - 1" class="hover:text-white disabled:opacity-30 disabled:cursor-default cursor-pointer">&#9660;</button>
                </div>
                <div class="flex-1">
                  <textarea v-model="msg.content" rows="2" maxlength="500" class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-sky-500" placeholder="私信内容，支持 {{keyword}} 变量" /></textarea>
                </div>
                <div class="flex flex-col gap-1 items-end">
                  <input v-model.number="msg.delay_ms" type="number" min="0" max="60000" step="500" class="w-20 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white text-xs text-center focus:outline-none focus:border-sky-500" title="本条发送后额外等待（毫秒）" />
                  <span class="text-xs text-slate-500">{{ msg.delay_ms || 0 }}ms</span>
                  <button @click="removeMessage(idx)" class="text-xs text-red-400 hover:text-red-300 cursor-pointer">删除</button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-3 mt-6">
          <button @click="showEditor = false" class="px-4 py-2 text-slate-400 hover:text-white transition cursor-pointer">取消</button>
          <button @click="handleSave" class="px-4 py-2 bg-sky-500 text-white rounded-lg hover:bg-sky-400 transition cursor-pointer">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>
