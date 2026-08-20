<template>
  <div class="input-area">
    <!-- 已选文件展示 -->
    <div class="selected-files" v-if="selectedFile || selectedFiles.length > 0">
      <div class="file-tag" v-if="selectedFile">
        <span class="file-icon">📹</span>
        <span class="file-name">{{ selectedFile.name }}</span>
        <span class="file-size">{{ formatSize(selectedFile.size) }}</span>
        <button class="remove-btn" @click="removeFile">×</button>
      </div>
      <div class="file-tag" v-else-if="selectedFiles.length > 0">
        <span class="file-icon">📹</span>
        <span class="file-name">{{ selectedFiles.length }} 个视频</span>
        <button class="remove-btn" @click="removeFiles">×</button>
      </div>
    </div>

    <div class="input-row">
      <label class="file-btn">
        📤 上传视频
        <input type="file" accept="video/*" multiple @change="handleFileSelect" />
      </label>
      <textarea
        v-model="messageText"
        class="input-field"
        placeholder="输入消息描述您的需求，或上传视频后发送..."
        rows="1"
        @keydown="handleKeydown"
      ></textarea>
      <button class="send-btn" @click="handleSend" :disabled="isLoading">发送</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useAppStore } from '../stores/app';
import { useSessions } from '../composables/useSessions';
import { useVideo } from '../composables/useVideo';
import { api } from '../api';

const store = useAppStore();
const { createSession, addMessage } = useSessions();
const { isLoading } = useVideo();

const messageText = ref('');

const selectedFile = computed(() => store.selectedFile);
const selectedFiles = computed(() => store.selectedFiles);

async function handleSend() {
  const hasFile = store.selectedFile || store.selectedFiles.length > 0;
  if (!messageText.value.trim() && !hasFile) return;

  // 确保有会话
  let sessionId = store.currentSessionId;
  if (!sessionId) {
    createSession();
    // createSession 会更新 store.currentSessionId，需要重新获取
    sessionId = store.currentSessionId!;
  }

  // 格式化选中参数
  const paramsText = store.formatSelectedParams();

  // 构建完整消息（参数 + 用户输入）
  const fullMessage = paramsText
    ? `${paramsText}\n${messageText.value}`
    : messageText.value;

  // 添加用户消息
  addMessage(sessionId, {
    role: 'user',
    content: fullMessage || '[上传视频]',
    timestamp: new Date().toISOString(),
  });

  // 如果是新建会话且名称是默认的，用第一条用户消息作为标题
  const currentSession = store.sessions.find(s => s.session_id === sessionId);
  if (currentSession && currentSession.name === '新会话' && messageText.value.trim()) {
    store.updateSession(sessionId, {
      name: messageText.value.trim().substring(0, 30) + (messageText.value.length > 30 ? '...' : '')
    });
  }

  const text = messageText.value;
  messageText.value = '';

  // 构建 FormData
  const formData = new FormData();
  if (store.selectedFile) {
    formData.append('file', store.selectedFile);
  }
  // 支持多文件上传（用于视频拼接等场景）
  if (store.selectedFiles.length > 0) {
    for (const file of store.selectedFiles) {
      formData.append('files', file);
    }
  }
  if (text || paramsText) {
    formData.append('message', fullMessage);
  }
  // 发送 session_id 以支持多轮对话
  if (sessionId) {
    formData.append('session_id', sessionId);
  }

  // 使用流式 API
  store.setLoading(true);
  const targetSessionId = sessionId;

  // 创建一条临时的助手消息用于流式更新
  const streamingMessageId = Date.now().toString();
  let accumulatedContent = '';

  addMessage(targetSessionId, {
    id: streamingMessageId,
    role: 'assistant',
    content: '',
    timestamp: new Date().toISOString(),
    streaming: true,  // 标记为流式消息
  });

  api.agentChatStream(
    formData,
    // onMessage: 流式内容回调
    (content: string) => {
      accumulatedContent += content;
      // 更新流式消息内容
      store.updateStreamingMessage(targetSessionId, streamingMessageId, accumulatedContent);
    },
    // onDone: 完成回调
    (_data: any) => {
      // 流式结束，更新最终消息
      store.finishStreamingMessage(targetSessionId, streamingMessageId, accumulatedContent);
      store.setLoading(false);
    },
    // onError: 错误回调
    (err: string) => {
      store.finishStreamingMessage(targetSessionId, streamingMessageId, '处理过程中出现错误: ' + err);
      store.setLoading(false);
    }
  );
}

function handleFileSelect(e: Event) {
  const input = e.target as HTMLInputElement;
  if (input.files?.length) {
    if (input.files.length === 1) {
      store.setSelectedFile(input.files[0]);
      store.setSelectedFiles([]);
    } else {
      store.setSelectedFiles(Array.from(input.files));
      store.setSelectedFile(null);
    }
  }
}

function removeFile() {
  store.setSelectedFile(null);
}

function removeFiles() {
  store.setSelectedFiles([]);
}

function formatSize(bytes: number) {
  if (bytes < 1024) return bytes + 'B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB';
  return (bytes / 1024 / 1024).toFixed(1) + 'MB';
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
}
</script>

<style scoped>
.selected-files {
  padding: 8px 16px;
  background: #252525;
  border-bottom: 1px solid #2a2a2a;
}
.file-tag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: #2a2a2a;
  border-radius: 6px;
  font-size: 13px;
}
.file-icon {
  font-size: 14px;
}
.file-name {
  color: #ccc;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-size {
  color: #888;
  font-size: 11px;
}
.remove-btn {
  background: none;
  border: none;
  color: #666;
  cursor: pointer;
  font-size: 14px;
  padding: 0 4px;
}
.remove-btn:hover {
  color: #c00;
}
.input-area {
  background: #1a1a1a;
  border-top: 1px solid #2a2a2a;
}
.input-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  padding: 12px 16px;
}
.file-btn {
  padding: 10px 16px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 8px;
  color: #888;
  cursor: pointer;
  font-size: 14px;
  position: relative;
  white-space: nowrap;
}
.file-btn:hover {
  border-color: #4CAF50;
  color: #4CAF50;
}
.file-btn input {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
}
.input-field {
  flex: 1;
  padding: 12px 16px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
  resize: none;
  min-height: 44px;
  max-height: 120px;
}
.input-field:focus {
  outline: none;
  border-color: #4CAF50;
}
.send-btn {
  padding: 10px 20px;
  background: #4CAF50;
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}
.send-btn:hover {
  background: #45a049;
}
.send-btn:disabled {
  background: #333;
  color: #555;
  cursor: not-allowed;
}
</style>
