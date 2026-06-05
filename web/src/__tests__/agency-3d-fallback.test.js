import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import AgencyTeamMap3D from '../components/agency/AgencyTeamMap3D.vue'

const threeState = vi.hoisted(() => ({
  delayImport: false,
  importGate: null,
  rendererConstructed: vi.fn(),
  rendererDisposed: 0,
  geometryDisposed: 0,
  materialDisposed: 0,
  textureDisposed: 0,
  spriteCreated: 0,
  sprites: [],
  raycastHit: false,
}))

vi.mock('three', async () => {
  if (threeState.delayImport && threeState.importGate) {
    await threeState.importGate
  }

  class Node3D {
    constructor() {
      this.children = []
      this.userData = {}
      this.position = { x: 0, y: 0, z: 0, set: vi.fn((x, y, z) => {
        this.position.x = x
        this.position.y = y
        this.position.z = z
      }) }
      this.rotation = { x: 0, y: 0, z: 0 }
      this.scale = { set: vi.fn() }
    }

    add(child) {
      this.children.push(child)
    }

    lookAt() {}

    traverse(visitor) {
      visitor(this)
      this.children.forEach(child => child.traverse ? child.traverse(visitor) : visitor(child))
    }
  }

  class Mesh extends Node3D {
    constructor(geometry, material) {
      super()
      this.isMesh = true
      this.geometry = geometry
      this.material = material
    }
  }

  class MeshStandardMaterial {
    constructor(options = {}) {
      Object.assign(this, options)
      this.map = {
        isTexture: true,
        dispose: vi.fn(() => {
          threeState.textureDisposed += 1
        }),
      }
    }

    dispose() {
      threeState.materialDisposed += 1
    }
  }

  class SpriteMaterial {
    constructor(options = {}) {
      Object.assign(this, options)
    }

    dispose() {
      threeState.materialDisposed += 1
    }
  }

  class CanvasTexture {
    constructor(image) {
      this.image = image
      this.isTexture = true
    }

    dispose() {
      threeState.textureDisposed += 1
    }
  }

  class Sprite extends Node3D {
    constructor(material) {
      super()
      this.isSprite = true
      this.material = material
      threeState.spriteCreated += 1
      threeState.sprites.push(this)
    }
  }

  class Geometry {
    dispose() {
      threeState.geometryDisposed += 1
    }
  }

  class WebGLRenderer {
    constructor({ canvas }) {
      this.domElement = canvas
      threeState.rendererConstructed()
    }

    setPixelRatio() {}
    setSize() {}
    render() {}

    dispose() {
      threeState.rendererDisposed += 1
    }
  }

  class PerspectiveCamera extends Node3D {
    updateProjectionMatrix() {}
  }

  return {
    AmbientLight: class AmbientLight extends Node3D {},
    BoxGeometry: Geometry,
    CapsuleGeometry: Geometry,
    CanvasTexture,
    CircleGeometry: Geometry,
    Color: class Color {
      constructor(value) {
        this.value = value
      }
    },
    ConeGeometry: Geometry,
    DirectionalLight: class DirectionalLight extends Node3D {},
    Group: class Group extends Node3D {},
    Mesh,
    MeshStandardMaterial,
    PerspectiveCamera,
    Raycaster: class Raycaster {
      setFromCamera() {}
      intersectObjects(objects) {
        return threeState.raycastHit && objects[0] ? [{ object: objects[0] }] : []
      }
    },
    Scene: class Scene extends Node3D {},
    SphereGeometry: Geometry,
    Sprite,
    SpriteMaterial,
    TorusGeometry: Geometry,
    Vector2: class Vector2 {
      constructor() {
        this.x = 0
        this.y = 0
      }
    },
    WebGLRenderer,
  }
})

const experts = [
  { expert_id: 'short_video_editing_coach', name: '短视频剪辑指导师', phases: ['storyboard'] },
  { expert_id: 'prompt_engineer', name: '提示词工程师', phases: ['storyboard'] },
]

const originalDom = {
  webglRenderingContext: Object.getOwnPropertyDescriptor(window, 'WebGLRenderingContext'),
  getContext: HTMLCanvasElement.prototype.getContext,
  innerWidth: Object.getOwnPropertyDescriptor(window, 'innerWidth'),
  matchMedia: Object.getOwnPropertyDescriptor(window, 'matchMedia'),
}

