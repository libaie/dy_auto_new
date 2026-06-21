// 专家团队业务组件：展示或操作专家团队、审查、返修和创意补丁相关业务状态。
const CORE_EXPERT_IDS = new Set([
  'story_generator',
  'narrative_designer',
  'visual_storyteller',
  'image_prompt_engineer',
  'prompt_engineer',
  'short_video_editing_coach',
  'douyin_strategist',
])

const QUALITY_EXPERT_IDS = new Set([
  'style_lock_quality_reviewer',
  'storyboard_quality_reviewer',
  'image_stage_quality_reviewer',
  'image_review_quality_reviewer',
  'video_stage_quality_reviewer',
  'video_review_quality_reviewer',
  'compose_quality_reviewer',
])

const SUPPORT_EXPERT_IDS = new Set([
  'video_optimization_specialist',
])

export const CURRENT_EXPERT_IDS = new Set([
  ...CORE_EXPERT_IDS,
  ...QUALITY_EXPERT_IDS,
  ...SUPPORT_EXPERT_IDS,
])

export const LEGACY_EXPERT_IDS = new Set(['reality_checker'])

export const EXPERT_NAMES = {
  story_generator: '故事生成专家',
  narrative_designer: '叙事设计师',
  visual_storyteller: '视觉叙事师',
  image_prompt_engineer: '图像提示词工程师',
  prompt_engineer: '提示词工程师',
  short_video_editing_coach: '短视频剪辑指导师',
  douyin_strategist: '抖音策略师',
  video_optimization_specialist: '视频优化专家',
  style_lock_quality_reviewer: '风格锁定质量审查专家',
  storyboard_quality_reviewer: '分镜脚本质量审查专家',
  image_stage_quality_reviewer: '图像生成质量审查专家',
  image_review_quality_reviewer: '图像结果质量审查专家',
  video_stage_quality_reviewer: '视频生成质量审查专家',
  video_review_quality_reviewer: '视频结果质量审查专家',
  compose_quality_reviewer: '合成交付质量审查专家',
  reality_checker: '历史审计角色',
}

export const EXPERT_AVATARS = {
  story_generator: '故',
  narrative_designer: '叙',
  visual_storyteller: '视',
  image_prompt_engineer: '图',
  prompt_engineer: '词',
  short_video_editing_coach: '剪',
  douyin_strategist: '抖',
  video_optimization_specialist: '优',
  style_lock_quality_reviewer: '风',
  storyboard_quality_reviewer: '镜',
  image_stage_quality_reviewer: '生',
  image_review_quality_reviewer: '审',
  video_stage_quality_reviewer: '频',
  video_review_quality_reviewer: '检',
  compose_quality_reviewer: '交',
  reality_checker: '史',
}

export const PHASE_LABELS = {
  story_planning: '故事规划',
  style_lock: '风格锁定',
  storyboard: '分镜脚本',
  image_stage: '图像生成',
  image_review: '图像审查',
  video_stage: '视频生成',
  video_review: '视频审查',
  compose: '合成交付',
  render: '画面生成',
  final_edit: '最终剪辑',
  image_generation: '图像生成',
  video_generation: '视频生成',
  compose_preflight: '合成预检',
  episode_compose: '成片合成',
}

export const STATUS_LABELS = {
  pending: '待执行',
  queued: '排队中',
  running: '运行中',
  in_progress: '运行中',
  completed: '已完成',
  complete: '轨迹完整',
  passed: '通过',
  pass: '通过',
  approved: '已通过',
  ready: '已就绪',
  warning: '有警告',
  warn: '有警告',
  partial: '部分记录',
  blocked: '已阻断',
  failed: '轨迹失败',
  failure: '轨迹失败',
  missing: '暂无记录',
  legacy_summary: '旧流程摘要',
  image_batch_running: '图像批次生成中',
  video_batch_running: '视频批次生成中',
  image_review_pending: '等待图像审查',
  video_review_pending: '等待视频审查',
  image_human_review_required: '等待人工图像审查',
  video_human_review_required: '等待人工视频审查',
  final_review_pending: '等待最终审查',
  review_pending: '等待审查',
  rejected: '审查未通过',
  regenerating: '正在重绘',
  retry_queued: '已加入重试队列',
  failed_retryable: '失败，可重试',
  composing: '合成中',
  submitted: '已提交',
  provider_submitted: '已提交模型任务',
  provider_running: '模型任务运行中',
  provider_succeeded: '模型任务已完成',
  provider_failed: '模型任务失败',
}

