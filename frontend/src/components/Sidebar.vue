<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <button class="new-chat-btn" @click="handleNewChat">+ 新建会话</button>
    </div>
    <div class="sessions-list">
      <div
        v-for="session in sessions"
        :key="session.session_id"
        class="session-item"
        :class="{ active: session.session_id === currentSessionId }"
        @click="handleSelectSession(session.session_id)"
      >
        <span class="icon">💬</span>
        <span class="name">{{ session.name || session.session_id }}</span>
        <span class="delete" @click.stop="handleDelete(session.session_id)">✕</span>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { useSessions } from '../composables/useSessions';

const { sessions, currentSessionId, createSession, selectSession, deleteSession } = useSessions();

function handleNewChat() {
  createSession();
}

function handleSelectSession(sessionId: string) {
  selectSession(sessionId);
}

function handleDelete(sessionId: string) {
  deleteSession(sessionId);
}
</script>
