import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AgencyConsolePage from '../views/AgencyConsolePage.vue'
import {
  applyAgencyCreativePatch,
  approveAgencyCreativePatch,
  getAgencyExpert,
  listAgencyRepairTasks,
  listAgencyCreativePatches,
  retryAgencyRepairTask,
  updateAgencyCreativePatch,
} from '../api/agency.js'
import { getAgencyConsole } from '../api/series.js'

const routeState = vi.hoisted(() => ({ query: {} }))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { seriesId: 'sid' }, query: routeState.query }),
  useRouter: () => ({ back: vi.fn() }),
}))

vi.mock('../api/agency.js', () => ({
  getAgencyExpert: vi.fn(() => Promise.resolve({
    data: {
      expert_id: 'prompt_engineer',
      name: '提示词工程师',
      source_path: 'specialized/prompt-engineer.md',
      source_commit: '13b8800',
      sha256: 'abc123',
      markdown: '# 提示词工程师\n\n负责把故事意图拆解为稳定提示词。',
    },
  })),
  listAgencyCreativePatches: vi.fn(() => Promise.resolve({
    data: {
      summary: { total: 1, blocking: 1, proposed: 1, edited: 0, approved: 0, applied: 0, rejected: 0 },
      items: [{
        id: 'patch-1',
        stage: 'storyboard',
        patch_type: 'storyboard_patch',
        target_type: 'storyboard_frame',
        target_id: 'shot-001',
        title: '强化前三秒钩子',
        reason: '原分镜冲突不够强。',
        before: { image_prompt: '原画面' },
        after: { image_prompt: '新画面' },
        status: 'proposed',
        priority: 'high',
        source_invocation_id: 'inv-1',
      }],
    },
  })),
  updateAgencyCreativePatch: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  approveAgencyCreativePatch: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  rejectAgencyCreativePatch: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  applyAgencyCreativePatch: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  listAgencyRepairTasks: vi.fn(() => Promise.resolve({
    data: {
      summary: { total: 1, blocking: 1, queued: 0, running: 0, failed: 1, manual_required: 0, recheck_required: 0 },
      items: [{
        id: 'repair-job-1',
        type: 'storyboard_missing_references',
        stage: 'image_stage',
        status: 'failed',
        reason: '图像阶段参考图缺失',
        repair_action_label: '去处理图像问题',
        repair_route: '/ai-video-review?run_id=run-1',
        affected_ids: ['seg-1'],
        retry_actions: { retry_enabled: true, primary_label: '重试返修' },
      }],
    },
  })),
  retryAgencyRepairTask: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  authorizeAgencyRepairRetry: vi.fn(() => Promise.resolve({ data: { ok: true } })),
}))

