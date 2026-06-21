<!-- 专家团队业务组件：展示或操作专家团队、审查、返修和创意补丁相关业务状态。 -->
<template>
  <section class="relative -mx-4 -mb-5 overflow-hidden border-y border-white/10 bg-black text-white md:-mx-6">
    <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(34,211,238,0.16),transparent_34%),linear-gradient(180deg,#09090b_0%,#030712_100%)]"></div>

    <div v-if="!canRender3d" class="relative z-10 flex flex-wrap items-start justify-between gap-3 px-4 py-4 md:px-6">
      <div>
        <div class="text-xs font-medium text-cyan-200">人物化专家可视化</div>
        <h2 class="mt-1 text-2xl font-semibold text-white">动漫制作工作室</h2>
        <div class="mt-2 inline-flex rounded border border-cyan-300/30 bg-cyan-300/10 px-2 py-1 text-xs text-cyan-100">3D 专家人物化</div>
        <p class="mt-2 max-w-3xl text-sm leading-6 text-zinc-300">这是一个剖面专家工作室，专家会在房间里随机走动，在分镜区、图像区、视频区、质检区与输出门之间完成协作；活跃阶段会亮起，点击人物查看完整专家档案。</p>
      </div>
      <button
        type="button"
        class="rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-cyan-100 hover:border-cyan-400/60 hover:text-white"
        @click="staticMode = !staticMode"
      >
        {{ staticMode ? '切换动态模式' : '切换静态模式' }}
      </button>
    </div>

    <div v-if="!canRender3d" class="relative z-10 mx-4 mb-6 rounded-md border border-white/10 bg-zinc-950/70 p-4 md:mx-6">
      <p class="text-sm text-amber-100">{{ fallbackReason }}</p>
      <div class="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        <button
          v-for="expert in visibleExperts"
          :key="expert.expert_id"
          :data-expert-id="expert.expert_id"
          type="button"
          class="rounded-md border border-white/10 bg-zinc-900/80 p-3 text-left hover:border-cyan-400/60"
          @click="$emit('select', expert.expert_id)"
        >
          <div class="font-medium text-zinc-100">{{ expertName(expert.expert_id, expert.name) }}</div>
          <div class="mt-1 text-xs leading-5 text-zinc-300">{{ roleText(expert) }}</div>
          <div class="text-xs leading-5 text-zinc-400">{{ phaseText(expert.phases || []) }}</div>
          <div class="mt-2 text-xs leading-5 text-zinc-500">{{ skillText(expert) }}</div>
        </button>
      </div>
    </div>

    <div v-else data-test="anime-studio-stage" class="relative z-10 h-[calc(100dvh-112px)] min-h-[640px] w-full overflow-hidden bg-zinc-950">
      <canvas
        ref="canvasEl"
        class="h-full w-full bg-zinc-950"
        aria-label="动漫专家团队三维地图"
      ></canvas>

      <div class="pointer-events-none absolute left-4 top-4 max-w-md rounded-md border border-white/10 bg-zinc-950/62 p-3 shadow-2xl backdrop-blur">
        <div class="text-xs font-medium text-cyan-200">人物化专家可视化</div>
        <h2 class="mt-1 text-xl font-semibold text-white">动漫制作工作室</h2>
        <div class="mt-2 inline-flex rounded border border-cyan-300/30 bg-cyan-300/10 px-2 py-1 text-xs text-cyan-100">3D 专家人物化</div>
        <p class="mt-2 text-xs leading-5 text-zinc-300">这是一个剖面专家工作室，专家会在房间里随机走动，在分镜区、图像区、视频区、质检区与输出门之间完成协作。</p>
        <div class="mt-3 grid gap-1.5 text-[11px] leading-4 text-zinc-300 sm:grid-cols-3">
          <div class="rounded border border-amber-300/30 bg-amber-300/10 px-2 py-1">
            <span class="font-semibold text-amber-100">亮起</span> 当前阶段正在参与
          </div>
          <div class="rounded border border-white/10 bg-white/5 px-2 py-1">
            <span class="font-semibold text-zinc-100">待命</span> 属于当前专家团队
          </div>
          <div class="rounded border border-violet-300/30 bg-violet-400/10 px-2 py-1">
            <span class="font-semibold text-violet-100">历史</span> 不在 3D 当前团队中展示
          </div>
        </div>
      </div>

      <button
        type="button"
        class="absolute right-4 top-4 z-20 rounded-md border border-white/10 bg-zinc-950/62 px-3 py-2 text-sm text-cyan-100 shadow-lg backdrop-blur hover:border-cyan-400/60 hover:text-white"
        @click="staticMode = !staticMode"
      >
        {{ staticMode ? '切换动态模式' : '切换静态模式' }}
      </button>

      <div class="pointer-events-none absolute bottom-4 left-4 right-4 grid gap-2 sm:grid-cols-3 lg:left-5 lg:right-auto lg:w-[33rem] lg:grid-cols-5">
        <div
          v-for="zone in STUDIO_ZONES"
          :key="zone.label"
          class="rounded-md border bg-zinc-950/58 px-2.5 py-2 shadow-lg backdrop-blur"
          :class="activeZoneKeys.has(zone.key) ? zone.activeClass : 'border-white/10 text-zinc-300'"
        >
          <div class="text-[11px] font-semibold">{{ zone.label }}</div>
          <div class="mt-1 text-[10px] leading-4 text-zinc-400">{{ zone.hint }}</div>
        </div>
      </div>

      <div class="sr-only" aria-live="polite">
        3D 人物头顶显示专家姓名，点击人物模型可打开专家档案。
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  expertName as knownExpertName,
  isLegacyExpert,
  phaseText as knownPhaseText,
  roleLabel,
  safeDisplayText,
  skillText as knownSkillText,
} from './agencyExpertLabels.js'

const emit = defineEmits(['select'])

const props = defineProps({
  experts: { type: Array, default: () => [] },
  stageGraph: { type: Array, default: () => [] },
  invocations: { type: Array, default: () => [] },
  webglAvailable: { type: Boolean, default: true },
})

const canvasEl = ref(null)
const viewportWidth = ref(typeof window === 'undefined' ? 0 : window.innerWidth)
const contextUnavailable = ref(false)
const staticMode = ref(typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)

let renderer = null
let scene = null
let camera = null
let frameId = 0
let resizeHandler = null
let canvasClickHandler = null
let canvasClickTarget = null
let renderToken = 0
let unmounted = false

const canRender3d = computed(() => (
  props.webglAvailable &&
  !contextUnavailable.value &&
  viewportWidth.value >= 768
))

const visibleExperts = computed(() => (
  props.experts.filter(expert => expert?.expert_id && !expert.legacy && !isLegacyExpert(expert.expert_id))
))

const fallbackReason = computed(() => {
  if (!props.webglAvailable || contextUnavailable.value) return '已切换到 2D 专家协作图，当前环境无法使用三维渲染。'
  if (viewportWidth.value < 768) return '已切换到 2D 专家协作图，窄屏设备优先显示卡片列表。'
  return '已切换到 2D 专家协作图。'
})

const expertSignature = computed(() => visibleExperts.value.map(expert => [
  expert.expert_id || '',
  expert.name || '',
  expert.role_type || '',
  (expert.phases || []).join(','),
].join(':')).join('|'))

const invocationStatusSignature = computed(() => props.invocations.map(item => [
  item.id || '',
  item.expert_id || '',
  item.role || '',
  item.execution_status || '',
  item.result_status || '',
].join(':')).sort().join('|'))

