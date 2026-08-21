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
          v-for="session in store.sessions"
          :key="session.session_id"
          class="session-item"
          :class="{ active: session.session_id === store.currentSessionId }"
          @click="handleSelectSession(session.session_id)"
        >
          <span class="session-icon">💬</span>
          <template v-if="editingSessionId === session.session_id">
            <input
              ref="sessionNameInput"
              v-model="editingSessionName"
              class="session-name-input"
              @blur="saveSessionName(session.session_id)"
              @keyup.enter="saveSessionName(session.session_id)"
              @keyup.escape="cancelEditSession"
            />
          </template>
          <template v-else>
            <span class="name" @dblclick="startEditSession(session)" :title="session.name">
              {{ session.name || session.session_id }}
            </span>
          </template>
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
import { useAppStore } from '../stores/app';

defineProps<{ collapsed?: boolean }>();
defineEmits(['collapse']);

const store = useAppStore();
const { createSession, selectSession, deleteSession, renameSession } = useSessions();

const agentName = ref(localStorage.getItem('agentName') || 'MediaRefitAgent');
const editingName = ref(false);
const nameInput = ref<HTMLInputElement | null>(null);

// 会话名称编辑状态
const editingSessionId = ref<string | null>(null);
const editingSessionName = ref('');
const sessionNameInput = ref<HTMLInputElement | null>(null);

function startEdit() {
  editingName.value = true;
  nextTick(() => nameInput.value?.focus());
}

function saveName() {
  editingName.value = false;
  localStorage.setItem('agentName', agentName.value);
}

function startEditSession(session: any) {
  editingSessionId.value = session.session_id;
  editingSessionName.value = session.name;
  nextTick(() => sessionNameInput.value?.focus());
}

function saveSessionName(sessionId: string) {
  if (editingSessionName.value.trim()) {
    renameSession(sessionId, editingSessionName.value.trim());
  }
  editingSessionId.value = null;
}

function cancelEditSession() {
  editingSessionId.value = null;
}

onMounted(() => {
  agentName.value = localStorage.getItem('agentName') || 'MediaRefitAgent';
});

function handleNewChat() {
  createSession();
}

function handleSelectSession(sessionId: string) {
  if (editingSessionId.value !== sessionId) {
    selectSession(sessionId);
  }
}

function handleDelete(sessionId: string) {
  deleteSession(sessionId);
}
</script>
