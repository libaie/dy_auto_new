<script setup>
import { reactive, ref, watch } from 'vue'

import EmptyState from '../EmptyState.vue'
import AppButton from '../ui/AppButton.vue'

const props = defineProps({
  title: { type: String, default: '参考图' },
  slots: { type: Array, default: () => [] },
  loadingSlot: { type: String, default: '' },
})

const emit = defineEmits(['regenerate', 'replace-url'])

const editing = reactive({})
const previewSlot = ref(null)

const MANAGED_IMAGE_PREFIXES = ['/static/', '/api/image-creation/pixelle-files/']
const LOOPBACK_HOSTS = new Set(['127.0.0.1', 'localhost', '[::1]', '::1'])

function clearEditing() {
  Object.keys(editing).forEach((key) => {
    delete editing[key]
  })
}

watch(
  () => props.slots,
  () => {
    clearEditing()
    previewSlot.value = null
  },
  { deep: true },
)

function startEdit(slot) {
  editing[slot.key] = slot.url || ''
}

function cancelEdit(slotKey) {
  delete editing[slotKey]
}

function saveUrl(slotKey) {
  emit('replace-url', slotKey, (editing[slotKey] || '').trim())
  delete editing[slotKey]
}

function regenerateAll() {
  props.slots.forEach((slot) => emit('regenerate', slot.key))
}

async function copyUrl(url) {
  if (!url) return
  await navigator.clipboard?.writeText(url)
}

function isManagedPath(path) {
  return MANAGED_IMAGE_PREFIXES.some((prefix) => String(path || '').startsWith(prefix))
}

function normalizeImageUrl(url) {
  const clean = String(url || '').trim()
  if (!clean) return ''
  if (isManagedPath(clean)) return clean
  try {
    const parsed = new URL(clean, window.location.origin)
    if (isManagedPath(parsed.pathname) && (parsed.origin === window.location.origin || LOOPBACK_HOSTS.has(parsed.hostname))) {
      return `${parsed.pathname}${parsed.search}${parsed.hash}`
    }
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return clean
    }
  } catch {
    return ''
  }
  return ''
}

function tosSignedUrlExpired(url) {
  const clean = String(url || '').trim()
  if (!clean) return false
  let parsed
  try {
    parsed = new URL(clean, window.location.origin)
  } catch {
    return false
  }
  const date = parsed.searchParams.get('X-Tos-Date') || parsed.searchParams.get('x-tos-date')
  const expires = Number(parsed.searchParams.get('X-Tos-Expires') || parsed.searchParams.get('x-tos-expires'))
  const match = String(date || '').match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/)
  if (!match || !Number.isFinite(expires)) return false
  const [, year, month, day, hour, minute, second] = match
  const issuedAt = Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second))
  return Date.now() >= issuedAt + expires * 1000
}

function slotImageSrc(slot) {
  if (!slot?.url || tosSignedUrlExpired(slot.url)) return ''
  return normalizeImageUrl(slot.url)
}

function slotProgress(slot) {
  return slot?.progress || {}
}

function slotStatusText(slot) {
  const progress = slotProgress(slot)
  if (progress.status === 'generating') return '风格锁定生成中'
  if (progress.status === 'pending') return '等待风格锁定生成'
  if (progress.status === 'failed') return '生成失败'
  if (progress.status === 'ready' && progress.source === 'style_lock') return '风格锁定已生成'
  if (!slot?.url) return '待生成'
  if (tosSignedUrlExpired(slot.url)) return '链接已过期'
  return '已配置'
}

function progressClass(slot) {
  const status = slotProgress(slot).status
  if (status === 'generating') return 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200'
  if (status === 'failed') return 'border-red-500/30 bg-red-500/10 text-red-200'
  if (status === 'ready') return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
  return 'border-slate-700 bg-slate-800/60 text-slate-300'
}

function openOriginal(slot) {
  const src = slotImageSrc(slot)
  if (!src) return
  previewSlot.value = { ...slot, src }
}

function closeOriginal() {
  previewSlot.value = null
}
</script>