const stageGraphSignature = computed(() => props.stageGraph.map(stage => [
  stage.stage || '',
  stage.status || '',
  normalizeExpertIds(stage.lead).join(','),
  normalizeExpertIds(stage.reviewers).join(','),
  normalizeExpertIds(stage.qa).join(','),
  normalizeExpertIds(stage.expert_ids).join(','),
  normalizeStageInvocationIds(stage).join(','),
  normalizeStageInvocationSummaries(stage).map(summary => [
    normalizeExpertIds(summary.expert_id || summary.expert_ids).join(','),
    summary.execution_status || '',
    summary.result_status || '',
    summary.status || '',
  ].join(':')).join(','),
].join(':')).sort().join('|'))

const invocationExpertIdsById = computed(() => new Map(
  props.invocations
    .filter(item => item.id && item.expert_id)
    .map(item => [item.id, item.expert_id])
))

const activeExpertIds = computed(() => {
  const ids = new Set(
    props.invocations
      .filter(isActiveInvocation)
      .map(item => item.expert_id)
      .filter(id => id && !isLegacyExpert(id))
      .filter(Boolean)
  )

  stageActiveExpertIds.value.forEach(id => ids.add(id))
  return ids
})

const stageActiveExpertIds = computed(() => {
  const ids = new Set()

  props.stageGraph
    .filter(stage => isAttentionStage(stage.status))
    .forEach(stage => {
      if (normalizeStageStatus(stage.status) !== 'pending') {
        addExpertIds(ids, stage.lead)
        addExpertIds(ids, stage.reviewers)
        addExpertIds(ids, stage.qa)
        addExpertIds(ids, stage.expert_ids)
      }

      normalizeStageInvocationIds(stage).forEach(invocationId => {
        addExpertIds(ids, invocationExpertIdsById.value.get(invocationId))
      })

      normalizeStageInvocationSummaries(stage).forEach(summary => {
        addExpertIds(ids, summary.expert_id)
        addExpertIds(ids, summary.expert_ids)
      })
    })

  return ids
})

const STUDIO_ZONES = [
  { key: 'storyboard', label: '分镜区', hint: '脚本、节奏、镜头', activeClass: 'border-cyan-300/50 text-cyan-100 bg-cyan-500/15' },
  { key: 'image_stage', label: '图像区', hint: '角色、场景、参考图', activeClass: 'border-violet-300/50 text-violet-100 bg-violet-500/15' },
  { key: 'video_stage', label: '视频区', hint: '镜头生成与延展', activeClass: 'border-amber-300/50 text-amber-100 bg-amber-500/15' },
  { key: 'video_review', label: '质检区', hint: '一致性与风险审查', activeClass: 'border-emerald-300/50 text-emerald-100 bg-emerald-500/15' },
  { key: 'compose', label: '输出门', hint: '合成、包装、入库', activeClass: 'border-rose-300/50 text-rose-100 bg-rose-500/15' },
]

const COLORS = ['#f87171', '#fb923c', '#facc15', '#4ade80', '#2dd4bf', '#38bdf8', '#818cf8', '#c084fc', '#f472b6']
const STUDIO_WAYPOINTS = [
  { x: -3.45, z: -0.92 },
  { x: -2.16, z: -1.78 },
  { x: 0.05, z: -1.74 },
  { x: 2.58, z: -1.42 },
  { x: 4.12, z: -0.12 },
  { x: 3.84, z: 1.24 },
  { x: 1.42, z: 1.58 },
  { x: -0.2, z: 1.66 },
  { x: -2.56, z: 1.45 },
  { x: -4.18, z: 0.08 },
]
const STUDIO_WALK_LINKS = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 4],
  [4, 5],
  [5, 6],
  [6, 7],
  [7, 8],
  [8, 9],
  [9, 0],
  [0, 8],
  [3, 6],
]
const STUDIO_OBSTACLES = [
  { xMin: -1.72, xMax: 1.32, zMin: -0.52, zMax: 1.02 },
  { xMin: -4.54, xMax: -2.86, zMin: -2.92, zMax: -1.86 },
  { xMin: -1.98, xMax: -0.32, zMin: -3.38, zMax: -2.32 },
  { xMin: 0.54, xMax: 2.24, zMin: -3.24, zMax: -2.18 },
  { xMin: 3.02, xMax: 4.68, zMin: -1.86, zMax: -0.84 },
  { xMin: 1.86, xMax: 3.54, zMin: 1.82, zMax: 2.92 },
  { xMin: 4.26, xMax: 5.26, zMin: 1.32, zMax: 2.76 },
]

const activeZoneKeys = computed(() => {
  const keys = new Set()
  props.stageGraph
    .filter(stage => isAttentionStage(stage.status))
    .forEach(stage => {
      const normalized = normalizeZoneKey(stage.stage)
      if (normalized) keys.add(normalized)
    })
  if (!keys.size && props.stageGraph.length) {
    const firstStage = props.stageGraph.find(stage => normalizeZoneKey(stage.stage))
    if (firstStage) keys.add(normalizeZoneKey(firstStage.stage))
  }
  return keys
})

// 前端业务函数：协调 expertName 对应的页面流程、接口调用或状态转换。
function expertName(id, fallback = '') {
  return knownExpertName(id, fallback)
}

// 前端业务函数：协调 phaseText 对应的页面流程、接口调用或状态转换。
function phaseText(phases) {
  return knownPhaseText(phases)
}

// 前端业务函数：协调 skillText 对应的页面流程、接口调用或状态转换。
function skillText(expert) {
  return knownSkillText(expert)
}

// 前端业务函数：协调 normalizeRoleLabels 对应的页面流程、接口调用或状态转换。
function normalizeRoleLabels(value) {
  if (!value) return []
  if (Array.isArray(value)) return value.flatMap(normalizeRoleLabels)
  if (typeof value === 'object') {
    return normalizeRoleLabels(value.role_type || value.role || value.type)
  }
  const key = String(value).trim().toLowerCase()
  const label = roleLabel(key)
  return label ? [label] : []
}

// 前端业务函数：协调 addRoleLabels 对应的页面流程、接口调用或状态转换。
function addRoleLabels(labels, value) {
  normalizeRoleLabels(value).forEach(label => labels.add(label))
}

// 前端业务函数：协调 roleText 对应的页面流程、接口调用或状态转换。
function roleText(expert) {
  const expertId = expert.expert_id
  const labels = new Set()
  addRoleLabels(labels, expert.role_type)

  props.invocations
    .filter(invocation => invocation.expert_id === expertId)
    .forEach(invocation => addRoleLabels(labels, invocation.role))

  props.stageGraph.forEach(stage => {
    if (normalizeExpertIds(stage.lead).includes(expertId)) addRoleLabels(labels, 'lead')
    if (normalizeExpertIds(stage.reviewers).includes(expertId)) addRoleLabels(labels, 'reviewer')
    if (normalizeExpertIds(stage.qa).includes(expertId)) addRoleLabels(labels, 'qa')
  })

  return `职责：${labels.size ? Array.from(labels).join(' / ') : '协作专家'}`
}

function isActiveInvocation(item) {
  return ['running', 'pending'].includes(item.execution_status) || ['running', 'pending'].includes(item.result_status)
}

// 前端业务函数：协调 isAttentionStage 对应的页面流程、接口调用或状态转换。
function isAttentionStage(status) {
  return [
    'blocked',
    'failed',
    'failure',
    'in_progress',
    'pending',
    'queued',
    'retrying',
    'running',
    'warning',
  ].includes(normalizeStageStatus(status))
}

