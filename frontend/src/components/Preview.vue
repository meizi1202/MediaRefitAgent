<template>
  <aside class="preview">
    <div class="preview-header">
      <span>🎬</span>
      <span>视频预览</span>
    </div>
    <div class="preview-content">
      <template v-if="videoData?.output_path">
        <video class="video-player" controls playsinline>
          <source :src="videoUrl" type="video/mp4">
          您的浏览器不支持视频播放
        </video>
        <div class="video-info">
          <div class="row">
            <span class="label">输出文件</span>
            <span class="value">{{ filename }}</span>
          </div>
        </div>
        <div class="preview-actions">
          <button class="preview-btn download" @click="downloadVideo">⬇️ 下载</button>
        </div>
      </template>
      <div v-else class="preview-empty">
        <div class="icon">📹</div>
        <p>暂无生成的视频</p>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useAppStore } from '../stores/app';
import { api } from '../api';

const store = useAppStore();
const videoData = computed(() => store.currentVideoData);

const filename = computed(() => {
  const path = videoData.value?.output_path || '';
  return path.split(/[/\\]/).pop() || '';
});

const videoUrl = computed(() => {
  if (!videoData.value) return '';
  if (videoData.value.download_url) {
    return api.getFullUrl(videoData.value.download_url);
  }
  if (videoData.value.output_path) {
    return api.getDownloadUrl(filename.value);
  }
  return '';
});

function downloadVideo() {
  if (videoUrl.value) {
    window.open(videoUrl.value, '_blank');
  }
}
</script>

<script lang="ts">
export default { name: 'Preview' };
</script>
