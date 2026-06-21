// 前端 API 客户端：封装 channels 相关后端接口，统一给页面和组件调用。
import client from './client';

export function listChannels() {
  return client.get('/channels');
}

// 前端业务函数：协调 getChannel 对应的页面流程、接口调用或状态转换。
export function getChannel(id) {
  return client.get(`/channels/${id}`);
}

// 前端业务函数：协调 createChannel 对应的页面流程、接口调用或状态转换。
export function createChannel(data) {
  return client.post('/channels', data);
}

// 前端业务函数：协调 updateChannel 对应的页面流程、接口调用或状态转换。
export function updateChannel(id, data) {
  return client.patch(`/channels/${id}`, data);
}

// 前端业务函数：协调 deleteChannel 对应的页面流程、接口调用或状态转换。
export function deleteChannel(id) {
  return client.delete(`/channels/${id}`);
}

// 前端业务函数：协调 appendChannelItems 对应的页面流程、接口调用或状态转换。
export function appendChannelItems(id, keywords) {
  return client.post(`/channels/${id}/items`, { keywords });
}

// 前端业务函数：协调 updateChannelItem 对应的页面流程、接口调用或状态转换。
export function updateChannelItem(channelId, itemId, data) {
  return client.patch(`/channels/${channelId}/items/${itemId}`, data);
}

// 前端业务函数：协调 editChannelMeta 对应的页面流程、接口调用或状态转换。
export function editChannelMeta(id, data) {
  return client.put(`/channels/${id}`, data);
}

// 前端业务函数：协调 editChannelItem 对应的页面流程、接口调用或状态转换。
export function editChannelItem(itemId, data) {
  return client.put(`/channels/items/${itemId}`, data);
}

// 前端业务函数：协调 batchEditItems 对应的页面流程、接口调用或状态转换。
export function batchEditItems(data) {
  return client.put('/channels/items/batch', data);
}
