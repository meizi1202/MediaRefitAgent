<template>
  <aside class="sidebar">
    <div class="sidebar-expanded" v-show="!collapsed">
      <div class="sidebar-header">
        <div class="header-top">
          <span class="agent-name-text" @dblclick="startEdit">{{ agentName }}</span>
          <button class="collapse-btn" @click="$emit('collapse')">—</button>
        </div>
        <input
          v-if="editingName"
          ref="nameInput"
          v-model="agentName"
          class="agent-name-input"
          @blur="saveName"
          @keyup.enter="saveName"
        />
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
    </div>
    <div class="sidebar-collapsed-content" v-show="collapsed" @click="$emit('collapse')">
      <span class="expand-icon">☰</span>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue';
import { useSessions } from '../composables/useSessions';

defineProps<{ collapsed?: boolean }>();
defineEmits(['collapse']);

const { sessions, currentSessionId, createSession, selectSession, deleteSession } = useSessions();
const agentName = ref(localStorage.getItem('agentName') || 'MediaRefitAgent');
const editingName = ref(false);
const nameInput = ref<HTMLInputElement | null>(null);

function startEdit() {
  editingName.value = true;
  nextTick(() => nameInput.value?.focus());
}

function saveName() {
  editingName.value = false;
  localStorage.setItem('agentName', agentName.value);
}

onMounted(() => {
  agentName.value = localStorage.getItem('agentName') || 'MediaRefitAgent';
});

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