// 前端业务函数：协调 normalizeStageStatus 对应的页面流程、接口调用或状态转换。
function normalizeStageStatus(status) {
  return String(status || '').toLowerCase()
}

// 前端业务函数：协调 normalizeExpertIds 对应的页面流程、接口调用或状态转换。
function normalizeExpertIds(value) {
  if (!value) return []
  if (Array.isArray(value)) return value.flatMap(normalizeExpertIds)
  if (typeof value === 'object') {
    return normalizeExpertIds(value.expert_id || value.expert_ids || value.id)
  }
  return [String(value)].filter(Boolean)
}

// 前端业务函数：协调 addExpertIds 对应的页面流程、接口调用或状态转换。
function addExpertIds(ids, value) {
  normalizeExpertIds(value)
    .filter(id => !isLegacyExpert(id))
    .forEach(id => ids.add(id))
}

// 前端业务函数：协调 normalizeStageInvocationIds 对应的页面流程、接口调用或状态转换。
function normalizeStageInvocationIds(stage) {
  return [
    ...(stage.invocation_ids || []),
    ...(stage.invocationIds || []),
  ].filter(Boolean)
}

// 前端业务函数：协调 normalizeStageInvocationSummaries 对应的页面流程、接口调用或状态转换。
function normalizeStageInvocationSummaries(stage) {
  return [
    ...(stage.invocation_summaries || []),
    ...(stage.invocationSummaries || []),
    ...(stage.invocations || []),
    ...(stage.summaries || []),
  ].filter(Boolean)
}

// 前端业务函数：协调 isExpertActive 对应的页面流程、接口调用或状态转换。
function isExpertActive(expertId) {
  return activeExpertIds.value.has(expertId)
}

// 前端业务函数：协调 normalizeZoneKey 对应的页面流程、接口调用或状态转换。
function normalizeZoneKey(stage) {
  if (['storyboard', 'style_lock'].includes(stage)) return 'storyboard'
  if (['image_stage', 'render'].includes(stage)) return 'image_stage'
  if (['video_stage'].includes(stage)) return 'video_stage'
  if (['image_review', 'video_review'].includes(stage)) return 'video_review'
  if (['compose', 'final_edit'].includes(stage)) return 'compose'
  return ''
}

// 前端业务函数：协调 selectExpert 对应的页面流程、接口调用或状态转换。
function selectExpert(expertId) {
  emit('select', expertId)
}

// 前端业务函数：协调 updateViewport 对应的页面流程、接口调用或状态转换。
function updateViewport() {
  viewportWidth.value = window.innerWidth
}

// 前端业务函数：协调 hasWebglContext 对应的页面流程、接口调用或状态转换。
function hasWebglContext() {
  if (typeof window.WebGLRenderingContext === 'undefined') return false
  try {
    const probe = document.createElement('canvas')
    const context = probe.getContext('webgl2') || probe.getContext('webgl') || probe.getContext('experimental-webgl')
    return Boolean(context)
  } catch {
    return false
  }
}

// 前端业务函数：协调 disposeMaterialTextures 对应的页面流程、接口调用或状态转换。
function disposeMaterialTextures(material, disposedTextures) {
  Object.values(material).forEach(value => {
    if (Array.isArray(value)) {
      value.forEach(item => {
        if (item?.isTexture && !disposedTextures.has(item)) {
          item.dispose?.()
          disposedTextures.add(item)
        }
      })
      return
    }
    if (value?.isTexture && !disposedTextures.has(value)) {
      value.dispose?.()
      disposedTextures.add(value)
    }
  })
}

// 前端业务函数：协调 disposeSceneGraph 对应的页面流程、接口调用或状态转换。
function disposeSceneGraph(currentScene) {
  if (!currentScene?.traverse) return
  const disposedTextures = new Set()
  currentScene.traverse(object => {
    if (!object?.isMesh && !object?.isSprite) return
    object.geometry?.dispose?.()
    const materials = Array.isArray(object.material) ? object.material : [object.material]
    materials.filter(Boolean).forEach(material => {
      disposeMaterialTextures(material, disposedTextures)
      material.dispose?.()
    })
  })
}

// 前端业务函数：协调 stopScene 对应的页面流程、接口调用或状态转换。
function stopScene() {
  if (frameId) cancelAnimationFrame(frameId)
  frameId = 0
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  resizeHandler = null
  if (canvasClickHandler && canvasClickTarget) {
    canvasClickTarget.removeEventListener('click', canvasClickHandler)
  }
  canvasClickHandler = null
  canvasClickTarget = null
  disposeSceneGraph(scene)
  renderer?.dispose()
  renderer = null
  scene = null
  camera = null
}

// 前端业务函数：协调 resizeRenderer 对应的页面流程、接口调用或状态转换。
function resizeRenderer() {
  if (!renderer || !camera || !canvasEl.value) return
  const canvas = canvasEl.value
  const width = Math.max(canvas.clientWidth, 1)
  const height = Math.max(canvas.clientHeight, 1)
  renderer.setSize(width, height, false)
  camera.aspect = width / height
  camera.updateProjectionMatrix()
}

// 前端业务函数：协调 createMaterial 对应的页面流程、接口调用或状态转换。
function createMaterial(THREE, color, options = {}) {
  const materialOptions = {
    color,
    roughness: options.roughness ?? 0.72,
    metalness: options.metalness ?? 0,
    flatShading: options.flatShading ?? true,
  }
  if (options.emissive) materialOptions.emissive = options.emissive
  if (options.emissiveIntensity !== undefined) materialOptions.emissiveIntensity = options.emissiveIntensity
  if (options.transparent !== undefined) materialOptions.transparent = options.transparent
  if (options.opacity !== undefined) materialOptions.opacity = options.opacity
  return new THREE.MeshStandardMaterial(materialOptions)
}

// 前端业务函数：协调 addBox 对应的页面流程、接口调用或状态转换。
function addBox(THREE, target, size, position, color, options = {}) {
  const material = createMaterial(THREE, color, options)
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(size[0], size[1], size[2]), material)
  mesh.position.set(position[0], position[1], position[2])
  if (options.rotation) {
    mesh.rotation.x = options.rotation[0] || 0
    mesh.rotation.y = options.rotation[1] || 0
    mesh.rotation.z = options.rotation[2] || 0
  }
  if (options.name) mesh.name = options.name
  if (options.userData) mesh.userData = { ...mesh.userData, ...options.userData }
  target.add(mesh)
  return mesh
}

// 前端业务函数：协调 addSphere 对应的页面流程、接口调用或状态转换。
function addSphere(THREE, target, radius, position, color, options = {}) {
  const mesh = new THREE.Mesh(
    new THREE.SphereGeometry(radius, options.widthSegments || 18, options.heightSegments || 12),
    createMaterial(THREE, color, options)
  )
  mesh.position.set(position[0], position[1], position[2])
  if (options.scale) mesh.scale.set(options.scale[0], options.scale[1], options.scale[2])
  target.add(mesh)
  return mesh
}