const mountedWrappers = []

function resetThreeState() {
  threeState.delayImport = false
  threeState.importGate = null
  threeState.rendererConstructed.mockClear()
  threeState.rendererDisposed = 0
  threeState.geometryDisposed = 0
  threeState.materialDisposed = 0
  threeState.textureDisposed = 0
  threeState.spriteCreated = 0
  threeState.sprites = []
  threeState.raycastHit = false
}

function useNoWebgl() {
  delete window.WebGLRenderingContext
  HTMLCanvasElement.prototype.getContext = vi.fn(() => null)
}

function useWebgl() {
  window.WebGLRenderingContext = vi.fn()
  HTMLCanvasElement.prototype.getContext = vi.fn(type => type === 'webgl' ? {} : null)
  Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: 1024 })
  window.matchMedia = vi.fn(() => ({ matches: true }))
}

function restoreDescriptor(target, key, descriptor) {
  if (descriptor) {
    Object.defineProperty(target, key, descriptor)
    return
  }
  delete target[key]
}

function restoreDomMocks() {
  restoreDescriptor(window, 'WebGLRenderingContext', originalDom.webglRenderingContext)
  HTMLCanvasElement.prototype.getContext = originalDom.getContext
  restoreDescriptor(window, 'innerWidth', originalDom.innerWidth)
  restoreDescriptor(window, 'matchMedia', originalDom.matchMedia)
}

function mountComponent(options) {
  const wrapper = mount(AgencyTeamMap3D, options)
  mountedWrappers.push(wrapper)
  return wrapper
}

function unmountWrapper(wrapper) {
  const index = mountedWrappers.indexOf(wrapper)
  if (index !== -1) mountedWrappers.splice(index, 1)
  wrapper.unmount()
}

function latestAvatarTitle(expertId) {
  return [...threeState.sprites]
    .reverse()
    .find(sprite => sprite.userData.avatarTitle && sprite.userData.expertId === expertId)
}

