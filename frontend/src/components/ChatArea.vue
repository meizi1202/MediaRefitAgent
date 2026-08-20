<template>
  <div class="messages" ref="messagesRef">
    <div v-if="groupedMessages.length === 0" class="empty-state">
      <div class="icon">💬</div>
      <p>开始一段新的对话</p>
    </div>
    <template v-else>
      <div
        v-for="(group, index) in groupedMessages"
        :key="index"
        class="message-group"
        :class="group.role"
      >
        <div class="message-avatar">{{ group.role === 'user' ? '👤' : '🤖' }}</div>
        <div class="message-content">
          <div
            v-for="(item, subIndex) in group.items"
            :key="subIndex"
            class="message-bubble"
            :class="{ 'streaming': item.streaming }"
            v-html="formatContent(item.content)"
          ></div>
          <div class="message-time">{{ formatTime(group.timestamp) }}</div>
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

// 将连续的多条助手消息合并为一个组
const groupedMessages = computed(() => {
  const valid = messages.value.filter(msg => msg && typeof msg.content === 'string');
  const groups: Array<{
    role: string;
    items: Array<{ content: string; streaming?: boolean }>;
    timestamp: string;
  }> = [];

  for (const msg of valid) {
    const last = groups[groups.length - 1];
    // 如果上一条和当前是同一角色，归入同一组
    if (last && last.role === msg.role) {
      last.items.push({ content: msg.content, streaming: (msg as any).streaming });
    } else {
      groups.push({
        role: msg.role,
        items: [{ content: msg.content, streaming: (msg as any).streaming }],
        timestamp: msg.timestamp,
      });
    }
  }
  return groups;
});

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

<style scoped>
.message-group {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.message-group.user {
  flex-direction: row-reverse;
}
.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #2a2a2a;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.message-content {
  max-width: 70%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.message-bubble {
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.message-group.user .message-bubble {
  background: #4CAF50;
  color: #fff;
  border-bottom-right-radius: 4px;
}
.message-group.assistant .message-bubble {
  background: #2a2a2a;
  color: #fff;
  border-bottom-left-radius: 4px;
}
.message-bubble + .message-bubble {
  margin-top: 4px;
  border-radius: 4px;
}
.message-bubble.streaming {
  opacity: 0.8;
  animation: pulse 1s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.8; }
  50% { opacity: 0.6; }
}
.message-time {
  font-size: 11px;
  color: #666;
  padding: 0 4px;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #666;
}
.empty-state .icon {
  font-size: 48px;
  margin-bottom: 12px;
}
</style>
