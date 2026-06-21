// 前端业务常量：集中维护 channels 相关中文文案、导航或状态枚举。
export const CHANNEL_TASK_TYPE_LABEL = {
  search_comment: '评论搜索',
  search_like: '点赞搜索',
  search_dm: '私信搜索',
  reply_comment: '回复评论',
  collect: '采集',
  nurture: '养号',
}

export const CHANNEL_STATUS_LABEL = {
  active: '运行中',
  paused: '已暂停',
  completed: '已完成',
  cancelled: '已取消',
}

export const CHANNEL_STATUS_CLASS = {
  active: 'bg-green-500/20 text-green-400',
  paused: 'bg-yellow-500/20 text-yellow-400',
  completed: 'bg-blue-500/20 text-blue-400',
  cancelled: 'bg-slate-600/50 text-slate-400',
}
