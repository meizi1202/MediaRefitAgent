<template>
  <div class="messages" ref="messagesRef">
    <div v-if="messages.length === 0" class="empty-state">
      <div class="icon">💬</div>
      <p>开始一段新的对话</p>
    </div>
    <template v-else>
      <div
        v-for="(msg, index) in validMessages"
        :key="index"
        class="message"
        :class="msg.role"
      >
        <div class="message-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
        <div class="message-content">
          <div class="message-bubble" v-html="formatContent(msg.content || '')"></div>
          <div class="message-time">{{ formatTime(msg.timestamp) }}</div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, watch, ref } from 'vue';
import { useAppStore } from '../stores/app';

const store = useAppStore();
const messagesRef = ref<HTMLElement | null>(null);

const messages = computed(() => store.currentMessages);
const validMessages = computed(() =>
  messages.value.filter(msg => msg && typeof msg.content === 'string')
);

function formatTime(ts: string): string {
  if (!ts) return '';
  const d = new Date(ts);
  return `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`;
}

function formatContent(content: string | null | undefined): string {
  if (!content) return '';
  return content.replace(/\n/g, '<br>');
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = 9999;
    }
  });
}

watch(messages, scrollToBottom, { deep: true });
</script>

<script lang="ts">
export default { name: 'ChatArea' };
</script>