<template>
  <section class="space-y-3">
    <div class="flex items-center justify-between gap-3">
      <h3 class="text-sm font-semibold text-slate-100">{{ title }}</h3>
      <AppButton
        data-test="regenerate-all"
        type="button"
        variant="secondary"
        size="sm"
        :disabled="slots.length === 0"
        @click="regenerateAll"
      >
        全部重新生成
      </AppButton>
    </div>

    <EmptyState v-if="slots.length === 0" message="暂无参考图槽位" />

    <div v-else class="grid gap-3 sm:grid-cols-2">
      <article
        v-for="slot in slots"
        :key="slot.key"
        class="rounded-lg border border-slate-800 bg-slate-900/70 p-3"
      >
        <div class="mb-2 flex items-center justify-between gap-2">
          <div class="min-w-0">
            <p class="truncate text-sm font-medium text-slate-100">{{ slot.label }}</p>
            <p class="text-xs" :class="tosSignedUrlExpired(slot.url) ? 'text-amber-300' : 'text-slate-500'">
              {{ slotStatusText(slot) }}
            </p>
            <p
              v-if="slot.progress?.status"
              :data-test="`progress-${slot.key}`"
              class="mt-1 inline-flex max-w-full rounded border px-2 py-0.5 text-xs"
              :class="progressClass(slot)"
            >
              {{ slotStatusText(slot) }}
            </p>
            <p v-if="slot.progress?.error" class="mt-1 truncate text-xs text-red-300">
              {{ slot.progress.error }}
            </p>
          </div>
          <span
            v-if="loadingSlot === slot.key"
            class="rounded border border-cyan-500/30 px-2 py-1 text-xs text-cyan-200"
          >
            生成中
          </span>
        </div>

        <div class="mb-3 overflow-hidden rounded-md border border-slate-800 bg-slate-950">
          <button
            v-if="slotImageSrc(slot)"
            :data-test="`open-original-${slot.key}`"
            type="button"
            class="group relative block w-full text-left"
            @click="openOriginal(slot)"
          >
            <img
              :data-test="`preview-image-${slot.key}`"
              :src="slotImageSrc(slot)"
              :alt="`${slot.label}参考图`"
              class="h-36 w-full object-cover transition duration-200 group-hover:scale-[1.02]"
              loading="lazy"
            >
            <span class="absolute bottom-2 right-2 rounded bg-slate-950/80 px-2 py-1 text-xs text-slate-100 opacity-0 transition group-hover:opacity-100">
              查看原图
            </span>
          </button>
          <div v-else class="flex h-36 flex-col items-center justify-center gap-1 px-3 text-center text-sm text-slate-500">
            <span>{{ slot.url ? '链接已过期，请重新生成' : '待生成' }}</span>
          </div>
        </div>

        <div class="space-y-2">
          <label
            class="block text-xs font-medium text-slate-300"
            :for="`reference-url-${slot.key}`"
          >
            {{ slot.label }}链接
          </label>
          <input
            :id="`reference-url-${slot.key}`"
            :data-test="`url-input-${slot.key}`"
            :value="editing[slot.key] ?? slot.url ?? ''"
            class="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600"
            placeholder="粘贴图片 URL"
            @input="editing[slot.key] = $event.target.value"
          >
        </div>

        <div class="mt-3 flex flex-wrap gap-2">
          <AppButton
            :data-test="`regenerate-${slot.key}`"
            type="button"
            variant="secondary"
            size="sm"
            :loading="loadingSlot === slot.key"
            @click="emit('regenerate', slot.key)"
          >
            重新生成
          </AppButton>
          <AppButton
            :data-test="`copy-${slot.key}`"
            type="button"
            variant="ghost"
            size="sm"
            :disabled="!slot.url"
            @click="copyUrl(slot.url)"
          >
            复制链接
          </AppButton>
          <AppButton
            v-if="editing[slot.key] === undefined"
            :data-test="`edit-${slot.key}`"
            type="button"
            variant="ghost"
            size="sm"
            @click="startEdit(slot)"
          >
            替换链接
          </AppButton>
          <template v-else>
            <AppButton
              :data-test="`save-url-${slot.key}`"
              type="button"
              variant="success"
              size="sm"
              @click="saveUrl(slot.key)"
            >
              保存链接
            </AppButton>
            <AppButton
              :data-test="`cancel-url-${slot.key}`"
              type="button"
              variant="ghost"
              size="sm"
              @click="cancelEdit(slot.key)"
            >
              取消
            </AppButton>
          </template>
        </div>
      </article>
    </div>

    <div
      v-if="previewSlot"
      data-test="reference-original-modal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4"
      @click.self="closeOriginal"
    >
      <div class="w-full max-w-5xl rounded-lg border border-slate-700 bg-slate-900 p-4 shadow-2xl">
        <div class="mb-3 flex items-center justify-between gap-3">
          <div class="min-w-0">
            <p class="text-sm font-semibold text-slate-100">{{ previewSlot.label }}原图</p>
            <p class="mt-1 break-all text-xs text-slate-500">{{ previewSlot.url }}</p>
          </div>
          <AppButton data-test="close-original" type="button" variant="ghost" size="sm" @click="closeOriginal">
            关闭
          </AppButton>
        </div>
        <img
          data-test="reference-original-image"
          :src="previewSlot.src"
          :alt="`${previewSlot.label}原图`"
          class="max-h-[75vh] w-full rounded-md bg-slate-950 object-contain"
        >
      </div>
    </div>
  </section>
</template>