// 前端业务函数：协调 addCapsule 对应的页面流程、接口调用或状态转换。
function addCapsule(THREE, target, radius, length, position, color, options = {}) {
  const mesh = new THREE.Mesh(
    new THREE.CapsuleGeometry(radius, length, options.capSegments || 5, options.radialSegments || 12),
    createMaterial(THREE, color, options)
  )
  mesh.position.set(position[0], position[1], position[2])
  if (options.rotation) {
    mesh.rotation.x = options.rotation[0] || 0
    mesh.rotation.y = options.rotation[1] || 0
    mesh.rotation.z = options.rotation[2] || 0
  }
  target.add(mesh)
  return mesh
}

// 前端业务函数：协调 addCone 对应的页面流程、接口调用或状态转换。
function addCone(THREE, target, radius, height, position, color, options = {}) {
  const mesh = new THREE.Mesh(
    new THREE.ConeGeometry(radius, height, options.radialSegments || 16),
    createMaterial(THREE, color, options)
  )
  mesh.position.set(position[0], position[1], position[2])
  if (options.rotation) {
    mesh.rotation.x = options.rotation[0] || 0
    mesh.rotation.y = options.rotation[1] || 0
    mesh.rotation.z = options.rotation[2] || 0
  }
  target.add(mesh)
  return mesh
}

// 前端业务函数：协调 addTorus 对应的页面流程、接口调用或状态转换。
function addTorus(THREE, target, radius, tube, position, color, options = {}) {
  const mesh = new THREE.Mesh(
    new THREE.TorusGeometry(radius, tube, options.radialSegments || 8, options.tubularSegments || 32),
    createMaterial(THREE, color, options)
  )
  mesh.position.set(position[0], position[1], position[2])
  if (options.rotation) {
    mesh.rotation.x = options.rotation[0] || 0
    mesh.rotation.y = options.rotation[1] || 0
    mesh.rotation.z = options.rotation[2] || 0
  }
  target.add(mesh)
  return mesh
}

// 前端业务函数：协调 drawRoundedRect 对应的页面流程、接口调用或状态转换。
function drawRoundedRect(ctx, x, y, width, height, radius) {
  ctx.beginPath()
  ctx.moveTo(x + radius, y)
  ctx.lineTo(x + width - radius, y)
  ctx.quadraticCurveTo(x + width, y, x + width, y + radius)
  ctx.lineTo(x + width, y + height - radius)
  ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height)
  ctx.lineTo(x + radius, y + height)
  ctx.quadraticCurveTo(x, y + height, x, y + height - radius)
  ctx.lineTo(x, y + radius)
  ctx.quadraticCurveTo(x, y, x + radius, y)
  ctx.closePath()
}

// 前端业务函数：协调 createAvatarTitleTexture 对应的页面流程、接口调用或状态转换。
function createAvatarTitleTexture(THREE, title, active) {
  const canvas = document.createElement('canvas')
  canvas.width = 384
  canvas.height = 112
  const ctx = canvas.getContext?.('2d')
  if (ctx) {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    drawRoundedRect(ctx, 18, 24, 348, 58, 24)
    ctx.fillStyle = active ? 'rgba(69, 49, 18, 0.88)' : 'rgba(9, 9, 11, 0.82)'
    ctx.fill()
    ctx.strokeStyle = active ? 'rgba(252, 211, 77, 0.82)' : 'rgba(103, 232, 249, 0.48)'
    ctx.lineWidth = 4
    ctx.stroke()
    ctx.fillStyle = active ? '#fef3c7' : '#f8fafc'
    ctx.font = '600 30px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    const safeTitle = title.length > 10 ? `${title.slice(0, 10)}...` : title
    ctx.fillText(safeTitle, canvas.width / 2, 53)
  }
  const texture = new THREE.CanvasTexture(canvas)
  texture.needsUpdate = true
  return texture
}

// 前端业务函数：协调 addAvatarTitle 对应的页面流程、接口调用或状态转换。
function addAvatarTitle(THREE, base, expert) {
  const active = isExpertActive(expert.expert_id)
  const texture = createAvatarTitleTexture(THREE, expert.name || expertName(expert.expert_id), active)
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false,
    depthWrite: false,
  })
  const title = new THREE.Sprite(material)
  title.position.set(0, 2.26, 0)
  title.scale.set(1.36, 0.4, 1)
  title.userData = { expertId: expert.expert_id, avatarTitle: true, active }
  base.add(title)
  return title
}

// 前端业务函数：协调 addExpertStudio 对应的页面流程、接口调用或状态转换。
function addExpertStudio(THREE, target) {
  const studio = new THREE.Group()

  addBox(THREE, studio, [10.9, 0.14, 7.35], [0, -0.07, 0], '#111827')
  addBox(THREE, studio, [10.8, 0.02, 7.2], [0, 0.012, 0], '#1f2937', { roughness: 0.58, emissive: '#020617', opacity: 0.92, transparent: true })
  addFloorGrid(THREE, studio)
  addBox(THREE, studio, [10.95, 3.1, 0.16], [0, 1.48, -3.55], '#27272f')
  addBox(THREE, studio, [0.16, 3.0, 7.15], [-5.38, 1.42, 0], '#22242b')
  addBox(THREE, studio, [0.16, 3.0, 7.15], [5.38, 1.42, 0], '#1b1d24')
  addBox(THREE, studio, [10.95, 0.12, 0.16], [0, 3.02, -3.55], '#0f172a', { emissive: '#020617' })
  addBox(THREE, studio, [0.18, 0.12, 7.1], [-5.38, 3.02, 0], '#0f172a', { emissive: '#020617' })
  addBox(THREE, studio, [0.18, 0.12, 7.1], [5.38, 3.02, 0], '#0f172a', { emissive: '#020617' })
  addBox(THREE, studio, [10.65, 0.05, 0.08], [0, 0.38, -3.42], '#475569')
  addBox(THREE, studio, [0.08, 0.05, 6.9], [-5.25, 0.36, 0], '#475569')
  addBox(THREE, studio, [0.08, 0.05, 6.9], [5.25, 0.36, 0], '#475569')

  addZonePanel(THREE, studio, 'storyboard', [-3.45, 0.01, -1.55], [1.75, 0.035, 1.2], '#0e7490')
  addZonePanel(THREE, studio, 'image_stage', [-1.08, 0.012, -2.1], [1.7, 0.035, 1.05], '#6d28d9')
  addZonePanel(THREE, studio, 'video_stage', [1.42, 0.014, -1.9], [1.7, 0.035, 1.08], '#b45309')
  addZonePanel(THREE, studio, 'video_review', [3.42, 0.016, -0.55], [1.55, 0.035, 1.18], '#047857')
  addZonePanel(THREE, studio, 'compose', [2.35, 0.018, 1.68], [1.5, 0.035, 1.06], '#be123c')

  addWorkStation(THREE, studio, [-3.7, 0.72, -2.4], '#0e7490')
  addWorkStation(THREE, studio, [-1.15, 0.72, -2.88], '#6d28d9')
  addWorkStation(THREE, studio, [1.4, 0.72, -2.72], '#b45309')
  addWorkStation(THREE, studio, [3.85, 0.72, -1.35], '#047857')
  addWorkStation(THREE, studio, [2.7, 0.72, 2.35], '#be123c')

  addBox(THREE, studio, [2.8, 0.18, 1.25], [-0.2, 0.76, 0.28], '#3f3f46')
  addBox(THREE, studio, [2.55, 0.03, 1.0], [-0.2, 0.87, 0.28], '#71717a', { roughness: 0.35 })
  addBox(THREE, studio, [0.14, 0.68, 0.14], [-1.2, 0.34, -0.1], '#27272a')
  addBox(THREE, studio, [0.14, 0.68, 0.14], [0.8, 0.34, -0.1], '#27272a')
  addBox(THREE, studio, [0.14, 0.68, 0.14], [-1.2, 0.34, 0.68], '#27272a')
  addBox(THREE, studio, [0.14, 0.68, 0.14], [0.8, 0.34, 0.68], '#27272a')
  addBox(THREE, studio, [0.5, 0.08, 0.32], [-0.85, 0.98, 0.15], '#0891b2', { emissive: '#164e63' })
  addBox(THREE, studio, [0.44, 0.42, 0.06], [0.25, 1.12, -0.2], '#1e293b', { emissive: '#0f172a' })
  addBox(THREE, studio, [0.38, 0.03, 0.065], [0.25, 0.88, -0.15], '#67e8f9', { emissive: '#0891b2' })

  addBox(THREE, studio, [2.35, 1.05, 0.08], [-2.7, 1.78, -3.45], '#164e63', { emissive: '#083344', roughness: 0.35 })
  addBox(THREE, studio, [2.35, 1.05, 0.08], [2.7, 1.78, -3.45], '#1e3a8a', { emissive: '#172554', roughness: 0.35 })
  addBox(THREE, studio, [2.0, 0.06, 0.1], [-2.7, 1.24, -3.38], '#67e8f9', { emissive: '#155e75' })
  addBox(THREE, studio, [2.0, 0.06, 0.1], [2.7, 1.24, -3.38], '#a5b4fc', { emissive: '#312e81' })
  addBox(THREE, studio, [1.1, 0.08, 0.08], [0, 2.64, -3.42], '#f8fafc', { emissive: '#22d3ee' })
  addBox(THREE, studio, [0.92, 0.06, 0.08], [0, 2.48, -3.42], '#fbbf24', { emissive: '#b45309' })

  addBox(THREE, studio, [1.08, 2.08, 0.18], [4.82, 1.05, 2.35], '#7f1d1d', { emissive: '#450a0a', roughness: 0.5 })
  addBox(THREE, studio, [0.86, 1.72, 0.2], [4.82, 0.92, 2.2], '#111827', { emissive: '#020617', roughness: 0.42 })
  addBox(THREE, studio, [0.72, 0.08, 0.22], [4.82, 2.08, 2.18], '#fecaca', { emissive: '#991b1b' })
  addBox(THREE, studio, [0.26, 0.08, 0.24], [4.45, 1.08, 2.08], '#fda4af', { emissive: '#be123c' })
  addOverheadLights(THREE, studio)

  target.add(studio)
  return studio
}

