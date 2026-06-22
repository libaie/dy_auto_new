// 前端业务工具：封装 format 相关格式化或轻量转换逻辑。
// 前端业务函数：协调 formatDate 对应的页面流程、接口调用或状态转换。
// 入参：dateStr 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 formatDate 对应业务流程的处理结果。
export function formatDate(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Shanghai',
  })
}
