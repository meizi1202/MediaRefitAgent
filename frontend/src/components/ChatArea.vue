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
            :class="{ 'streaming': item.streaming, 'has-next': subIndex < group.items.length - 1 }"
            v-html="formatContent(item.content)"
          ></div>
          <div class="message-time">{{ formatTime(group.timestamp) }}</div>
          <!-- 视频预览 - 紧跟在助手消息下方 -->
          <div v-if="group.role === 'assistant' && group.previewPath" class="video-preview">
            <video
              :src="getPreviewUrl(group.previewPath)"
              controls
              class="preview-video"
            ></video>
            <div class="preview-info">
              <a :href="getPreviewUrl(group.previewPath)" target="_blank" class="download-link">⬇️ 下载</a>
            </div>
          </div>
          <!-- 流式消息加载指示器 - 仅在当前消息组未完成时展示 -->
          <div v-if="group.role === 'assistant' && group.items.some(item => item.streaming)" class="streaming-indicator">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, watch, ref } from 'vue';
import { useAppStore } from '../stores/app';
import { api } from '../api';

const store = useAppStore();
const messagesRef = ref<HTMLElement | null>(null);

const messages = computed(() => store.currentMessages);

// 计算预览视频 URL
function getPreviewUrl(path: string): string {
  if (!path) return '';
  const filename = path.split(/[/\\]/).pop() || '';
  return api.getDownloadUrl(filename);
}

// 检查是否有正在流式传输的消息
const hasStreamingMessage = computed(() =>
  messages.value.some(msg => (msg as any).streaming)
);

// 简化：所有助手消息合并为一个带内容的列表，用户消息独立
const groupedMessages = computed(() => {
  const valid = messages.value.filter(msg => msg && typeof msg.content === 'string');
  const groups: Array<{
    role: string;
    items: Array<{ content: string; streaming?: boolean }>;
    timestamp: string;
    previewPath?: string;
  }> = [];

  for (const msg of valid) {
    const streaming = (msg as any).streaming;

    // 用户消息独立一行
    if (msg.role === 'user') {
      groups.push({
        role: msg.role,
        items: [{ content: msg.content, streaming }],
        timestamp: msg.timestamp,
      });
    } else {
      // 助手消息：合并到上一组
      const last = groups[groups.length - 1];
      // 提取预览路径
      const previewMatch = msg.content.match(/\[PREVIEW:([^\]]+)\]/);
      const previewPath = previewMatch ? previewMatch[1] : undefined;

      if (last && last.role === 'assistant') {
        // 如果上一条还在流式，替换内容；否则追加
        if (last.items[last.items.length - 1].streaming) {
          last.items[last.items.length - 1] = { content: msg.content, streaming };
        } else {
          last.items.push({ content: msg.content, streaming });
        }
        // 更新预览路径
        if (previewPath) {
          last.previewPath = previewPath;
        }
      } else {
        groups.push({
          role: msg.role,
          items: [{ content: msg.content, streaming }],
          timestamp: msg.timestamp,
          previewPath,
        });
      }
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
  // 移除 [PREVIEW:...] 标签（用于触发视频预览，不显示在消息中）
  let text = content.replace(/\[PREVIEW:[^\]]*\]/g, '').trim();
  // 转义 HTML 特殊字符，防止 \n \t 等被解释
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
    .replace(/\t/g, '&nbsp;&nbsp;&nbsp;&nbsp;')  // Tab 转为 4 个空格
    .replace(/\n/g, '<br>')  // 换行符转为 <br>
    .replace(/\v/g, '<br>');  // 垂直制表符转为换行
  return escaped.replace(/\n/g, '<br>');
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = 9999;
    }
  });
}

// 仅当添加新消息时滚动，非流式更新时不滚动
// 流式消息时用 requestAnimationFrame 防抖，避免闪烁
let scrollRaf: number | null = null;
function scrollToBottomDebounced() {
  if (scrollRaf) cancelAnimationFrame(scrollRaf);
  scrollRaf = requestAnimationFrame(() => {
    scrollToBottom();
    scrollRaf = null;
  });
}

// 监听消息长度变化（新增消息时滚动）
watch(() => messages.value.length, () => {
  scrollToBottomDebounced();
});

// 流式消息时频繁滚动到底部
watch(hasStreamingMessage, (streaming) => {
  if (streaming) {
    // 开始流式传输时启动定时滚动
    const scrollInterval = setInterval(() => {
      if (messagesRef.value) {
        messagesRef.value.scrollTop = 9999;
      }
    }, 100);
    // 保存 interval 引用以便清除
    (messagesRef.value as any).__scrollInterval = scrollInterval;
  } else {
    // 结束流式传输时清除
    const interval = (messagesRef.value as any).__scrollInterval;
    if (interval) {
      clearInterval(interval);
    }
  }
});
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
  display: block;
}
.message-bubble.has-next {
  margin-bottom: 12px;
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
/* 同一组内的多个气泡之间通过 formatContent 的 br 换行 */
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
/* 流式消息加载指示器 */
.streaming-indicator {
  display: flex;
  gap: 4px;
  padding: 12px 16px;
  justify-content: center;
}
.streaming-indicator .dot {
  width: 8px;
  height: 8px;
  background: #666;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}
.streaming-indicator .dot:nth-child(1) { animation-delay: -0.32s; }
.streaming-indicator .dot:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}
/* 视频预览 */
.video-preview {
  margin-top: 8px;
  background: #2a2a2a;
  border-radius: 8px;
  overflow: hidden;
  max-width: 300px;
}
.preview-video {
  width: 100%;
  max-height: 180px;
  display: block;
}
.preview-info {
  padding: 4px 8px;
  text-align: right;
}
.download-link {
  color: #4CAF50;
  text-decoration: none;
  font-size: 12px;
}
.download-link:hover {
  text-decoration: underline;
}
</style>
