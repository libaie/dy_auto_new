// 前端 API 客户端：封装 selectors 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listSelectors(includeDisabled = false, category = '') {
  return client.get('/selectors', { params: { include_disabled: includeDisabled, category: category || undefined } })
}

// 前端业务函数：协调 createSelector 对应的页面流程、接口调用或状态转换。
export function createSelector(data) {
  return client.post('/selectors', data)
}

// 前端业务函数：协调 updateSelector 对应的页面流程、接口调用或状态转换。
export function updateSelector(actionName, data) {
  return client.put(`/selectors/${actionName}`, data)
}

// 前端业务函数：协调 deleteSelector 对应的页面流程、接口调用或状态转换。
export function deleteSelector(actionName, platformVersion, resolutionProfile) {
  var params = {}
  if (platformVersion) params.platform_version = platformVersion
  if (resolutionProfile) params.resolution_profile = resolutionProfile
  return client.delete(`/selectors/${actionName}`, { params })
}

// 前端业务函数：协调 toggleSelector 对应的页面流程、接口调用或状态转换。
export function toggleSelector(actionName, enabled, platformVersion, resolutionProfile) {
  var params = {}
  if (platformVersion) params.platform_version = platformVersion
  if (resolutionProfile) params.resolution_profile = resolutionProfile
  return client.patch(`/selectors/${actionName}/toggle`, { enabled }, { params })
}

// 前端业务函数：协调 uploadTemplate 对应的页面流程、接口调用或状态转换。
export function uploadTemplate(file, actionName, resolution = 'default') {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('action_name', actionName)
  return client.post('/selectors/templates/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params: { resolution: resolution || 'default' },
  })
}

// 前端业务函数：协调 listTemplates 对应的页面流程、接口调用或状态转换。
export function listTemplates() {
  return client.get('/selectors/templates')
}

// 前端业务函数：协调 deleteTemplate 对应的页面流程、接口调用或状态转换。
export function deleteTemplate(filename) {
  return client.delete(`/selectors/templates/${filename}`)
}
// 前端业务函数：协调 generateRegex 对应的页面流程、接口调用或状态转换。
export function generateRegex(description) {
  return client.post('/content/generate-regex', { description })
}

// 前端业务函数：协调 generateCleanPrompt 对应的页面流程、接口调用或状态转换。
export function generateCleanPrompt(description) {
  return client.post('/content/generate-clean-prompt', { description })
}
