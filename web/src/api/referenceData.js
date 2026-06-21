// 前端 API 客户端：封装 referenceData 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// Category CRUD
export function listCategories() { return client.get('/reference-categories') }
export function createCategory(data) { return client.post('/reference-categories', data) }
// 前端业务函数：协调 updateCategory 对应的页面流程、接口调用或状态转换。
export function updateCategory(id, data) { return client.put(`/reference-categories/${id}`, data) }
// 前端业务函数：协调 deleteCategory 对应的页面流程、接口调用或状态转换。
export function deleteCategory(id) { return client.delete(`/reference-categories/${id}`) }

// Item CRUD
// 前端业务函数：协调 listItems 对应的页面流程、接口调用或状态转换。
export function listItems(category) { return client.get(`/reference-data/${category}`) }
// 前端业务函数：协调 listAllItems 对应的页面流程、接口调用或状态转换。
export function listAllItems(category) { return client.get(`/reference-data/admin/${category}`) }
// 前端业务函数：协调 createItem 对应的页面流程、接口调用或状态转换。
export function createItem(data) { return client.post('/reference-data', data) }
// 前端业务函数：协调 updateItem 对应的页面流程、接口调用或状态转换。
export function updateItem(id, data) { return client.put(`/reference-data/${id}`, data) }
// 前端业务函数：协调 deleteItem 对应的页面流程、接口调用或状态转换。
export function deleteItem(id) { return client.delete(`/reference-data/${id}`) }