vi.mock('../api/series.js', () => ({
  getAgencyConsole: vi.fn(() => Promise.resolve({
    data: {
      ok: true,
      series: { id: 'sid', title: '城市疗愈师' },
      latest_run: { id: 'run-1', status: 'image_review_pending' },
      agency_trace_status: 'failed',
      expert_team: [
        { expert_id: 'narrative_designer', name: '叙事设计师', phases: ['storyboard'], role_type: 'core' },
        { expert_id: 'visual_storyteller', name: '视觉叙事师', phases: ['style_lock', 'storyboard'], role_type: 'core' },
        { expert_id: 'image_prompt_engineer', name: '图像提示词工程师', phases: ['style_lock', 'image_stage'], role_type: 'core' },
        { expert_id: 'prompt_engineer', name: '提示词工程师', phases: ['image_stage', 'video_stage'], role_type: 'core' },
        { expert_id: 'short_video_editing_coach', name: '短视频剪辑指导师', phases: ['storyboard', 'compose'], role_type: 'core' },
        { expert_id: 'douyin_strategist', name: '抖音策略师', phases: ['storyboard', 'compose'], role_type: 'core' },
        { expert_id: 'video_optimization_specialist', name: '视频优化专家', phases: ['video_review', 'compose'], role_type: 'support' },
        { expert_id: 'style_lock_quality_reviewer', name: '风格锁定质量审查专家', phases: ['style_lock'], role_type: 'quality' },
        { expert_id: 'storyboard_quality_reviewer', name: '分镜脚本质量审查专家', phases: ['storyboard'], role_type: 'quality' },
        { expert_id: 'image_stage_quality_reviewer', name: '图像生成质量审查专家', phases: ['image_stage'], role_type: 'quality' },
        { expert_id: 'image_review_quality_reviewer', name: '图像结果质量审查专家', phases: ['image_review'], role_type: 'quality' },
        { expert_id: 'video_stage_quality_reviewer', name: '视频生成质量审查专家', phases: ['video_stage'], role_type: 'quality' },
        { expert_id: 'video_review_quality_reviewer', name: '视频结果质量审查专家', phases: ['video_review'], role_type: 'quality' },
        { expert_id: 'compose_quality_reviewer', name: '合成交付质量审查专家', phases: ['compose'], role_type: 'quality' },
      ],
      stage_graph: [
        {
          stage: 'style_lock',
          label: '风格锁定',
          status: 'completed',
          reviewers: ['image_prompt_engineer'],
          lead: 'visual_storyteller',
          qa: ['style_lock_quality_reviewer'],
          invocation_ids: [],
        },
        {
          stage: 'storyboard',
          label: '分镜脚本',
          status: 'failed',
          reviewers: ['visual_storyteller', 'short_video_editing_coach', 'douyin_strategist'],
          lead: 'narrative_designer',
          qa: ['storyboard_quality_reviewer'],
          invocation_ids: ['inv-1'],
        },
        {
          stage: 'image_stage',
          label: 'Image Stage',
          status: 'image_batch_running',
          reviewers: ['prompt_engineer'],
          lead: 'image_prompt_engineer',
          qa: ['image_stage_quality_reviewer'],
          invocation_ids: ['inv-2'],
        },
      ],
      expert_invocations: [{
        id: 'inv-1',
        stage: 'storyboard',
        expert_id: 'prompt_engineer',
        role: 'reviewer',
        result_status: 'failed',
        summary: '结构不稳定',
      }],
      decision_log: [{
        invocation_id: 'inv-1',
        stage: 'storyboard',
        expert_id: 'prompt_engineer',
        role: 'reviewer',
        result_status: 'failed',
        decision: 'Invalid JSON',
        findings: ['Missing reference image', '质量门返回 MODEL_TIMEOUT，provider task timeout'],
        required_changes: ['Retry provider worker', '重新执行 image_stage frame_01'],
        evidence: ['inv-1', 'provider_task_id=task_123 image_stage'],
        next_action: 'Open provider retry panel',
        display_scope: 'current_team',
      }, {
        invocation_id: 'inv-2',
        stage: 'image_stage',
        expert_id: 'image_stage_quality_reviewer',
        role: 'qa',
        result_status: 'warning',
        decision: 'Characters (老李, 王医生, 张阿姨, 小刘) : , is incomplete.',
        findings: [
          "Scenes (书房, 公园步道, 菜市场, 家庭餐桌, 厨房) is ''.",
          'Evidence trace: character_refs (, , , ) scene_refs (, , ) are empty.',
          'Character face consistency is weak across front/profile references; scene lighting shifts between park walkway and kitchen; shot continuity misses the previous end-frame state.',
        ],
        required_changes: [
          'Add a provider task to regenerate in image_stage.',
          'or create a compose fallback.',
          'Regenerate character anchor images before image generation and keep warm morning light across park walkway, kitchen, and dining table shots.',
        ],
        evidence: ['characters (, , , ) scenes (, , ) empty_refs'],
        next_action: 'a worker to retry in image_stage or a compose fallback.',
        display_scope: 'current_team',
      }],
      production_steps: [
        { id: 'style_lock', label: '风格锁定', status: 'completed' },
        { id: 'provider_worker', label: 'Provider Worker', status: 'image_batch_running', summary: 'waiting worker result' },
      ],
      creative_patch_summary: { total: 1, blocking: 1, proposed: 1, applied: 0 },
      creative_patches: [{
        id: 'patch-1',
        stage: 'storyboard',
        patch_type: 'storyboard_patch',
        target_type: 'storyboard_frame',
        target_id: 'shot-001',
        title: '强化前三秒钩子',
        status: 'proposed',
        priority: 'high',
      }],
    },
  })),
}))