export const STEP_LABELS = {
  input: '输入系列一句话',
  style_lock: '风格锁定',
  auto_plan: '自动分镜',
  storyboard: '自动分镜',
  provider_worker: '模型任务执行',
  image_worker: '图像任务执行',
  video_worker: '视频任务执行',
  layer_0_assets: '第一层图像资产生成',
  layer_1_narration: '第二层旁白生成',
  layer_2_title: '第三层标题生成',
  layer_3_image_prompt: '第四层图像提示词生成',
  layer_4_render: '第五层视频渲染',
  layer_5_postproduction: '第六层后期剪辑',
  episode_writeback: '写回剧集',
  video_library_writeback: '写入视频资产库',
}

const ENGLISH_TEXT_LABELS = {
  'image stage': '\u56fe\u50cf\u751f\u6210',
  'video stage': '\u89c6\u9891\u751f\u6210',
  'provider worker': '\u6a21\u578b\u4efb\u52a1\u6267\u884c',
  'waiting worker result': '\u7b49\u5f85\u540e\u53f0\u4efb\u52a1\u8fd4\u56de\u7ed3\u679c',
  'missing reference image': '\u7f3a\u5c11\u53c2\u8003\u56fe',
  'retry provider worker': '\u91cd\u65b0\u63d0\u4ea4\u6a21\u578b\u4efb\u52a1',
  'invalid json': '\u4e13\u5bb6\u8f93\u51fa\u683c\u5f0f\u65e0\u6548',
  'open provider retry panel': '\u6253\u5f00\u6a21\u578b\u4efb\u52a1\u91cd\u8bd5\u5165\u53e3',
  timeout: '\u8d85\u65f6',
}