describe('AgencyTeamMap3D', () => {
  beforeEach(() => {
    resetThreeState()
    useNoWebgl()
  })

  afterEach(() => {
    mountedWrappers.splice(0).forEach(wrapper => wrapper.unmount())
    restoreDomMocks()
  })

  it('falls back to 2D when WebGL is unavailable', () => {
    const wrapper = mountComponent({
      props: { experts, stageGraph: [], invocations: [], webglAvailable: false },
    })

    expect(wrapper.text()).toContain('3D 专家人物化')
    expect(wrapper.text()).toContain('已切换到 2D 专家协作图')
    expect(wrapper.text()).toContain('短视频剪辑指导师')
    expect(wrapper.find('canvas').exists()).toBe(false)
  })

  it('shows Chinese responsibilities and phases in the 2D fallback cards', () => {
    const wrapper = mountComponent({
      props: {
        experts: [
          { expert_id: 'short_video_editing_coach', name: '短视频剪辑指导师', phases: ['storyboard'], role_type: 'core' },
          { expert_id: 'prompt_engineer', name: '提示词工程师', phases: ['storyboard'] },
          { expert_id: 'storyboard_quality_reviewer', name: '分镜脚本质量审查专家', phases: ['storyboard'], role_type: 'quality' },
        ],
        stageGraph: [{
          stage: 'storyboard',
          status: 'completed',
          lead: 'short_video_editing_coach',
          reviewers: ['prompt_engineer'],
          qa: ['storyboard_quality_reviewer'],
        }],
        invocations: [{ expert_id: 'prompt_engineer', role: 'reviewer' }],
        webglAvailable: false,
      },
    })

    expect(wrapper.text()).toContain('职责：核心专家 / 主责汇总')
    expect(wrapper.text()).toContain('职责：并行审阅')
    expect(wrapper.text()).toContain('职责：质量门禁')
    expect(wrapper.text()).toContain('分镜脚本')
    expect(wrapper.text()).toContain('分镜脚本质量审查专家')
  })

  it('keeps 3D expert titles attached to avatars and selects the clicked avatar', async () => {
    useWebgl()
    const wrapper = mountComponent({
      props: {
        experts: [
          { expert_id: 'short_video_editing_coach', name: '短视频剪辑指导师', phases: ['storyboard'], role_type: 'core' },
          { expert_id: 'prompt_engineer', name: '提示词工程师', phases: ['storyboard'] },
        ],
        stageGraph: [{
          stage: 'storyboard',
          status: 'completed',
          lead: 'short_video_editing_coach',
          reviewers: ['prompt_engineer'],
          qa: [],
        }],
        invocations: [{ expert_id: 'prompt_engineer', role: 'reviewer' }],
        webglAvailable: true,
      },
    })

    await flushPromises()

    expect(wrapper.find('button[data-expert-id="prompt_engineer"]').exists()).toBe(false)
    expect(threeState.spriteCreated).toBeGreaterThanOrEqual(2)
    expect(wrapper.text()).toContain('人物化专家可视化')
    expect(wrapper.text()).toContain('动漫制作工作室')
    expect(wrapper.text()).toContain('在房间里随机走动')
    expect(wrapper.text()).toContain('点击人物模型可打开专家档案')

    const canvas = wrapper.find('canvas')
    canvas.element.getBoundingClientRect = () => ({ left: 0, top: 0, width: 320, height: 240 })
    threeState.raycastHit = true
    await canvas.trigger('click', { clientX: 120, clientY: 80 })

    expect(wrapper.emitted('select')?.[0]).toEqual(['short_video_editing_coach'])
  })

  it('presents a full anime studio stage with compact expert nameplates', async () => {
    useWebgl()
    const wrapper = mountComponent({
      props: {
        experts: [
          { expert_id: 'short_video_editing_coach', name: '短视频剪辑指导师', phases: ['storyboard'], role_type: 'core' },
          { expert_id: 'prompt_engineer', name: '提示词工程师', phases: ['storyboard'] },
          { expert_id: 'storyboard_quality_reviewer', name: '分镜脚本质量审查专家', phases: ['storyboard'], role_type: 'quality' },
        ],
        stageGraph: [{
          stage: 'storyboard',
          status: 'running',
          lead: 'short_video_editing_coach',
          reviewers: ['prompt_engineer'],
          qa: ['storyboard_quality_reviewer'],
        }],
        invocations: [{ expert_id: 'prompt_engineer', role: 'reviewer', execution_status: 'running' }],
        webglAvailable: true,
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('动漫制作工作室')
    expect(wrapper.text()).toContain('分镜区')
    expect(wrapper.text()).toContain('图像区')
    expect(wrapper.text()).toContain('视频区')
    expect(wrapper.text()).toContain('质检区')
    expect(wrapper.text()).toContain('输出门')
    expect(wrapper.text()).toContain('亮起')
    expect(wrapper.text()).toContain('待命')
    expect(wrapper.text()).toContain('历史')

    expect(wrapper.find('button[data-expert-id="prompt_engineer"]').exists()).toBe(false)
    expect(threeState.spriteCreated).toBeGreaterThanOrEqual(3)
  })

  it('uses the 2D fallback on narrow screens without rendering a canvas', async () => {
    useWebgl()
    Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: 480 })
    const wrapper = mountComponent({
      props: { experts, stageGraph: [], invocations: [], webglAvailable: true },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('窄屏设备优先显示卡片列表')
    expect(wrapper.find('canvas').exists()).toBe(false)
    expect(threeState.rendererConstructed).not.toHaveBeenCalled()
  })

  it('switches to the 2D fallback when WebGL context creation returns null', async () => {
    window.WebGLRenderingContext = vi.fn()
    HTMLCanvasElement.prototype.getContext = vi.fn(() => null)
    Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: 1024 })
    window.matchMedia = vi.fn(() => ({ matches: true }))

    const wrapper = mountComponent({
      props: { experts, stageGraph: [], invocations: [], webglAvailable: true },
    })
    await flushPromises()
    await nextTick()

    expect(wrapper.text()).toContain('当前环境无法使用三维渲染')
    expect(wrapper.find('canvas').exists()).toBe(false)
    expect(threeState.rendererConstructed).not.toHaveBeenCalled()
  })

  it('refreshes 3D highlight when invocation status changes without length change', async () => {
    useWebgl()
    const wrapper = mountComponent({
      props: {
        experts,
        stageGraph: [],
        invocations: [{ expert_id: 'prompt_engineer', execution_status: 'completed', result_status: 'completed' }],
        webglAvailable: true,
      },
    })
    await flushPromises()

    expect(threeState.rendererConstructed).toHaveBeenCalledTimes(1)
    expect(latestAvatarTitle('prompt_engineer')?.userData.active).toBe(false)

    await wrapper.setProps({
      invocations: [{ expert_id: 'prompt_engineer', execution_status: 'running', result_status: 'completed' }],
    })
    await flushPromises()

    expect(threeState.rendererConstructed).toHaveBeenCalledTimes(2)
    expect(latestAvatarTitle('prompt_engineer')?.userData.active).toBe(true)
  })

  it('does not mark future pending stage assignees as active without invocation evidence', async () => {
    useWebgl()
    const wrapper = mountComponent({
      props: {
        experts: [
          ...experts,
          { expert_id: 'storyboard_quality_reviewer', name: '分镜脚本质量审查专家', phases: ['storyboard'], role_type: 'quality' },
        ],
        stageGraph: [{
          stage: 'storyboard',
          status: 'pending',
          lead: 'short_video_editing_coach',
          reviewers: ['prompt_engineer'],
          qa: ['storyboard_quality_reviewer'],
        }],
        invocations: [],
        webglAvailable: true,
      },
    })
    await flushPromises()

    expect(latestAvatarTitle('short_video_editing_coach')?.userData.active).toBe(false)
    expect(latestAvatarTitle('prompt_engineer')?.userData.active).toBe(false)
    expect(latestAvatarTitle('storyboard_quality_reviewer')?.userData.active).toBe(false)
  })

  it('refreshes 3D highlight when stage status changes without invocation changes', async () => {
    useWebgl()
    const invocations = [{ expert_id: 'prompt_engineer', execution_status: 'completed', result_status: 'completed' }]
    const wrapper = mountComponent({
      props: {
        experts,
        stageGraph: [{
          stage: 'storyboard',
          status: 'completed',
          reviewers: ['prompt_engineer'],
          lead: 'short_video_editing_coach',
          qa: [],
        }],
        invocations,
        webglAvailable: true,
      },
    })
    await flushPromises()

    expect(threeState.rendererConstructed).toHaveBeenCalledTimes(1)
    expect(latestAvatarTitle('prompt_engineer')?.userData.active).toBe(false)

    await wrapper.setProps({
      stageGraph: [{
        stage: 'storyboard',
        status: 'warning',
        reviewers: ['prompt_engineer'],
        lead: 'short_video_editing_coach',
        qa: [],
      }],
      invocations,
    })
    await flushPromises()

    expect(threeState.rendererConstructed).toHaveBeenCalledTimes(2)
    expect(latestAvatarTitle('prompt_engineer')?.userData.active).toBe(true)
  })

  it('does not create a WebGL renderer after unmount during async import', async () => {
    useWebgl()
    let resolveImport
    threeState.delayImport = true
    threeState.importGate = new Promise(resolve => {
      resolveImport = resolve
    })

    const wrapper = mountComponent({
      props: { experts, stageGraph: [], invocations: [], webglAvailable: true },
    })
    await nextTick()

    unmountWrapper(wrapper)
    resolveImport()
    await flushPromises()

    expect(threeState.rendererConstructed).not.toHaveBeenCalled()
  })

  it('disposes scene geometry, material, textures and renderer on unmount', async () => {
    useWebgl()
    const wrapper = mountComponent({
      props: { experts, stageGraph: [], invocations: [], webglAvailable: true },
    })
    await flushPromises()

    unmountWrapper(wrapper)

    expect(threeState.geometryDisposed).toBeGreaterThan(0)
    expect(threeState.materialDisposed).toBeGreaterThan(0)
    expect(threeState.textureDisposed).toBeGreaterThan(0)
    expect(threeState.rendererDisposed).toBe(1)
  })
})
