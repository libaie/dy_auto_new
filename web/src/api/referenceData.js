// 前端 API 客户端：封装 referenceData 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// Category CRUD
export function listCategories() { return client.get('/reference-categories') }
export function createCategory(data) { return client.post('/reference-categories', data) }
export function updateCategory(id, data) { return client.put(`/reference-categories/${id}`, data) }
export function deleteCategory(id) { return client.delete(`/reference-categories/${id}`) }

// Item CRUD
export function listItems(category) { return client.get(`/reference-data/${category}`) }
export function listAllItems(category) { return client.get(`/reference-data/admin/${category}`) }
export function createItem(data) { return client.post('/reference-data', data) }
export function updateItem(id, data) { return client.put(`/reference-data/${id}`, data) }
export function deleteItem(id) { return client.delete(`/reference-data/${id}`) }