const EMBEDDED_ENGLISH_REPLACEMENTS = [
  { pattern: /\bMODEL_TIMEOUT\b/gi, label: '\u6a21\u578b\u8c03\u7528\u8d85\u65f6' },
  { pattern: /\bInvalid JSON\b/gi, label: '\u4e13\u5bb6\u8f93\u51fa\u683c\u5f0f\u65e0\u6548' },
  { pattern: /\bMissing reference image\b/gi, label: '\u7f3a\u5c11\u53c2\u8003\u56fe' },
  { pattern: /\bRetry provider worker\b/gi, label: '\u91cd\u65b0\u63d0\u4ea4\u6a21\u578b\u4efb\u52a1' },
  { pattern: /\bOpen provider retry panel\b/gi, label: '\u6253\u5f00\u6a21\u578b\u4efb\u52a1\u91cd\u8bd5\u5165\u53e3' },
  { pattern: /\bprovider task timeout\b/gi, label: '\u6a21\u578b\u4efb\u52a1\u8d85\u65f6' },
  { pattern: /\bprovider task\b/gi, label: '\u6a21\u578b\u4efb\u52a1' },
  { pattern: /\bprovider_worker\b/gi, label: '\u6a21\u578b\u4efb\u52a1\u6267\u884c' },
  { pattern: /\bimage_batch_running\b/gi, label: '\u56fe\u50cf\u6279\u6b21\u751f\u6210\u4e2d' },
  { pattern: /\bvideo_batch_running\b/gi, label: '\u89c6\u9891\u6279\u6b21\u751f\u6210\u4e2d' },
  { pattern: /\bstory_planning\b/gi, label: '\u6545\u4e8b\u89c4\u5212' },
  { pattern: /\bstyle_lock\b/gi, label: '\u98ce\u683c\u9501\u5b9a' },
  { pattern: /\bstoryboard\b/gi, label: '\u5206\u955c\u811a\u672c' },
  { pattern: /\bimage_stage\b/gi, label: '\u56fe\u50cf\u751f\u6210' },
  { pattern: /\bvideo_stage\b/gi, label: '\u89c6\u9891\u751f\u6210' },
  { pattern: /\bimage_review\b/gi, label: '\u56fe\u50cf\u5ba1\u67e5' },
  { pattern: /\bvideo_review\b/gi, label: '\u89c6\u9891\u5ba1\u67e5' },
  { pattern: /\bcompose_preflight\b/gi, label: '\u5408\u6210\u9884\u68c0' },
  { pattern: /\bcompose\b/gi, label: '\u5408\u6210\u4ea4\u4ed8' },
  { pattern: /\bframe[_-]?(\d+)\b/gi, label: (_, number) => '\u7b2c ' + Number(number) + ' \u5e27' },
  { pattern: /\bprovider_task_id\s*=\s*[A-Za-z0-9_-]+\b/gi, label: '\u6a21\u578b\u4efb\u52a1\u7f16\u53f7\u5df2\u8bb0\u5f55' },
  { pattern: /\btask[_-][A-Za-z0-9_-]+\b/gi, label: '\u4efb\u52a1\u7f16\u53f7\u5df2\u8bb0\u5f55' },
  { pattern: /\bfailed\b/gi, label: '\u5931\u8d25' },
  { pattern: /\berror\b/gi, label: '\u9519\u8bef' },
  { pattern: /\btimeout\b/gi, label: '\u8d85\u65f6' },
  { pattern: /\bworker\b/gi, label: '\u540e\u53f0\u4efb\u52a1' },
  { pattern: /\bprovider\b/gi, label: '\u6a21\u578b\u670d\u52a1' },
  { pattern: /\bBGM\b/g, label: '\u80cc\u666f\u97f3\u4e50' },
]

export const ROLE_GROUPS = {
  core: { key: 'core', label: '核心创作', detail: '叙事、视觉、提示词、剪辑与平台策略' },
  quality: { key: 'quality', label: '阶段质检', detail: '逐阶段质量门禁与返修判断' },
  support: { key: 'support', label: '优化支持', detail: '交付前优化与平台表现建议' },
}

export const ROLE_LABELS = {
  core: '核心专家',
  core_expert: '核心专家',
  primary: '核心专家',
  support: '支持专家',
  optimization: '优化支持',
  lead: '主责汇总',
  leader: '主责汇总',
  owner: '主责汇总',
  responsible: '主责汇总',
  reviewer: '并行审阅',
  reviewers: '并行审阅',
  review: '并行审阅',
  qa: '质量门禁',
  quality: '质量门禁',
  quality_assurance: '质量门禁',
  quality_gate: '质量门禁',
}