// 前端业务函数：协调 addFloorGrid 对应的页面流程、接口调用或状态转换。
function addFloorGrid(THREE, target) {
  for (let x = -4; x <= 4; x += 1) {
    addBox(THREE, target, [0.018, 0.012, 7.0], [x, 0.035, 0], '#334155', { emissive: '#020617', opacity: 0.64, transparent: true })
  }
  for (let z = -3; z <= 3; z += 1) {
    addBox(THREE, target, [10.6, 0.012, 0.018], [0, 0.036, z], '#334155', { emissive: '#020617', opacity: 0.64, transparent: true })
  }
}

// 前端业务函数：协调 addZonePanel 对应的页面流程、接口调用或状态转换。
function addZonePanel(THREE, target, zoneKey, position, size, color) {
  const active = activeZoneKeys.value.has(zoneKey)
  const panel = addBox(THREE, target, size, position, color, {
    emissive: active ? color : '#111827',
    emissiveIntensity: active ? 1.35 : 0.28,
    roughness: active ? 0.28 : 0.65,
    userData: { zoneKey, active },
  })
  if (active) {
    addBox(THREE, target, [size[0] + 0.18, 0.028, size[2] + 0.18], [position[0], position[1] + 0.018, position[2]], color, {
      emissive: color,
      emissiveIntensity: 1.6,
      opacity: 0.26,
      transparent: true,
    })
  }
  addBox(THREE, target, [size[0] + 0.08, 0.08, 0.05], [position[0], 0.54, position[2] - size[2] / 2 - 0.08], color, {
    emissive: active ? color : '#0f172a',
    emissiveIntensity: active ? 1.05 : 0.2,
    roughness: 0.4,
  })
  return panel
}

// 前端业务函数：协调 addWorkStation 对应的页面流程、接口调用或状态转换。
function addWorkStation(THREE, target, position, color) {
  addBox(THREE, target, [1.28, 0.1, 0.68], [position[0], position[1] - 0.08, position[2]], '#374151')
  addBox(THREE, target, [1.1, 0.04, 0.5], [position[0], position[1] - 0.005, position[2]], '#52525b', { roughness: 0.36 })
  addBox(THREE, target, [0.82, 0.64, 0.1], [position[0], position[1] + 0.42, position[2] - 0.3], color, { emissive: color, emissiveIntensity: 0.74, roughness: 0.38 })
  addBox(THREE, target, [0.58, 0.05, 0.08], [position[0], position[1] + 0.06, position[2] - 0.24], '#e0f2fe', { emissive: color, emissiveIntensity: 1.1 })
  addBox(THREE, target, [0.18, 0.16, 0.18], [position[0] - 0.43, position[1] + 0.07, position[2] + 0.16], '#f8fafc', { roughness: 0.55 })
  addBox(THREE, target, [0.2, 0.04, 0.28], [position[0] + 0.42, position[1] + 0.03, position[2] + 0.14], '#0f172a', { emissive: '#111827' })
  addBox(THREE, target, [0.08, 0.36, 0.08], [position[0] + 0.57, position[1] + 0.16, position[2] + 0.08], color, { emissive: color })
  addSphere(THREE, target, 0.11, [position[0] + 0.57, position[1] + 0.39, position[2] + 0.02], '#fef3c7', { emissive: color, roughness: 0.42 })
}

// 前端业务函数：协调 addOverheadLights 对应的页面流程、接口调用或状态转换。
function addOverheadLights(THREE, target) {
  ;[-3.2, 0, 3.2].forEach(x => {
    addBox(THREE, target, [1.35, 0.045, 0.22], [x, 2.86, -0.9], '#e0f2fe', {
      emissive: '#67e8f9',
      emissiveIntensity: 1.2,
      roughness: 0.2,
    })
    addBox(THREE, target, [0.04, 0.36, 0.04], [x - 0.52, 2.64, -0.9], '#475569')
    addBox(THREE, target, [0.04, 0.36, 0.04], [x + 0.52, 2.64, -0.9], '#475569')
  })
}

// 前端业务函数：协调 seededUnit 对应的页面流程、接口调用或状态转换。
function seededUnit(seed) {
  const value = Math.sin(seed * 12.9898 + 78.233) * 43758.5453
  return value - Math.floor(value)
}

// 前端业务函数：协调 clamp 对应的页面流程、接口调用或状态转换。
function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

// 前端业务函数：协调 easeInOut 对应的页面流程、接口调用或状态转换。
function easeInOut(value) {
  const t = clamp(value, 0, 1)
  return t * t * (3 - 2 * t)
}

// 前端业务函数：协调 pointInsideObstacle 对应的页面流程、接口调用或状态转换。
function pointInsideObstacle(point, obstacle, padding = 0) {
  return (
    point.x >= obstacle.xMin - padding &&
    point.x <= obstacle.xMax + padding &&
    point.z >= obstacle.zMin - padding &&
    point.z <= obstacle.zMax + padding
  )
}

