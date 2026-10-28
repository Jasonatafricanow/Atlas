// The sole network boundary. Responses are never cached or retained here.
export async function read(route, params = {}, signal) {
  const query = new URLSearchParams(params);
  const response = await fetch(`/api/${route}?${query}`, {
    signal, cache: 'no-store', credentials: 'same-origin',
  });
  if (!response.ok) {
    const messages = {404: '记录不存在，或当前敏感设置下不可见。', 409: '记录或证据校验失败，未显示原文。', 503: '本地数据库暂不可读，请检查服务配置。'};
    throw new Error(messages[response.status] || '读取失败，请重试。');
  }
  return response.json();
}