export const SKILL_TEXT = {
  story_generator: '负责整季故事主线、单集剧情卡、跨集伏笔和人物状态连续性。',
  narrative_designer: '负责叙事结构、角色动机、情绪推进和跨镜头故事连续性。',
  visual_storyteller: '负责视觉叙事、镜头语言、场景氛围和锁定风格一致性。',
  image_prompt_engineer: '负责文生图提示词、角色锚定图和视觉参考图组织。',
  prompt_engineer: '负责把故事意图拆解为稳定提示词，控制角色、场景和风格一致性。',
  short_video_editing_coach: '负责镜头节奏、时长拆分、剪辑包装和多镜头叙事连贯性。',
  douyin_strategist: '负责平台节奏、开场钩子、完播率判断和内容传播策略。',
  video_optimization_specialist: '负责完播率、章节节奏、封面标题和视频投放优化。',
  style_lock_quality_reviewer: '审查角色锚定、场景规则、视觉美学、字幕与声音包装是否完整可继承。',
  storyboard_quality_reviewer: '审查分镜是否具备场景、人物、动作、情绪、时长和连续性说明。',
  image_stage_quality_reviewer: '审查图像生成输入是否绑定角色参考、场景参考和统一美学约束。',
  image_review_quality_reviewer: '审查图像结果是否满足角色一致、场景正确、画面可用和返修条件。',
  video_stage_quality_reviewer: '审查视频生成输入是否包含起止帧、镜头动作、时长和跨段连续性。',
  video_review_quality_reviewer: '审查视频结果是否存在走样、闪烁、动作断裂和不可合成风险。',
  compose_quality_reviewer: '审查最终合成是否满足字幕、BGM、片头片尾、水印和输出规格。',
  reality_checker: '历史审计角色，仅用于查看旧流程记录，不参与当前视频生成编排。',
}

export function isLegacyExpert(id) {
  return LEGACY_EXPERT_IDS.has(id)
}

export function isCurrentExpert(id) {
  return CURRENT_EXPERT_IDS.has(id)
}

export function isRawIdentifier(value) {
  return /^[a-z][a-z0-9_]{2,}$/.test(String(value || ''))
}

export function expertName(id, fallback = '') {
  const fallbackLabel = localizedText(fallback, '')
  if (fallbackLabel) return fallbackLabel
  return EXPERT_NAMES[id] || '未命名专家'
}

export function expertAvatar(id) {
  return EXPERT_AVATARS[id] || '专'
}

export function phaseLabel(phase, fallback = '') {
  const key = String(phase || '').trim()
  if (PHASE_LABELS[key]) return PHASE_LABELS[key]
  const fallbackLabel = localizedText(fallback, '')
  if (fallbackLabel) return fallbackLabel
  return PHASE_LABELS[phase] || '未命名阶段'
}

export function statusLabel(status) {
  const key = String(status || '').trim().toLowerCase()
  return STATUS_LABELS[key] || '未知状态'
}

export function stepName(step = {}) {
  const id = String(step.id || '').trim()
  if (STEP_LABELS[id]) return STEP_LABELS[id]
  return localizedText(step.label, '已记录生产步骤')
}

export function phaseText(phases) {
  const values = Array.isArray(phases) ? phases : [phases]
  const labels = values
    .filter(Boolean)
    .map(phase => typeof phase === 'object' ? phaseLabel(phase.stage || phase.id, phase.label) : phaseLabel(phase))
  return labels.length ? labels.join(' / ') : '待配置阶段'
}

export function expertRoleGroup(expert) {
  const explicit = String(expert?.role_type || '').toLowerCase()
  if (['core', 'quality', 'support'].includes(explicit)) return explicit
  const id = expert?.expert_id || expert
  if (QUALITY_EXPERT_IDS.has(id)) return 'quality'
  if (SUPPORT_EXPERT_IDS.has(id)) return 'support'
  return 'core'
}

export function roleLabel(role) {
  return ROLE_LABELS[String(role || '').toLowerCase()] || ''
}

export function skillText(expert) {
  return safeDisplayText(
    expert?.skill_summary || expert?.description || SKILL_TEXT[expert?.expert_id],
    SKILL_TEXT[expert?.expert_id] || '负责阶段判断、内容审查与生产交接。'
  )
}

