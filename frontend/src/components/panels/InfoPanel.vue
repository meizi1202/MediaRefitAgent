<template>
  <Transition name="slide-up">
    <div class="panel info-panel" v-if="visible">
      <div class="panel-header">
        <span>视频信息</span>
        <button class="close-btn" @click="close">×</button>
      </div>
      <div class="panel-body">
        <div class="info-grid" v-if="videoData">
          <div class="info-item">
            <span class="label">分辨率</span>
            <span class="value">{{ videoData.width }} × {{ videoData.height }}</span>
          </div>
          <div class="info-item">
            <span class="label">时长</span>
            <span class="value">{{ videoData.duration?.toFixed(1) }}秒</span>
          </div>
          <div class="info-item">
            <span class="label">文件大小</span>
            <span class="value">{{ formatSize(videoData.original_size) }}</span>
          </div>
          <div class="info-item" v-if="videoData.fps">
            <span class="label">帧率</span>
            <span class="value">{{ videoData.fps }}</span>
          </div>
        </div>
        <div v-else class="empty-tip">请先上传视频获取信息</div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useAppStore } from '../../stores/app';

const store = useAppStore();

const visible = computed(() => store.currentFeature === 'info');
const videoData = computed(() => store.currentVideoData);

function close() {
  store.setFeature('info');
}

function formatSize(bytes: number | undefined) {
  if (!bytes) return '-';
  if (bytes < 1024) return bytes + 'B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB';
  return (bytes / 1024 / 1024).toFixed(1) + 'MB';
}
</script>

<style scoped>
.panel {
  background: #1a1a1a;
  border-top: 1px solid #2a2a2a;
  border-bottom: 1px solid #2a2a2a;
  max-height: 200px;
  overflow-y: auto;
}
.panel-header {
  padding: 10px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  font-size: 13px;
}
.close-btn {
  background: none;
  border: none;
  color: #888;
  font-size: 18px;
  cursor: pointer;
}
.panel-body {
  padding: 0 16px 16px;
}
.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.info-item {
  background: #2a2a2a;
  padding: 10px;
  border-radius: 6px;
}
.info-item .label {
  display: block;
  color: #888;
  font-size: 11px;
  margin-bottom: 4px;
}
.info-item .value {
  display: block;
  color: #4CAF50;
  font-size: 14px;
  font-weight: 600;
}
.empty-tip {
  color: #666;
  font-size: 12px;
  padding: 20px;
  text-align: center;
}
.slide-up-enter-active, .slide-up-leave-active {
  transition: max-height 0.3s ease, opacity 0.3s ease;
  overflow: hidden;
}
.slide-up-enter-from, .slide-up-leave-to {
  max-height: 0;
  opacity: 0;
}
.slide-up-enter-to, .slide-up-leave-from {
  max-height: 200px;
  opacity: 1;
}
</style>
