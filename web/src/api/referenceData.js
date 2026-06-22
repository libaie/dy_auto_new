// 前端 API 客户端：封装 referenceData 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// Category CRUD
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listCategories 对应业务流程的处理结果。
export function listCategories() { return client.get('/reference-categories') }
// 入参：data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createCategory 对应业务流程的处理结果。
export function createCategory(data) { return client.post('/reference-categories', data) }
// 前端业务函数：协调 updateCategory 对应的页面流程、接口调用或状态转换。
// 入参：id、data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updateCategory 对应业务流程的处理结果。
export function updateCategory(id, data) { return client.put(`/reference-categories/${id}`, data) }
// 前端业务函数：协调 deleteCategory 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 deleteCategory 对应业务流程的处理结果。
export function deleteCategory(id) { return client.delete(`/reference-categories/${id}`) }

// Item CRUD
// 前端业务函数：协调 listItems 对应的页面流程、接口调用或状态转换。
// 入参：category 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listItems 对应业务流程的处理结果。
export function listItems(category) { return client.get(`/reference-data/${category}`) }
// 前端业务函数：协调 listAllItems 对应的页面流程、接口调用或状态转换。
// 入参：category 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listAllItems 对应业务流程的处理结果。
export function listAllItems(category) { return client.get(`/reference-data/admin/${category}`) }
// 前端业务函数：协调 createItem 对应的页面流程、接口调用或状态转换。
// 入参：data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createItem 对应业务流程的处理结果。
export function createItem(data) { return client.post('/reference-data', data) }
// 前端业务函数：协调 updateItem 对应的页面流程、接口调用或状态转换。
// 入参：id、data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updateItem 对应业务流程的处理结果。
export function updateItem(id, data) { return client.put(`/reference-data/${id}`, data) }
// 前端业务函数：协调 deleteItem 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 deleteItem 对应业务流程的处理结果。
export function deleteItem(id) { return client.delete(`/reference-data/${id}`) }