// 前端业务函数：协调 isPointWalkable 对应的页面流程、接口调用或状态转换。
function isPointWalkable(point, padding = 0.18) {
  return !STUDIO_OBSTACLES.some(obstacle => pointInsideObstacle(point, obstacle, padding))
}

// 前端业务函数：协调 segmentsIntersect 对应的页面流程、接口调用或状态转换。
function segmentsIntersect(a, b, c, d) {
  const cross = (p, q, r) => ((q.x - p.x) * (r.z - p.z)) - ((q.z - p.z) * (r.x - p.x))
  const abC = cross(a, b, c)
  const abD = cross(a, b, d)
  const cdA = cross(c, d, a)
  const cdB = cross(c, d, b)
  return (abC * abD <= 0) && (cdA * cdB <= 0)
}

// 前端业务函数：协调 segmentIntersectsObstacle 对应的页面流程、接口调用或状态转换。
function segmentIntersectsObstacle(start, end, obstacle, padding = 0.24) {
  const inflated = {
    xMin: obstacle.xMin - padding,
    xMax: obstacle.xMax + padding,
    zMin: obstacle.zMin - padding,
    zMax: obstacle.zMax + padding,
  }
  if (pointInsideObstacle(start, inflated) || pointInsideObstacle(end, inflated)) return true
  const topLeft = { x: inflated.xMin, z: inflated.zMin }
  const topRight = { x: inflated.xMax, z: inflated.zMin }
  const bottomRight = { x: inflated.xMax, z: inflated.zMax }
  const bottomLeft = { x: inflated.xMin, z: inflated.zMax }
  return (
    segmentsIntersect(start, end, topLeft, topRight) ||
    segmentsIntersect(start, end, topRight, bottomRight) ||
    segmentsIntersect(start, end, bottomRight, bottomLeft) ||
    segmentsIntersect(start, end, bottomLeft, topLeft)
  )
}

// 前端业务函数：协调 isWalkSegmentClear 对应的页面流程、接口调用或状态转换。
function isWalkSegmentClear(start, end) {
  return STUDIO_OBSTACLES.every(obstacle => !segmentIntersectsObstacle(start, end, obstacle))
}

// 前端业务函数：协调 jitterWaypoint 对应的页面流程、接口调用或状态转换。
function jitterWaypoint(point, seed) {
  const candidate = {
    x: clamp(point.x + (seededUnit(seed) - 0.5) * 0.42, -4.15, 4.15),
    z: clamp(point.z + (seededUnit(seed + 9.7) - 0.5) * 0.36, -2.95, 2.55),
  }
  return isPointWalkable(candidate) ? candidate : point
}

// 前端业务函数：协调 distanceBetween 对应的页面流程、接口调用或状态转换。
function distanceBetween(start, end) {
  return Math.hypot(end.x - start.x, end.z - start.z)
}

// 前端业务函数：协调 pickNextWaypointIndex 对应的页面流程、接口调用或状态转换。
function pickNextWaypointIndex(currentIndex, seed) {
  const nearby = STUDIO_WALK_LINKS
    .filter(([a, b]) => a === currentIndex || b === currentIndex)
    .map(([a, b]) => (a === currentIndex ? b : a))
    .filter(nextIndex => isWalkSegmentClear(STUDIO_WAYPOINTS[currentIndex], STUDIO_WAYPOINTS[nextIndex]))
  const candidates = nearby.length ? nearby : STUDIO_WAYPOINTS
    .map((_, index) => index)
    .filter(index => index !== currentIndex && isWalkSegmentClear(STUDIO_WAYPOINTS[currentIndex], STUDIO_WAYPOINTS[index]))
  return candidates[Math.floor(seededUnit(seed) * candidates.length) % candidates.length]
}

// 前端业务函数：协调 createWalkState 对应的页面流程、接口调用或状态转换。
function createWalkState(index, total) {
  const currentIndex = index % STUDIO_WAYPOINTS.length
  const nextIndex = pickNextWaypointIndex(currentIndex, index * 17 + total + 5)
  const previous = jitterWaypoint(STUDIO_WAYPOINTS[currentIndex], index * 31 + 3)
  const target = jitterWaypoint(STUDIO_WAYPOINTS[nextIndex], index * 31 + 17)
  const distance = distanceBetween(previous, target)
  const duration = 3.2 + distance * 1.08 + seededUnit(index * 19 + 4) * 1.25
  const pause = 0.5 + seededUnit(index * 23 + 8) * 1.1
  const segmentStartedAt = -seededUnit(index * 29 + 11) * duration * 0.72
  return {
    currentIndex: nextIndex,
    previous,
    target,
    duration,
    pause,
    segmentStartedAt,
    seed: index * 101 + 37,
    facing: Math.atan2(target.x - previous.x, target.z - previous.z),
  }
}

// 前端业务函数：协调 advanceWalkState 对应的页面流程、接口调用或状态转换。
function advanceWalkState(state) {
  state.previous = state.target
  const nextIndex = pickNextWaypointIndex(state.currentIndex, state.seed)
  state.currentIndex = nextIndex
  state.target = jitterWaypoint(STUDIO_WAYPOINTS[nextIndex], state.seed + 13)
  const distance = distanceBetween(state.previous, state.target)
  state.duration = 3.0 + distance * 1.12 + seededUnit(state.seed + 21) * 1.45
  state.pause = 0.45 + seededUnit(state.seed + 34) * 1.2
  state.facing = Math.atan2(state.target.x - state.previous.x, state.target.z - state.previous.z)
  state.seed += 1
}

// 前端业务函数：协调 randomWalkingPosition 对应的页面流程、接口调用或状态转换。
function randomWalkingPosition(state, elapsedSeconds) {
  while (elapsedSeconds >= state.segmentStartedAt + state.duration + state.pause) {
    state.segmentStartedAt += state.duration + state.pause
    advanceWalkState(state)
  }

  const localTime = elapsedSeconds - state.segmentStartedAt
  const rawProgress = localTime <= 0 ? 0 : localTime / state.duration
  const progress = easeInOut(rawProgress)
  const x = state.previous.x + (state.target.x - state.previous.x) * progress
  const z = state.previous.z + (state.target.z - state.previous.z) * progress
  if (rawProgress <= 1) {
    state.facing = Math.atan2(state.target.x - state.previous.x, state.target.z - state.previous.z)
  }
  return { x, z, facing: state.facing, moving: rawProgress > 0 && rawProgress < 1 }
}

// 前端业务函数：协调 avatarStageFacing 对应的页面流程、接口调用或状态转换。
function avatarStageFacing(facing, index) {
  return facing * 0.22 + Math.sin(index * 1.37) * 0.12
}

// 前端业务函数：协调 lerpAngle 对应的页面流程、接口调用或状态转换。
function lerpAngle(current, target, amount) {
  const delta = Math.atan2(Math.sin(target - current), Math.cos(target - current))
  return current + delta * amount
}

