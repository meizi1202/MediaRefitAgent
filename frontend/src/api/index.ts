import type { VideoResult } from '../types';

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
  async transform(formData: FormData): Promise<VideoResult> {
    return fetchJson(`${API_BASE}/transform`, { method: 'POST', body: formData });
  },

  async compress(formData: FormData): Promise<VideoResult> {
    return fetchJson(`${API_BASE}/compress`, { method: 'POST', body: formData });
  },

  async trim(formData: FormData): Promise<VideoResult> {
    return fetchJson(`${API_BASE}/trim`, { method: 'POST', body: formData });
  },

  async concat(formData: FormData): Promise<VideoResult> {
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
