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
