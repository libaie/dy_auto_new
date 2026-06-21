// 前端 API 客户端：封装 channels 相关后端接口，统一给页面和组件调用。
import client from './client';

export function listChannels() {
  return client.get('/channels');
}

export function getChannel(id) {
  return client.get(`/channels/${id}`);
}

export function createChannel(data) {
  return client.post('/channels', data);
}

export function updateChannel(id, data) {
  return client.patch(`/channels/${id}`, data);
}

export function deleteChannel(id) {
  return client.delete(`/channels/${id}`);
}

export function appendChannelItems(id, keywords) {
  return client.post(`/channels/${id}/items`, { keywords });
}

export function updateChannelItem(channelId, itemId, data) {
  return client.patch(`/channels/${channelId}/items/${itemId}`, data);
}

export function editChannelMeta(id, data) {
  return client.put(`/channels/${id}`, data);
}

export function editChannelItem(itemId, data) {
  return client.put(`/channels/items/${itemId}`, data);
}

export function batchEditItems(data) {
  return client.put('/channels/items/batch', data);
}
