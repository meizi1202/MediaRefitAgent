<template>
  <div class="app" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <Sidebar :collapsed="sidebarCollapsed" @collapse="toggleSidebar" />
    <div class="resize-handle" @mousedown="startResize"></div>
    <main class="main">
      <ChatArea />
      <FeatureBar />
      <OrientPanel />
      <CompressPanel />
      <TrimPanel />
      <ConcatPanel />
      <CondensePanel />
      <RestorePanel />
      <EditorPanel />
      <InputArea />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import Sidebar from './components/Sidebar.vue';
import ChatArea from './components/ChatArea.vue';
import FeatureBar from './components/FeatureBar.vue';
import InputArea from './components/InputArea.vue';
import OrientPanel from './components/panels/OrientPanel.vue';
import CompressPanel from './components/panels/CompressPanel.vue';
import TrimPanel from './components/panels/TrimPanel.vue';
import ConcatPanel from './components/panels/ConcatPanel.vue';
import CondensePanel from './components/panels/CondensePanel.vue';
import RestorePanel from './components/panels/RestorePanel.vue';
import EditorPanel from './components/panels/EditorPanel.vue';
import { useSessions } from './composables/useSessions';

const { loadSessions } = useSessions();
const sidebarCollapsed = ref(false);
const sidebarWidth = ref(220);
let isResizing = false;

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
}

function startResize(e: MouseEvent) {
  isResizing = true;
  document.addEventListener('mousemove', doResize);
  document.addEventListener('mouseup', stopResize);
}

function doResize(e: MouseEvent) {
  if (!isResizing) return;
  const newWidth = Math.max(150, Math.min(400, e.clientX));
  sidebarWidth.value = newWidth;
  document.documentElement.style.setProperty('--sidebar-width', newWidth + 'px');
}

function stopResize() {
  isResizing = false;
  document.removeEventListener('mousemove', doResize);
  document.removeEventListener('mouseup', stopResize);
}

onMounted(() => {
  loadSessions();
});

onUnmounted(() => {
  document.removeEventListener('mousemove', doResize);
  document.removeEventListener('mouseup', stopResize);
});
</script>