describe('AgencyConsolePage', () => {
  beforeEach(() => {
    routeState.query = {}
    getAgencyConsole.mockClear()
    getAgencyExpert.mockClear()
    listAgencyCreativePatches.mockClear()
    listAgencyRepairTasks.mockClear()
    retryAgencyRepairTask.mockClear()
    updateAgencyCreativePatch.mockClear()
    approveAgencyCreativePatch.mockClear()
    applyAgencyCreativePatch.mockClear()
  })

  it('renders the production command center with Chinese labels only', async () => {
    const wrapper = mount(AgencyConsolePage)
    await flushPromises()

    expect(wrapper.text()).toContain('AI 视频生产指挥台')
    expect(wrapper.text()).toContain('专家团队透明控制台')
    expect(wrapper.text()).toContain('城市疗愈师')
    expect(wrapper.text()).toContain('生产总览')
    expect(wrapper.text()).toContain('阶段流转')
    expect(wrapper.text()).toContain('专家席位')
    expect(wrapper.text()).toContain('创作补丁')
    expect(wrapper.text()).toContain('进入 3D 专家人物化')
    expect(wrapper.text()).toContain('轨迹失败')
    expect(wrapper.text()).toContain('专家轨迹存在阻断')
    expect(wrapper.find('[data-test="agency-blocking-message"]').text()).toContain('下方「决策日志」')
    expect(wrapper.find('[data-test="agency-blocking-message"]').text()).toContain('必须修改')
    expect(wrapper.find('[data-test="jump-to-decision-log"]').exists()).toBe(true)
    expect(wrapper.find('#agency-decision-log').exists()).toBe(true)
    expect(wrapper.text()).toContain('风格锁定')
    expect(wrapper.text()).toContain('专家调用拓扑')
    expect(wrapper.text()).toContain('专家席位地图')
    expect(wrapper.text()).toContain('决策日志')
    expect(wrapper.text()).toContain('提示词工程师')
    expect(wrapper.text()).toContain('14 位当前专家，7 个阶段质量门')
    expect(wrapper.text()).toContain('分镜脚本质量审查专家')
    expect(wrapper.text()).toContain('核心创作 · 6')
    expect(wrapper.text()).toContain('阶段质检 · 7')
    expect(wrapper.text()).toContain('专家输出格式无效')
    expect(wrapper.text()).toContain('缺少参考图')
    expect(wrapper.text()).toContain('质量门返回模型调用超时，模型任务超时')
    expect(wrapper.text()).toContain('重新执行图像生成第 1 帧')
    expect(wrapper.text()).toContain('角色信息不完整：老李、王医生、张阿姨、小刘')
    expect(wrapper.text()).toContain('场景信息不完整：书房、公园步道、菜市场、家庭餐桌、厨房')
    expect(wrapper.text()).toContain('参考素材记录为空：角色参考、场景参考缺失')
    expect(wrapper.text()).toContain('角色面部一致性不足，正面和侧面参考之间不稳定；公园步道和厨房之间的场景光线发生跳变；镜头连续性缺少上一段结束帧状态')
    expect(wrapper.text()).toContain('请重新提交图像生成任务')
    expect(wrapper.text()).toContain('或创建合成交付兜底方案')
    expect(wrapper.text()).toContain('先重新生成角色锚定图，再进入图像生成；公园步道、厨房和家庭餐桌镜头保持暖色晨光')
    expect(wrapper.text()).toContain('重新执行图像生成，必要时启用合成交付兜底')
    expect(wrapper.text()).not.toMatch(/已记录异常结论|已记录审查发现|已记录返修要求|等待下一步处理/)
    expect(wrapper.text()).not.toMatch(/Prompt Engineer|short_video_editing_coach|reality_checker|现实检验者|storyboard|failed|Invalid JSON|Image Stage|Provider Worker|image_batch_running|waiting worker|Missing reference image|Retry provider worker|MODEL_TIMEOUT|provider task|timeout|image_stage|frame_01|provider_task_id|Open provider retry panel|技术标识|Characters|Scenes|Evidence trace|character_refs|scene_refs|empty_refs|incomplete|empty|fallback|\(,\s*,/)
  })

  it('keeps the 3D personified expert team as the expert tab', async () => {
    const wrapper = mount(AgencyConsolePage)
    await flushPromises()

    await wrapper.find('button[data-tab="experts"]').trigger('click')
    await vi.dynamicImportSettled()
    await flushPromises()

    expect(wrapper.text()).toContain('3D 专家人物化')
    expect(wrapper.text()).toContain('动漫制作工作室')
    expect(wrapper.text()).toContain('在房间里随机走动')
    expect(wrapper.text()).not.toContain('生产总览')
    expect(wrapper.text()).not.toContain('生产步骤')
    expect(wrapper.text()).not.toContain('Expert Team')
  })

  it('renders the director workbench tab and handles patch actions', async () => {
    routeState.query = { tab: 'workbench' }
    const wrapper = mount(AgencyConsolePage)
    await flushPromises()

    expect(listAgencyCreativePatches).toHaveBeenCalledWith({ series_id: 'sid', run_id: 'run-1' })
    expect(wrapper.text()).toContain('短视频导演台')
    expect(wrapper.text()).toContain('创作补丁')
    expect(wrapper.text()).toContain('强化前三秒钩子')
    expect(wrapper.text()).toContain('原画面')
    expect(wrapper.text()).toContain('新画面')

    await wrapper.find('textarea[data-field="image_prompt"]').setValue('人工调整后的画面')
    await wrapper.find('button[data-action="save"]').trigger('click')
    await flushPromises()
    await wrapper.find('button[data-action="approve"]').trigger('click')
    await flushPromises()
    await wrapper.find('button[data-action="apply"]').trigger('click')
    await flushPromises()

    expect(updateAgencyCreativePatch).toHaveBeenCalledWith('patch-1', { after: { image_prompt: '人工调整后的画面' } })
    expect(approveAgencyCreativePatch).toHaveBeenCalledWith('patch-1')
    expect(applyAgencyCreativePatch).toHaveBeenCalledWith('patch-1')
  })

  it('shows concrete auto-repair tasks and can retry them from the command center', async () => {
    const wrapper = mount(AgencyConsolePage)
    await flushPromises()

    expect(listAgencyRepairTasks).toHaveBeenCalledWith({
      series_id: 'sid',
      run_id: 'run-1',
      page: 1,
      page_size: 20,
    })
    const repairList = wrapper.find('[data-test="auto-repair-task-list"]')
    expect(repairList.exists()).toBe(true)
    expect(repairList.text()).toContain('图像阶段参考图缺失')
    expect(repairList.text()).toContain('去处理图像问题')

    await repairList.find('button').trigger('click')
    await flushPromises()

    expect(retryAgencyRepairTask).toHaveBeenCalledWith('repair-job-1')
  })

  it('can open the 3D expert map directly from the expert query tab', async () => {
    routeState.query = { tab: 'experts' }
    const wrapper = mount(AgencyConsolePage)
    await flushPromises()
    await vi.dynamicImportSettled()
    await flushPromises()

    expect(wrapper.text()).toContain('动漫制作工作室')
    expect(wrapper.text()).not.toContain('生产总览')
  })

  it('opens the expert drawer after selecting an expert', async () => {
    const wrapper = mount(AgencyConsolePage)
    await flushPromises()

    await wrapper.find('button[data-expert-id="prompt_engineer"]').trigger('click')
    await flushPromises()

    expect(getAgencyExpert).toHaveBeenCalledWith('prompt_engineer')
    expect(wrapper.text()).toContain('源文件')
    expect(wrapper.text()).toContain('负责把故事意图拆解为稳定提示词')
  })

  it('shows a Chinese empty state when no replayable trace exists', async () => {
    getAgencyConsole.mockResolvedValueOnce({
      data: {
        ok: true,
        series: { id: 'empty', title: '空白系列' },
        agency_trace_status: 'missing',
        expert_team: [],
        stage_graph: [],
        expert_invocations: [],
        decision_log: [],
        production_steps: [],
        creative_patch_summary: { total: 0, blocking: 0 },
        creative_patches: [],
      },
    })

    const wrapper = mount(AgencyConsolePage)
    await flushPromises()

    expect(wrapper.text()).toContain('暂无可回放的专家生产过程')
    expect(wrapper.text()).not.toMatch(/empty|missing|button/i)
  })

  it('shows a localized error instead of raw backend messages', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    getAgencyConsole.mockRejectedValueOnce({
      response: { data: { detail: 'Backend exploded: Cannot read properties of undefined' } },
    })

    const wrapper = mount(AgencyConsolePage)
    await flushPromises()

    expect(wrapper.text()).toContain('专家控制台加载失败，请稍后重试。')
    expect(wrapper.text()).not.toMatch(/Backend exploded|Cannot read properties|undefined/)
    expect(errorSpy).toHaveBeenCalled()
    errorSpy.mockRestore()
  })
})
