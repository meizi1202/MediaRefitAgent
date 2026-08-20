const API_BASE = '/api';

async function fetchJson(url: string, options?: RequestInit): Promise<any> {
  const resp = await fetch(url, options);
  return resp.json();
}

export const api = {
  // ========== Agent ==========
  async agentChat(formData: FormData) {
    const resp = await fetch(`${API_BASE}/agent/chat`, { method: 'POST', body: formData });
    const text = await resp.text();
    if (!resp.ok) {
      throw new Error(text);
    }
    return JSON.parse(text);
  },

  // 流式聊天
  agentChatStream(
    formData: FormData,
    onMessage: (content: string) => void,
    onDone: (data: any) => void,
    onError: (err: string) => void
  ) {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_BASE}/agent/chat-stream`);

    // 记录已处理的字符位置
    let lastCharIndex = 0;

    xhr.onprogress = () => {
      const text = xhr.responseText;
      const currentLen = text.length;

      // 从上次处理到的位置继续，只处理新增的部分
      if (lastCharIndex >= currentLen) return;

      // 找到下一个 data: 位置
      let startIdx = text.indexOf('data: ', lastCharIndex);
      if (startIdx === -1) {
        lastCharIndex = currentLen;
        return;
      }

      // 找到这行的结束位置（换行符）
      let endIdx = text.indexOf('\n', startIdx);
      if (endIdx === -1) endIdx = currentLen;

      // 提取并处理这条数据
      const line = text.slice(startIdx, endIdx).trim();
      if (line.startsWith('data: ')) {
        const jsonStr = line.slice(6);
        try {
          const data = JSON.parse(jsonStr);
          if (data.event === 'message') {
            onMessage(data.answer || '');
          } else if (data.event === 'message_end') {
            onDone(data);
          } else if (data.event === 'error') {
            onError(data.error || data.message);
          }
        } catch (e) {
          // 忽略解析错误
        }
      }

      lastCharIndex = endIdx;
    };

    xhr.onerror = () => onError('Network error');
    xhr.onload = () => {
      if (xhr.status !== 200) {
        onError(xhr.statusText);
      }
    };

    xhr.send(formData);
    return xhr;
  },

  async agentContinue(sessionId: string, message: string) {
    return fetchJson(`${API_BASE}/agent/continue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message }),
    });
  },

  async getSessions() {
    return fetchJson(`${API_BASE}/agent/sessions`);
  },

  async getSession(sessionId: string) {
    return fetchJson(`${API_BASE}/agent/session/${sessionId}`);
  },

  async deleteSession(sessionId: string) {
    return fetch(`${API_BASE}/agent/session/${sessionId}`, { method: 'DELETE' });
  },

  // ========== 视频操作 ==========
  async transform(formData: FormData): Promise<any> {
    return fetchJson(`${API_BASE}/transform`, { method: 'POST', body: formData });
  },

  async compress(formData: FormData): Promise<any> {
    return fetchJson(`${API_BASE}/compress`, { method: 'POST', body: formData });
  },

  async trim(formData: FormData): Promise<any> {
    return fetchJson(`${API_BASE}/trim`, { method: 'POST', body: formData });
  },

  async concat(formData: FormData): Promise<any> {
    return fetchJson(`${API_BASE}/concat`, { method: 'POST', body: formData });
  },

  async videoInfo(formData: FormData) {
    return fetchJson(`${API_BASE}/video-info`, { method: 'POST', body: formData });
  },

  async condense(formData: FormData) {
    return fetchJson(`${API_BASE}/condense`, { method: 'POST', body: formData });
  },

  async restore(formData: FormData) {
    return fetchJson(`${API_BASE}/restore`, { method: 'POST', body: formData });
  },

  // ========== 系统 ==========
  async capabilities() {
    return fetchJson(`${API_BASE}/capabilities`);
  },

  async listOutputs() {
    return fetchJson(`${API_BASE}/outputs`);
  },

  async health() {
    return fetchJson(`${API_BASE}/health`);
  },

  // ========== 下载 ==========
  getDownloadUrl(filename: string) {
    return `${API_BASE}/download/${filename}`;
  },

  getFullUrl(path: string) {
    if (path.startsWith('http')) return path;
    return `${API_BASE}${path}`;
  },
};