// 前端业务函数：协调 addAvatar 对应的页面流程、接口调用或状态转换。
function addAvatar(THREE, group, expert, index, total) {
  const walkState = createWalkState(index, total)
  const walk = randomWalkingPosition(walkState, 0)
  const color = COLORS[index % COLORS.length]
  const hairColor = ['#111827', '#7c2d12', '#581c87', '#0f172a', '#3f1d14'][index % 5]
  const accentColor = ['#22d3ee', '#f59e0b', '#a78bfa', '#34d399', '#fb7185'][index % 5]
  const base = new THREE.Group()
  base.position.set(walk.x, 0, walk.z)
  base.rotation.y = avatarStageFacing(walk.facing, index)
  base.scale.set(0.82, 0.82, 0.82)
  base.userData.expertId = expert.expert_id
  base.userData.walkIndex = index
  base.userData.walkState = walkState

  const leftLeg = addCapsule(THREE, base, 0.06, 0.34, [-0.13, 0.28, -0.02], '#111827', { rotation: [0, 0, 0.08], roughness: 0.7 })
  const rightLeg = addCapsule(THREE, base, 0.06, 0.34, [0.13, 0.28, -0.02], '#111827', { rotation: [0, 0, -0.08], roughness: 0.7 })
  const leftFoot = addBox(THREE, base, [0.2, 0.075, 0.29], [-0.15, 0.07, 0.12], '#020617', { roughness: 0.55 })
  const rightFoot = addBox(THREE, base, [0.2, 0.075, 0.29], [0.15, 0.07, 0.12], '#020617', { roughness: 0.55 })

  const body = addCapsule(THREE, base, 0.24, 0.48, [0, 0.78, 0], color, { roughness: 0.58 })
  const jacket = addBox(THREE, base, [0.62, 0.38, 0.34], [0, 0.92, 0.02], '#111827', { roughness: 0.72 })
  addBox(THREE, base, [0.18, 0.4, 0.035], [-0.1, 0.92, 0.2], accentColor, { emissive: accentColor, emissiveIntensity: 0.45, roughness: 0.36 })
  addBox(THREE, base, [0.18, 0.4, 0.035], [0.1, 0.92, 0.2], '#f8fafc', { roughness: 0.42 })

  const leftArm = addCapsule(THREE, base, 0.055, 0.45, [-0.4, 0.86, 0.02], '#fde2c4', { rotation: [0, 0, -0.52], roughness: 0.8 })
  const rightArm = addCapsule(THREE, base, 0.055, 0.45, [0.4, 0.86, 0.02], '#fde2c4', { rotation: [0, 0, 0.52], roughness: 0.8 })

  const neck = addBox(THREE, base, [0.18, 0.16, 0.16], [0, 1.18, 0], '#f9d2ad', { roughness: 0.75 })
  const head = addSphere(THREE, base, 0.5, [0, 1.55, 0.03], '#fde2c4', { widthSegments: 24, heightSegments: 16, roughness: 0.82 })
  const hairCap = addSphere(THREE, base, 0.52, [0, 1.72, -0.02], hairColor, {
    scale: [1.05, 0.62, 1.0],
    roughness: 0.88,
  })
  addSphere(THREE, base, 0.34, [0, 1.95, -0.08], hairColor, {
    scale: [1.05, 0.34, 0.84],
    roughness: 0.86,
  })
  const bangLeft = addCone(THREE, base, 0.16, 0.34, [-0.2, 1.84, 0.28], hairColor, { rotation: [0.65, 0, 0.35], roughness: 0.86 })
  const bangRight = addCone(THREE, base, 0.14, 0.3, [0.16, 1.84, 0.3], hairColor, { rotation: [0.68, 0, -0.32], roughness: 0.86 })
  if (index % 3 === 1) {
    addSphere(THREE, base, 0.15, [-0.46, 1.7, -0.02], hairColor, { roughness: 0.88 })
    addSphere(THREE, base, 0.15, [0.46, 1.7, -0.02], hairColor, { roughness: 0.88 })
  }

  addSphere(THREE, base, 0.065, [-0.15, 1.58, 0.43], '#f8fafc', { roughness: 0.35 })
  addSphere(THREE, base, 0.065, [0.15, 1.58, 0.43], '#f8fafc', { roughness: 0.35 })
  addSphere(THREE, base, 0.04, [-0.15, 1.58, 0.48], '#0f172a', { roughness: 0.25 })
  addSphere(THREE, base, 0.04, [0.15, 1.58, 0.48], '#0f172a', { roughness: 0.25 })
  addSphere(THREE, base, 0.012, [-0.132, 1.598, 0.516], '#ffffff', { emissive: '#ffffff', roughness: 0.2 })
  addSphere(THREE, base, 0.012, [0.168, 1.598, 0.516], '#ffffff', { emissive: '#ffffff', roughness: 0.2 })
  addBox(THREE, base, [0.14, 0.018, 0.02], [-0.15, 1.66, 0.47], hairColor, { rotation: [0, 0, 0.15], roughness: 0.52 })
  addBox(THREE, base, [0.14, 0.018, 0.02], [0.15, 1.66, 0.47], hairColor, { rotation: [0, 0, -0.15], roughness: 0.52 })
  addBox(THREE, base, [0.16, 0.025, 0.022], [0, 1.42, 0.5], '#7f1d1d', { roughness: 0.4 })
  addSphere(THREE, base, 0.035, [-0.29, 1.49, 0.39], '#fda4af', { roughness: 0.45, opacity: 0.72, transparent: true })
  addSphere(THREE, base, 0.035, [0.29, 1.49, 0.39], '#fda4af', { roughness: 0.45, opacity: 0.72, transparent: true })

  addBox(THREE, base, [0.22, 0.13, 0.024], [0.2, 0.96, 0.22], '#f8fafc', { roughness: 0.35 })
  addBox(THREE, base, [0.14, 0.02, 0.026], [0.2, 0.985, 0.236], accentColor, { emissive: accentColor, roughness: 0.3 })
  addAvatarProp(THREE, base, expert.expert_id, accentColor)

  if (isExpertActive(expert.expert_id)) {
    const halo = addTorus(THREE, base, 0.68, 0.024, [0, 2.06, 0.02], '#fde68a', {
      emissive: '#78350f',
      emissiveIntensity: 1.2,
      rotation: [Math.PI / 2, 0, 0],
      roughness: 0.35,
    })
    base.userData.activeHalo = halo
  }
  addAvatarTitle(THREE, base, expert)
  base.userData.parts = { body, jacket, head, hairCap, bangLeft, bangRight, leftArm, rightArm, leftLeg, rightLeg, leftFoot, rightFoot, neck }

  group.add(base)
  return base
}

// 前端业务函数：协调 addAvatarProp 对应的页面流程、接口调用或状态转换。
function addAvatarProp(THREE, base, expertId, accentColor) {
  if (expertId === 'short_video_editing_coach') {
    addBox(THREE, base, [0.28, 0.2, 0.04], [-0.48, 1.08, 0.28], '#f8fafc', { roughness: 0.38 })
    addBox(THREE, base, [0.28, 0.04, 0.044], [-0.48, 1.2, 0.3], '#111827')
    return
  }
  if (expertId === 'image_prompt_engineer' || expertId === 'prompt_engineer') {
    addBox(THREE, base, [0.09, 0.52, 0.04], [0.48, 1.08, 0.26], '#fde68a', { rotation: [0, 0, -0.28], roughness: 0.38 })
    addCone(THREE, base, 0.055, 0.14, [0.55, 1.29, 0.26], '#f97316', { rotation: [0, 0, -0.28] })
    return
  }
  if (expertId === 'video_optimization_specialist' || expertId.endsWith('_quality_reviewer')) {
    addBox(THREE, base, [0.26, 0.34, 0.035], [0.48, 1.03, 0.27], '#ecfeff', { roughness: 0.38 })
    addBox(THREE, base, [0.14, 0.04, 0.04], [0.48, 1.19, 0.29], '#22c55e', { emissive: '#166534' })
    return
  }
  if (expertId === 'narrative_designer' || expertId === 'visual_storyteller') {
    addBox(THREE, base, [0.34, 0.22, 0.035], [-0.48, 1.02, 0.28], '#0f172a', { emissive: '#1e293b' })
    addBox(THREE, base, [0.24, 0.035, 0.04], [-0.48, 0.9, 0.3], accentColor, { emissive: accentColor })
    return
  }
  addSphere(THREE, base, 0.09, [0.44, 1.12, 0.28], accentColor, { emissive: accentColor, roughness: 0.4 })
}

