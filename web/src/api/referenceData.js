import client from './client.js'

export function listItems(category) { return client.get(`/reference-data/${category}`) }
export function listAllItems(category) { return client.get(`/reference-data/admin/${category}`) }
export function createItem(data) { return client.post('/reference-data', data) }
export function updateItem(id, data) { return client.put(`/reference-data/${id}`, data) }
export function deleteItem(id) { return client.delete(`/reference-data/${id}`) }