export function safeDisplayText(value, fallback = '已记录专家结论') {
  if (value === null || value === undefined || value === '') return fallback
  const text = Array.isArray(value) ? value.join('；') : String(value)
  if (!text.trim()) return fallback
  if (/^\{|\[object Object\]/.test(text)) return fallback
  if (/^[a-z][a-z0-9_]{2,}$/i.test(text)) return fallback
  const mapped = localizedText(text, '')
  if (mapped) return mapped
  const localized = localizeEmbeddedEnglish(text)
  if (localized) return localized
  if (/[A-Za-z_]/.test(text)) return fallback
  if (/^[\x00-\x7F]+$/.test(text) && /[A-Za-z]/.test(text)) return fallback
  return text
}

export function decisionLogText(value, field = 'generic', fallback = '') {
  if (value === null || value === undefined || value === '') return fallback
  const text = String(value).trim()
  if (!text) return fallback

  const exact = localizedText(text, '')
  if (exact) return compactChineseText(exact)

  const domain = decisionDomainText(text, field)
  if (domain) return domain

  const localized = localizeEmbeddedEnglish(text)
  if (localized) return compactChineseText(localized)

  if (field === 'evidence') return compactChineseText(text) || fallback
  if (/[A-Za-z_]/.test(text)) return fallback
  return compactChineseText(text) || fallback
}

export function localizedText(value, fallback = '') {
  if (value === null || value === undefined || value === '') return fallback
  const text = String(value).trim()
  if (!text) return fallback
  const lower = text.toLowerCase()
  if (PHASE_LABELS[text]) return PHASE_LABELS[text]
  if (STATUS_LABELS[lower]) return STATUS_LABELS[lower]
  if (STEP_LABELS[text]) return STEP_LABELS[text]
  if (ENGLISH_TEXT_LABELS[lower]) return ENGLISH_TEXT_LABELS[lower]
  if (/^[a-z][a-z0-9_]{2,}$/i.test(text)) return fallback
  if (/^[\x00-\x7F]+$/.test(text) && /[A-Za-z]/.test(text)) return fallback
  const localized = localizeEmbeddedEnglish(text)
  if (localized) return localized
  if (/[A-Za-z_]/.test(text)) return fallback
  return text
}

export function localizeEmbeddedEnglish(value) {
  const original = String(value || '')
  if (!original || !/[A-Za-z_]/.test(original)) return ''
  let text = original
  let knownReplacementApplied = false
  EMBEDDED_ENGLISH_REPLACEMENTS.forEach(({ pattern, label }) => {
    text = text.replace(pattern, (...args) => {
      knownReplacementApplied = true
      return typeof label === 'function' ? label(...args) : label
    })
  })
  if (!knownReplacementApplied) return ''
  if (/[A-Za-z_]/.test(text)) return ''
  text = text
    .replace(/\b[A-Z][A-Z0-9_]{2,}\b/g, '')
    .replace(/\b[a-z]+(?:[_-][a-z0-9]+)+\b/gi, '')
    .replace(/\b[A-Za-z][A-Za-z0-9./:-]{2,}\b/g, '')
    .replace(/\b[a-z]{1,2}\b/gi, '')
    .replace(/\(\s*[,，、；;\s]*\)/g, '')
    .replace(/[（(]\s*[）)]/g, '')
    .replace(/[,，、；;：:。.]{2,}/g, '；')
    .replace(/^[\s,，、；;：:。.()（）]+|[\s,，、；;：:。.()（）]+$/g, '')
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+([，。；：、])/g, '$1')
    .replace(/([，；：、])\s+/g, '$1')
    .trim()
  if (!text || text === original) return ''
  if (/[A-Za-z_]/.test(text)) return ''
  const chineseCount = (text.match(/[\u4e00-\u9fff]/g) || []).length
  return chineseCount >= 4 ? text : ''
}

