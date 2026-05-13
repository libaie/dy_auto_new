export const TASK_TYPE_LABEL_MAP = {
  nurture: '养号',
  search_comment: '搜索评论',
  search_like: '搜索点赞',
  search_dm: '搜索私信',
  reply_comment: '评论回复',
  collect: '数据采集',
}

export const TASK_TYPE_OPTIONS = [
  { value: 'nurture', label: '养号' },
  { value: 'search_comment', label: '搜索评论' },
  { value: 'search_like', label: '搜索点赞' },
  { value: 'search_dm', label: '搜索私信' },
  { value: 'reply_comment', label: '评论回复' },
  { value: 'collect', label: '数据采集' },
]

export const STATUS_FILTER_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'pending', label: '待执行' },
  { value: 'running', label: '运行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
  { value: 'cancelled', label: '已取消' },
]

export const SUB_TASK_TYPE_OPTIONS = [
  { value: 'browse', label: '浏览' },
  { value: 'watch', label: '观看' },
  { value: 'like', label: '点赞' },
  { value: 'comment', label: '评论' },
  { value: 'follow', label: '关注' },
]

export const TASK_TABLE_COLUMNS = [
  { key: 'select', label: '', headerClass: 'w-8', cellClass: 'w-8' },
  { key: 'type', label: '任务类型', sortable: true },
  { key: 'keyword', label: '关键词' },
  { key: 'account_id', label: '账号ID' },
  { key: 'device_id', label: '执行设备' },
  { key: 'progress', label: '执行进度' },
  { key: 'status', label: '状态' },
  { key: 'created_at', label: '创建时间', sortable: true },
  { key: 'actions', label: '操作', headerClass: 'text-right', cellClass: 'text-right' },
]

export const KEYWORD_ACTION_TYPE_OPTIONS = [
  { value: 'search_comment', label: '搜索评论' },
  { value: 'search_like', label: '搜索点赞' },
  { value: 'search_dm', label: '搜索私信' },
  { value: 'reply_comment', label: '评论回复' },
  { value: 'collect', label: '数据采集' },
]

export const SORT_BY_OPTIONS = [
  { value: '', label: '默认排序' },
  { value: 'latest', label: '最新发布' },
  { value: 'most_liked', label: '最多点赞' },
]

export const NURTURE_DEFAULT_FORM = {
  type: 'nurture',
  account_id: '',
  device_id: '',
  keyword: '',
  content: '',
  count: 10,
  video_count: 5,  // reply_comment / search_comment / collect 共用
  sort_by: '',
  max_age_days: 5,
  duration: 30,
}
