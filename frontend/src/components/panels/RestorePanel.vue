<template>
  <Transition name="slide-up">
    <div class="panel restore-panel" v-if="visible">
      <div class="panel-header">
        <span>老视频修复参数</span>
        <button class="close-btn" @click="close">×</button>
      </div>
      <div class="panel-body">
        <div class="form-group">
          <label>修复套餐</label>
          <div class="preset-grid">
            <button
              v-for="(item, key) in RESTORE_PRESETS"
              :key="key"
              class="preset-btn"
              :class="{ active: preset === key }"
              @click="preset = key"
            >
              <span class="preset-name">{{ item.name }}</span>
              <span class="preset-desc">{{ item.desc }}</span>
            </button>
          </div>
        </div>
        <div class="form-group">
          <label>说明</label>
          <div class="preset-info">
            <p>基础修复：去噪、去抖动、色彩校正</p>
            <p>胶片修复：基础 + 划痕修复、闪烁修复</p>
            <p>增强版：完整 + 补帧、超分辨率</p>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useAppStore } from '../../stores/app';

const store = useAppStore();

const preset = ref<string>('basic');

const visible = computed(() => store.currentFeature === 'restore');

const RESTORE_PRESETS = {
  basic: { name: '基础修复', desc: '去噪、去抖动、色彩校正' },
  film: { name: '胶片修复', desc: '基础 + 划痕修复、闪烁修复' },
  enhanced: { name: '增强版', desc: '完整 + 补帧、超分辨率' },
};

// 监听套餐变化，保存到 store
watch(preset, (val) => {
  store.setRestorePreset(val);
});

// 同步 store 值到本地
watch(() => store.selectedRestorePreset, (val) => {
  preset.value = val;
}, { immediate: true });

function close() {
  store.setFeature(null);
}
</script>

<style scoped>
.panel {
  background: #1a1a1a;
  border-top: 1px solid #2a2a2a;
  border-bottom: 1px solid #2a2a2a;
  max-height: 220px;
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
.preset-grid {
  display: flex;
  gap: 8px;
}
.preset-btn {
  flex: 1;
  padding: 10px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}
.preset-btn.active {
  border-color: #4CAF50;
  background: #2a4a2a;
}
.preset-name {
  display: block;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
}
.preset-desc {
  display: block;
  color: #888;
  font-size: 11px;
  margin-top: 2px;
}
.preset-info {
  font-size: 12px;
  color: #666;
  padding: 8px 0;
  line-height: 1.6;
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
  max-height: 220px;
  opacity: 1;
}
</style>
