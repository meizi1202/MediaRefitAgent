import { api } from '../api';
import { useAppStore } from '../stores/app';
import type { Message, Session } from '../types';

export function useSessions() {
  const store = useAppStore();

  async function loadSessions() {
    try {
      const data = await api.getSessions();
      store.sessions = data.sessions || [];
    } catch (e) {
      console.error('Failed to load sessions:', e);
    }
  }

  function createSession(): Session {
    // 使用 UUID 作为会话 ID，保持前后端一致
    const session_id = crypto.randomUUID();
    const session: Session = {
      session_id,
      name: '新会话',
      messages: [],
      created: new Date().toISOString(),
    };
    store.addSession(session);
    store.setCurrentSession(session.session_id);
    return session;
  }

  async function selectSession(sessionId: string) {
    store.setCurrentSession(sessionId);
    const session = store.sessions.find(s => s.session_id === sessionId);
    if (session && session.messages.length === 0) {
      try {
        const data = await api.getSession(sessionId);
        store.updateSession(sessionId, { messages: data.messages || [] });
      } catch (e) {
        console.error('Failed to load session:', e);
      }
    }
  }

  async function deleteSession(sessionId: string) {
    try {
      await api.deleteSession(sessionId);
    } catch (e) {
      console.error('Failed to delete session:', e);
    }
    store.removeSession(sessionId);
  }

  function addMessage(sessionId: string, message: Message) {
    store.addMessage(sessionId, message);
    // 如果是用户消息且会话名称是默认名称，则自动命名为消息内容
    if (message.role === 'user') {
      const updatedSession = store.sessions.find(s => s.session_id === sessionId);
      if (updatedSession && updatedSession.name === '新会话') {
        const name = message.content.slice(0, 30) + (message.content.length > 30 ? '...' : '');
        store.updateSession(sessionId, { name });
      }
    }
  }

  function renameSession(sessionId: string, name: string) {
    store.updateSession(sessionId, { name });
  }

  return {
    sessions: store.sessions,
    currentSessionId: store.currentSessionId,
    currentSession: store.currentSession,
    currentMessages: store.currentMessages,
    loadSessions,
    createSession,
    selectSession,
    deleteSession,
    addMessage,
    renameSession,
  };
}
