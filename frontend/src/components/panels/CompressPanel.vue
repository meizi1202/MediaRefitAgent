<template>
  <Transition name="slide-up">
    <div class="panel compress-panel" v-if="visible">
      <div class="panel-header">
        <span>视频压缩参数</span>
        <button class="close-btn" @click="close">×</button>
      </div>
      <div class="panel-body">
        <div class="form-group">
          <label>压缩级别</label>
          <div class="level-grid">
            <button
              v-for="(item, key) in COMPRESS_LEVELS"
              :key="key"
              class="level-btn"
              :class="{ active: level === key }"
              @click="level = key"
            >
              <span class="level-name">{{ item.name }}</span>
              <span class="level-desc">{{ item.desc }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useAppStore } from '../../stores/app';
import type { CompressionLevel } from '../../types';

const store = useAppStore();

const level = ref<CompressionLevel>('medium');

const visible = computed(() => store.currentFeature === 'compress');

const COMPRESS_LEVELS = {
  low: { name: '低压缩', desc: '高质量，文件较大' },
  medium: { name: '中压缩', desc: '质量和体积平衡' },
  high: { name: '高压缩', desc: '小体积，质量较低' },
};

// 参数变化时自动保存到 store
watch(level, (val) => {
  store.setCompression(val);
});

function close() {
  store.setFeature('compress');
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
.form-group {
  margin-bottom: 12px;
}
.form-group label {
  display: block;
  margin-bottom: 8px;
  color: #888;
  font-size: 12px;
}
.level-grid {
  display: flex;
  gap: 8px;
}
.level-btn {
  flex: 1;
  padding: 10px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}
.level-btn.active {
  border-color: #4CAF50;
  background: #2a4a2a;
}
.level-name {
  display: block;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
}
.level-desc {
  display: block;
  color: #888;
  font-size: 11px;
  margin-top: 2px;
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
