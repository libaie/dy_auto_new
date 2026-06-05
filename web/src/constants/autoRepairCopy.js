const MOJIBAKE_PATTERN = /閿|闁|閻|閸|鐟|鐞|娓|锟|宸茶|瀹|鍥|瑙|绛|涓撳|杩斾慨|鍙傝/

export const AUTO_REPAIR_STATUS_LABELS = {
  queued: '等待返修',
  running: '正在返修',
  completed: '返修完成',
  failed: '返修失败',
  blocked: '需要人工处理',
  retry_wait: '等待重试',
  repair_recheck_pending: '等待复审',
  manual_required: '需要人工处理',
}

export const AUTO_REPAIR_TYPE_LABELS = {
  missing_character_reference: '角色参考图缺失',
  missing_scene_reference: '场景参考图缺失',
  storyboard_missing_references: '分镜参考信息缺失',
  image_generation_failed: '图像生成失败',
  image_generation_timeout: '图像生成超时',
  video_generation_failed: '视频生成失败',
  video_generation_timeout: '视频生成超时',
  provider_sync_required: '供应商结果需同步',
  manual_incomplete_repair_task: '需要人工确认',
}

export const AUTO_REPAIR_COPY = {
  summaryTitle: '自动返修',
  emptyTasks: '暂无自动返修任务',
  loadingTasks: '正在加载返修任务...',
  loadFailed: '返修任务加载失败，请稍后重试',
  noRoute: '暂无可跳转入口',
  originalFinding: '专家发现',
  repairAction: '返修动作',
  expectedResult: '预期结果',
  nextGate: '下一步',
  costImpact: '成本影响',
  noExtraCost: '不产生额外付费调用',
  recheckPending: '返修后仍需人工复审',
  retry: '重试返修',
  authorizeRetry: '确认追加预算并重试',
  manualAction: '去处理',
  policyTitle: '自动返修策略',
  policyEnabled: '允许系统自动处理确定性问题',
  policyDisabled: '仅记录建议，不自动返修',
  budgetLabel: '返修预算上限',
  paidRepairWarning: '涉及付费模型时会先检查预算，不会静默扣费。',
  allowedScope: '允许范围',
  showAll: '展开全部',
  collapse: '收起',
  paidConfirmTitle: '确认付费返修',
  paidConfirmBody: '该操作可能追加模型调用预算。确认后系统会重新校验预算、轮次和阶段权限，再提交返修任务。',
  paidConfirmReason: '确认原因',
  paidConfirmBudget: '追加预算',
  paidConfirmCancel: '取消',
  paidConfirmSubmit: '确认并重试',
  paidConfirmMissingReason: '请填写确认原因',
}

export function safeAutoRepairText(value, fallback = '信息待补充') {
  const text = String(value ?? '').trim()
  if (!text || MOJIBAKE_PATTERN.test(text)) return fallback
  return text
}

export function autoRepairStatusLabel(status) {
  return AUTO_REPAIR_STATUS_LABELS[String(status || '').toLowerCase()] || safeAutoRepairText(status, '未知状态')
}

export function autoRepairTypeLabel(type) {
  return AUTO_REPAIR_TYPE_LABELS[String(type || '').toLowerCase()] || safeAutoRepairText(type, '返修任务')
}

export function formatRepairCost(value) {
  const numberValue = Number(value || 0)
  if (!Number.isFinite(numberValue) || numberValue <= 0) return AUTO_REPAIR_COPY.noExtraCost
  return `预计 ${numberValue.toFixed(2)} 元`
}