function decisionDomainText(text, field) {
  const lower = text.toLowerCase()
  if (lower.includes('invalid json')) return '\u4e13\u5bb6\u8f93\u51fa\u683c\u5f0f\u65e0\u6548'
  if (lower.includes('missing reference image')) return '\u7f3a\u5c11\u53c2\u8003\u56fe'
  if (lower.includes('retry provider worker')) return '\u91cd\u65b0\u63d0\u4ea4\u6a21\u578b\u4efb\u52a1'
  if (lower.includes('open provider retry panel')) return '\u6253\u5f00\u6a21\u578b\u4efb\u52a1\u91cd\u8bd5\u5165\u53e3'
  if (lower.includes('provider_task_id')) {
    const stage = lower.includes('image_stage') ? '\u56fe\u50cf\u751f\u6210' : lower.includes('video_stage') ? '\u89c6\u9891\u751f\u6210' : ''
    return stage ? '\u6a21\u578b\u4efb\u52a1\u7f16\u53f7\u5df2\u8bb0\u5f55\uff0c\u5173\u8054' + stage + '\u9636\u6bb5' : '\u6a21\u578b\u4efb\u52a1\u7f16\u53f7\u5df2\u8bb0\u5f55'
  }
  if (lower.includes('characters') && lower.includes('incomplete')) {
    const names = extractParenthesizedChineseList(text)
    return names.length ? '\u89d2\u8272\u4fe1\u606f\u4e0d\u5b8c\u6574\uff1a' + names.join('\u3001') : '\u89d2\u8272\u4fe1\u606f\u4e0d\u5b8c\u6574'
  }
  if (lower.includes('scenes')) {
    const names = extractParenthesizedChineseList(text)
    return names.length ? '\u573a\u666f\u4fe1\u606f\u4e0d\u5b8c\u6574\uff1a' + names.join('\u3001') : '\u573a\u666f\u4fe1\u606f\u4e0d\u5b8c\u6574'
  }
  if (lower.includes('evidence trace') || lower.includes('character_refs') || lower.includes('scene_refs') || lower.includes('empty_refs')) {
    return field === 'evidence' ? '\u53c2\u8003\u7d20\u6750\u7f3a\u5931\u8bc1\u636e\u5df2\u8bb0\u5f55' : '\u53c2\u8003\u7d20\u6750\u8bb0\u5f55\u4e3a\u7a7a\uff1a\u89d2\u8272\u53c2\u8003\u3001\u573a\u666f\u53c2\u8003\u7f3a\u5931'
  }
  const detailed = translateDetailedEnglishText(text)
  if (detailed) return detailed
  if (lower.includes('add a provider task') && lower.includes('image_stage')) return '\u8bf7\u91cd\u65b0\u63d0\u4ea4\u56fe\u50cf\u751f\u6210\u4efb\u52a1'
  if (lower.includes('compose fallback')) {
    if (lower.includes('worker') || lower.includes('retry')) return '\u91cd\u65b0\u6267\u884c\u56fe\u50cf\u751f\u6210\uff0c\u5fc5\u8981\u65f6\u542f\u7528\u5408\u6210\u4ea4\u4ed8\u515c\u5e95'
    return '\u6216\u521b\u5efa\u5408\u6210\u4ea4\u4ed8\u515c\u5e95\u65b9\u6848'
  }
  if (lower.includes('provider task timeout')) return '\u6a21\u578b\u4efb\u52a1\u8d85\u65f6'
  if (lower.includes('model_timeout')) return '\u6a21\u578b\u8c03\u7528\u8d85\u65f6'
  return ''
}

function translateDetailedEnglishText(text) {
  const clauses = String(text || '')
    .split(/[.;]\s*/)
    .map(item => item.trim())
    .filter(Boolean)
  if (!clauses.length) return ''

  const translated = clauses.map(translateEnglishClause).filter(Boolean)
  if (!translated.length || translated.length !== clauses.length) return ''
  return translated.join('\uff1b')
}