// 前端业务函数：协调 updateAvatarWalkPose 对应的页面流程、接口调用或状态转换。
function updateAvatarWalkPose(walker, index, elapsedSeconds, moving) {
  const parts = walker.userData.parts || {}
  const stride = moving ? Math.sin(elapsedSeconds * 7.2 + index * 0.71) : 0
  const counterStride = -stride
  const leftLift = Math.max(0, stride) * 0.06
  const rightLift = Math.max(0, counterStride) * 0.06

  if (parts.leftLeg) {
    parts.leftLeg.position.z = -0.02 + stride * 0.12
    parts.leftLeg.position.y = 0.28 + leftLift * 0.38
    parts.leftLeg.rotation.x = stride * 0.36
    parts.leftLeg.rotation.z = 0.08 + stride * 0.05
  }
  if (parts.rightLeg) {
    parts.rightLeg.position.z = -0.02 + counterStride * 0.12
    parts.rightLeg.position.y = 0.28 + rightLift * 0.38
    parts.rightLeg.rotation.x = counterStride * 0.36
    parts.rightLeg.rotation.z = -0.08 + counterStride * 0.05
  }
  if (parts.leftFoot) {
    parts.leftFoot.position.z = 0.12 + stride * 0.16
    parts.leftFoot.position.y = 0.07 + leftLift
    parts.leftFoot.rotation.x = -stride * 0.22
  }
  if (parts.rightFoot) {
    parts.rightFoot.position.z = 0.12 + counterStride * 0.16
    parts.rightFoot.position.y = 0.07 + rightLift
    parts.rightFoot.rotation.x = -counterStride * 0.22
  }
  if (parts.leftArm) {
    parts.leftArm.rotation.x = counterStride * 0.46
    parts.leftArm.rotation.z = -0.52 + counterStride * 0.08
  }
  if (parts.rightArm) {
    parts.rightArm.rotation.x = stride * 0.46
    parts.rightArm.rotation.z = 0.52 + stride * 0.08
  }
  if (parts.body) parts.body.rotation.z = stride * 0.025
  if (parts.jacket) parts.jacket.rotation.z = stride * 0.025
  if (parts.head) parts.head.rotation.z = Math.sin(elapsedSeconds * 2.4 + index) * (moving ? 0.03 : 0.012)
}

// 前端业务函数：协调 isRenderCurrent 对应的页面流程、接口调用或状态转换。
function isRenderCurrent(token) {
  return !unmounted && token === renderToken && canRender3d.value && canvasEl.value
}

// 前端业务函数：协调 expertIdFromObject 对应的页面流程、接口调用或状态转换。
function expertIdFromObject(object) {
  let cursor = object
  while (cursor) {
    if (cursor.userData?.expertId) return cursor.userData.expertId
    cursor = cursor.parent
  }
  return ''
}

// 前端业务函数：协调 renderScene 对应的页面流程、接口调用或状态转换。
async function renderScene() {
  const token = ++renderToken
  stopScene()
  if (!canRender3d.value) return
  await nextTick()
  if (!isRenderCurrent(token)) return
  const canvas = canvasEl.value
  if (!canvas) return
  if (!hasWebglContext()) {
    contextUnavailable.value = true
    return
  }

  const THREE = await import('three')
  if (!isRenderCurrent(token)) return
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: 'high-performance' })
  } catch {
    contextUnavailable.value = true
    return
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
  if (renderer.shadowMap) renderer.shadowMap.enabled = true
  scene = new THREE.Scene()
  scene.background = new THREE.Color('#05060a')
  camera = new THREE.PerspectiveCamera(43, 1, 0.1, 100)
  camera.position.set(0, 4.65, 8.6)
  camera.lookAt(0, 1.1, -0.35)

  scene.add(new THREE.AmbientLight(0xffffff, 0.68))
  const keyLight = new THREE.DirectionalLight(0xffffff, 1.25)
  keyLight.position.set(2.8, 7.2, 5.8)
  scene.add(keyLight)
  const rimLight = new THREE.DirectionalLight(0x67e8f9, 0.86)
  rimLight.position.set(-4.5, 4.8, -5.2)
  scene.add(rimLight)
  const warmLight = new THREE.DirectionalLight(0xfbbf24, 0.38)
  warmLight.position.set(4.5, 2.6, 2.4)
  scene.add(warmLight)

  addExpertStudio(THREE, scene)

  const teamGroup = new THREE.Group()
  const walkers = visibleExperts.value.map((expert, index) => addAvatar(THREE, teamGroup, expert, index, visibleExperts.value.length))
  scene.add(teamGroup)
  const sceneStartedAt = Date.now() / 1000

  resizeHandler = resizeRenderer
  window.addEventListener('resize', resizeHandler)
  const raycaster = new THREE.Raycaster()
  const pointer = new THREE.Vector2()
  canvasClickHandler = event => {
    if (!renderer || !camera) return
    const rect = renderer.domElement.getBoundingClientRect()
    if (!rect.width || !rect.height) return
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
    raycaster.setFromCamera(pointer, camera)
    const hit = raycaster.intersectObjects(teamGroup.children, true)[0]
    const expertId = expertIdFromObject(hit?.object)
    if (expertId) selectExpert(expertId)
  }
  canvas.addEventListener('click', canvasClickHandler)
  canvasClickTarget = canvas
  resizeRenderer()

  const animate = () => {
    if (!isRenderCurrent(token) || !renderer || !scene || !camera) return
    if (!staticMode.value) {
      const elapsedSeconds = (Date.now() / 1000) - sceneStartedAt
      walkers.forEach((walker, index) => {
        const walk = randomWalkingPosition(walker.userData.walkState, elapsedSeconds)
        const stride = walk.moving ? Math.sin(elapsedSeconds * 7.2 + index * 0.71) : 0
        const bob = walk.moving ? Math.abs(stride) * 0.028 : 0
        walker.position.set(walk.x, bob, walk.z)
        walker.rotation.y = lerpAngle(walker.rotation.y, avatarStageFacing(walk.facing, index), 0.075)
        updateAvatarWalkPose(walker, index, elapsedSeconds, walk.moving)
        if (walker.userData.activeHalo) walker.userData.activeHalo.rotation.z += 0.025
      })
      frameId = requestAnimationFrame(animate)
    }
    renderer.render(scene, camera)
  }
  animate()
}

watch(() => [expertSignature.value, invocationStatusSignature.value, stageGraphSignature.value, canRender3d.value], renderScene, { immediate: true })
watch(staticMode, () => {
  if (!renderer || !scene || !camera) return
  if (staticMode.value && frameId) {
    cancelAnimationFrame(frameId)
    frameId = 0
    renderer.render(scene, camera)
    return
  }
  renderScene()
})

onMounted(() => {
  window.addEventListener('resize', updateViewport)
})

onBeforeUnmount(() => {
  unmounted = true
  renderToken += 1
  window.removeEventListener('resize', updateViewport)
  stopScene()
})
</script>
