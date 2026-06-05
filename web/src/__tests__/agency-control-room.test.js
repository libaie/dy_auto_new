import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AgencyDecisionLog from '../components/agency/AgencyDecisionLog.vue'
import AgencyInvocationGraph from '../components/agency/AgencyInvocationGraph.vue'
import AgencyStageRail from '../components/agency/AgencyStageRail.vue'
import AgencyTeamMap2D from '../components/agency/AgencyTeamMap2D.vue'

const stages = [
  {
    stage: 'style_lock',
    label: '风格锁定',
    status: 'completed',
    reviewers: ['image_prompt_engineer'],
    lead: 'visual_storyteller',
    qa: ['style_lock_quality_reviewer'],
    invocation_ids: ['inv-0'],
  },
  {
    stage: 'storyboard',
    label: '分镜脚本',
    status: 'running',
    reviewers: ['visual_storyteller', 'short_video_editing_coach', 'douyin_strategist'],
    lead: 'narrative_designer',
    qa: ['storyboard_quality_reviewer'],
    invocation_ids: ['inv-1', 'inv-2'],
  },
]

const experts = [
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
]

describe('agency control room components', () => {
  it('renders current stage rail without exposing raw stage keys', () => {
    const wrapper = mount(AgencyStageRail, { props: { stages } })

    expect(wrapper.text()).toContain('风格锁定')
    expect(wrapper.text()).toContain('分镜脚本')
    expect(wrapper.text()).not.toMatch(/style_lock|storyboard/)
  })

  it('shows current stage graph topology and emits expert selection', async () => {
    const wrapper = mount(AgencyInvocationGraph, {
      props: {
        stages,
        expertTeam: experts,
        invocations: [
          {
            id: 'inv-1',
            stage: 'storyboard',
            expert_id: 'storyboard_quality_reviewer',
            role: 'qa',
            result_status: 'blocked',
            summary: '分镜缺少连续性说明',
          },
        ],
      },
    })

    expect(wrapper.text()).toContain('专家调用拓扑')
    expect(wrapper.text()).toContain('并行审阅')
    expect(wrapper.text()).toContain('主责汇总')
    expect(wrapper.text()).toContain('质量门禁')
    expect(wrapper.text()).toContain('分镜脚本质量审查专家')
    expect(wrapper.text()).not.toContain('reality_checker')

    await wrapper.find('button[data-expert-id="storyboard_quality_reviewer"]').trigger('click')
    expect(wrapper.emitted('selectExpert')?.[0]).toEqual(['storyboard_quality_reviewer'])
  })

  it('renders the 2D team map grouped by current role type', () => {
    const wrapper = mount(AgencyTeamMap2D, { props: { experts } })

    expect(wrapper.text()).toContain('专家席位地图')
    expect(wrapper.text()).toContain('14 位当前视频专家按阶段接力')
    expect(wrapper.text()).toContain('核心创作 · 6')
    expect(wrapper.text()).toContain('阶段质检 · 7')
    expect(wrapper.text()).toContain('优化支持 · 1')
    expect(wrapper.text()).toContain('提示词工程师')
    expect(wrapper.text()).toContain('风格锁定')
    expect(wrapper.text()).toContain('合成交付')
    expect(wrapper.text()).not.toContain('8 位视频专家')
    expect(wrapper.text()).not.toContain('现实检验者')
    expect(wrapper.text()).not.toContain('prompt_engineer')
  })

  it('renders decision log with current and historical QA review fields', () => {
    const wrapper = mount(AgencyDecisionLog, {
      props: {
        items: [
          {
            id: 'inv-1',
            invocation_id: 'inv-1',
            stage: 'storyboard',
            expert_id: 'storyboard_quality_reviewer',
            result_status: 'blocked',
            decision: 'blocked',
            findings: ['分镜缺少连续性说明'],
            required_changes: ['补全上一段结束状态'],
            evidence: ['shot-001: missing end frame'],
            next_action: '返回自动分镜修订',
            display_scope: 'current_team',
          },
          {
            id: 'legacy-1',
            invocation_id: 'legacy-1',
            stage: 'storyboard',
            expert_id: 'reality_checker',
            result_status: 'warn',
            decision: 'legacy note',
            legacy: true,
            display_scope: 'historical_audit',
          },
        ],
        expertTeam: experts,
        stages,
      },
    })

    expect(wrapper.text()).toContain('决策日志')
    expect(wrapper.text()).toContain('全部')
    expect(wrapper.text()).toContain('当前审查')
    expect(wrapper.text()).toContain('历史审计')
    expect(wrapper.findAll('button[data-filter-scope]').map(button => button.attributes('data-filter-scope'))).toEqual([
      'all',
      'current_team',
      'historical_audit',
    ])
    expect(wrapper.text()).toContain('分镜脚本质量审查专家')
    expect(wrapper.text()).toContain('发现：分镜缺少连续性说明')
    expect(wrapper.text()).toContain('必须修改：补全上一段结束状态')
    expect(wrapper.text()).toContain('证据：shot-001: missing end frame')
    expect(wrapper.text()).toContain('下一步：返回自动分镜修订')
    expect(wrapper.text()).toContain('历史审计记录')
    expect(wrapper.text()).not.toMatch(/prompt_engineer|storyboard_quality_reviewer|\{/)
  })
})