function translateEnglishClause(clause) {
  const lower = clause.toLowerCase()
  if (lower.includes('character face consistency') && lower.includes('front/profile')) {
    return '\u89d2\u8272\u9762\u90e8\u4e00\u81f4\u6027\u4e0d\u8db3\uff0c\u6b63\u9762\u548c\u4fa7\u9762\u53c2\u8003\u4e4b\u95f4\u4e0d\u7a33\u5b9a'
  }
  if (lower.includes('scene lighting shifts') && lower.includes('park walkway') && lower.includes('kitchen')) {
    return '\u516c\u56ed\u6b65\u9053\u548c\u53a8\u623f\u4e4b\u95f4\u7684\u573a\u666f\u5149\u7ebf\u53d1\u751f\u8df3\u53d8'
  }
  if (lower.includes('shot continuity') && lower.includes('previous end-frame state')) {
    return '\u955c\u5934\u8fde\u7eed\u6027\u7f3a\u5c11\u4e0a\u4e00\u6bb5\u7ed3\u675f\u5e27\u72b6\u6001'
  }
  if (lower.includes('regenerate character anchor images') && lower.includes('image generation')) {
    const actions = ['\u5148\u91cd\u65b0\u751f\u6210\u89d2\u8272\u951a\u5b9a\u56fe\uff0c\u518d\u8fdb\u5165\u56fe\u50cf\u751f\u6210']
    if (lower.includes('warm morning light') && lower.includes('park walkway') && lower.includes('kitchen') && lower.includes('dining table')) {
      actions.push('\u516c\u56ed\u6b65\u9053\u3001\u53a8\u623f\u548c\u5bb6\u5ead\u9910\u684c\u955c\u5934\u4fdd\u6301\u6696\u8272\u6668\u5149')
    }
    return actions.join('\uff1b')
  }
  if (lower.includes('warm morning light') && lower.includes('park walkway') && lower.includes('kitchen') && lower.includes('dining table')) {
    return '\u516c\u56ed\u6b65\u9053\u3001\u53a8\u623f\u548c\u5bb6\u5ead\u9910\u684c\u955c\u5934\u4fdd\u6301\u6696\u8272\u6668\u5149'
  }
  if (lower.includes('keep') && lower.includes('consistent')) {
    return clauseWithKnownTerms(clause, '\u4fdd\u6301\u4e00\u81f4')
  }
  return ''
}

function clauseWithKnownTerms(clause, fallback) {
  const terms = []
  const lower = clause.toLowerCase()
  if (lower.includes('character')) terms.push('\u89d2\u8272')
  if (lower.includes('scene')) terms.push('\u573a\u666f')
  if (lower.includes('lighting')) terms.push('\u5149\u7ebf')
  if (lower.includes('style')) terms.push('\u98ce\u683c')
  if (lower.includes('prompt')) terms.push('\u63d0\u793a\u8bcd')
  if (lower.includes('image')) terms.push('\u56fe\u50cf')
  if (lower.includes('video')) terms.push('\u89c6\u9891')
  if (lower.includes('reference')) terms.push('\u53c2\u8003')
  if (lower.includes('face')) terms.push('\u9762\u90e8')
  if (lower.includes('shot')) terms.push('\u955c\u5934')
  if (lower.includes('continuity')) terms.push('\u8fde\u7eed\u6027')
  return terms.length ? terms.join('\u3001') + fallback : ''
}

function extractParenthesizedChineseList(text) {
  const match = String(text).match(/[\uff08(]([^()\uff08\uff09]+)[\uff09)]/)
  if (!match) return []
  return match[1]
    .split(/[,\uff0c\u3001]/)
    .map(item => item.trim())
    .filter(item => /[\u4e00-\u9fff]/.test(item))
}

function compactChineseText(value) {
  return String(value || '')
    .replace(/\s*第\s*(\d+)\s*帧/g, '第 $1 帧')
    .replace(/([\u4e00-\u9fff])\s+([\u4e00-\u9fff])/g, '$1$2')
    .replace(/\s+([，。；：、])/g, '$1')
    .replace(/([，。；：、])\s+/g, '$1')
    .replace(/，+/g, '，')
    .replace(/；+/g, '；')
    .replace(/：+/g, '：')
    .replace(/([，；：、])$/g, '')
    .trim()
}
