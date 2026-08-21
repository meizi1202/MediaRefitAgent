<template>
  <Transition name="slide-up">
    <div class="panel concat-panel" v-if="visible">
      <div class="panel-header">
        <span>视频拼接参数</span>
        <button class="close-btn" @click="close">×</button>
      </div>
      <div class="panel-body">
        <div class="form-group">
          <label>已选视频 ({{ selectedFiles.length }}个)</label>
          <div class="file-list" v-if="selectedFiles.length > 0">
            <div v-for="(file, i) in selectedFiles" :key="i" class="file-item">
              <span class="file-number">{{ i + 1 }}.</span>
              <span class="file-name">{{ file.name }}</span>
              <div class="file-actions">
                <button class="btn-up" @click="moveUp(i)" :disabled="i === 0">↑</button>
                <button class="btn-down" @click="moveDown(i)" :disabled="i === selectedFiles.length - 1">↓</button>
              </div>
            </div>
          </div>
          <div v-else class="empty-tip">请上传至少2个视频</div>
        </div>
        <div class="form-group">
          <label class="checkbox-label">
            <input type="checkbox" v-model="keepAudio" />
            <span>保留音频</span>
          </label>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useAppStore } from '../../stores/app';

const store = useAppStore();

const keepAudio = ref(true);
const localFiles = ref<File[]>([]);

const visible = computed(() => store.currentFeature === 'concat');
const selectedFiles = computed(() => localFiles.value);

watch(() => store.selectedFiles, (newFiles) => {
  localFiles.value = [...(newFiles || [])];
}, { immediate: true });

function moveUp(index: number) {
  if (index > 0) {
    const temp = localFiles.value[index];
    localFiles.value[index] = localFiles.value[index - 1];
    localFiles.value[index - 1] = temp;
    store.setSelectedFiles([...localFiles.value]);
  }
}

function moveDown(index: number) {
  if (index < localFiles.value.length - 1) {
    const temp = localFiles.value[index];
    localFiles.value[index] = localFiles.value[index + 1];
    localFiles.value[index + 1] = temp;
    store.setSelectedFiles([...localFiles.value]);
  }
}

function close() {
  store.setFeature('concat');
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
  margin-bottom: 6px;
  color: #888;
  font-size: 12px;
}
.file-list {
  background: #2a2a2a;
  border-radius: 6px;
  padding: 8px;
  max-height: 80px;
  overflow-y: auto;
}
.file-item {
  display: flex;
  align-items: center;
  padding: 4px 0;
  font-size: 12px;
  color: #ccc;
}
.file-number {
  color: #888;
  margin-right: 6px;
  min-width: 20px;
}
.file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-actions {
  display: flex;
  gap: 4px;
  margin-left: 8px;
}
.btn-up, .btn-down {
  background: #3a3a3a;
  border: none;
  color: #aaa;
  width: 22px;
  height: 22px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 11px;
  line-height: 1;
}
.btn-up:hover, .btn-down:hover {
  background: #4a4a4a;
  color: #fff;
}
.btn-up:disabled, .btn-down:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
.empty-tip {
  color: #666;
  font-size: 12px;
  padding: 8px;
  background: #2a2a2a;
  border-radius: 6px;
}
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #ccc;
  font-size: 13px;
}
.checkbox-label input {
  width: 16px;
  height: 16px;
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
