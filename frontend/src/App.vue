<template>
  <div class="app">
    <Sidebar />
    <main class="main">
      <ChatArea />
      <FeatureBar />
      <OrientPanel />
      <CompressPanel />
      <TrimPanel />
      <ConcatPanel />
      <InputArea />
    </main>
    <Preview />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import Sidebar from './components/Sidebar.vue';
import ChatArea from './components/ChatArea.vue';
import FeatureBar from './components/FeatureBar.vue';
import InputArea from './components/InputArea.vue';
import Preview from './components/Preview.vue';
import OrientPanel from './components/panels/OrientPanel.vue';
import CompressPanel from './components/panels/CompressPanel.vue';
import TrimPanel from './components/panels/TrimPanel.vue';
import ConcatPanel from './components/panels/ConcatPanel.vue';
import { useSessions } from './composables/useSessions';

const { loadSessions } = useSessions();

onMounted(() => {
  loadSessions();
});
</script>
