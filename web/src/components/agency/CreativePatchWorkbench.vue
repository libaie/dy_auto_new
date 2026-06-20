<template>
  <section class="space-y-4" data-test="creative-patch-workbench">
    <div class="rounded-lg border border-white/10 bg-zinc-900/90 p-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div class="inline-flex rounded border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-1 text-xs font-medium text-cyan-100">
            短视频导演台
          </div>
          <h1 class="mt-3 text-xl font-semibold text-white">创作补丁</h1>
        </div>
        <span v-if="summary.blocking" class="rounded border border-amber-300/30 bg-amber-300/10 px-2 py-1 text-xs text-amber-100">
          待处理 {{ summary.blocking }}
        </span>
      </div>
    </div>

    <CreativePatchSummaryStrip :summary="summary" />

    <div v-if="loading" class="rounded-lg border border-white/10 bg-zinc-900/80 p-4 text-sm text-zinc-400">
      正在加载创作补丁...
    </div>
    <div v-else-if="error" class="rounded-lg border border-rose-500/40 bg-rose-950/40 p-4 text-sm text-rose-100">
      {{ error }}
    </div>
    <div v-else class="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
      <CreativePatchList
        :patches="patches"
        :selected-id="selectedPatch?.id || ''"
        @select="selectPatch"
      />
      <div class="min-w-0 space-y-3">
        <CreativePatchDiff
          v-if="selectedPatch"
          :patch="selectedPatch"
          :after="editableAfter"
          @update:after="editableAfter = $event"
        />
        <div v-else class="rounded-lg border border-white/10 bg-zinc-900/80 p-4 text-sm text-zinc-400">
          选择一个补丁查看改稿。
        </div>
        <CreativePatchActions
          v-if="selectedPatch"
          :disabled="busy"
          :source-invocation-id="selectedPatch.source_invocation_id || ''"
          @save="emitSave"
          @approve="$emit('approve', selectedPatch)"
          @apply="$emit('apply', selectedPatch)"
          @reject="$emit('reject', selectedPatch)"
          @open-invocation="$emit('open-invocation', selectedPatch)"
        />
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import CreativePatchActions from './CreativePatchActions.vue'
import CreativePatchDiff from './CreativePatchDiff.vue'
import CreativePatchList from './CreativePatchList.vue'
import CreativePatchSummaryStrip from './CreativePatchSummaryStrip.vue'

const props = defineProps({
  patches: { type: Array, default: () => [] },
  summary: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  busyId: { type: String, default: '' },
})

const emit = defineEmits(['save', 'approve', 'reject', 'apply', 'open-invocation'])

const selectedId = ref('')
const editableAfter = ref({})

const selectedPatch = computed(() => (
  props.patches.find(patch => patch.id === selectedId.value) || props.patches[0] || null
))
const busy = computed(() => Boolean(props.busyId && selectedPatch.value?.id === props.busyId))

watch(
  () => props.patches.map(patch => patch.id).join('|'),
  () => {
    if (!props.patches.some(patch => patch.id === selectedId.value)) {
      selectedId.value = props.patches[0]?.id || ''
    }
  },
  { immediate: true },
)

watch(
  () => selectedPatch.value?.id,
  () => {
    editableAfter.value = { ...(selectedPatch.value?.after || {}) }
  },
  { immediate: true },
)

function selectPatch(patch) {
  selectedId.value = patch.id
}

function emitSave() {
  if (!selectedPatch.value) return
  emit('save', { ...selectedPatch.value, after: { ...editableAfter.value } })
}
</script>
