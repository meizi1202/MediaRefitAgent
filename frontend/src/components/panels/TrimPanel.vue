<template>
  <Transition name="slide-up">
    <div class="panel trim-panel" v-if="visible">
      <div class="panel-header">
        <span>视频修剪参数</span>
        <button class="close-btn" @click="close">×</button>
      </div>
      <div class="panel-body">
        <div class="form-row">
          <div class="form-group">
            <label>开始时间（秒）</label>
            <input type="number" v-model="startTime" min="0" step="0.1" />
          </div>
          <div class="form-group">
            <label>结束时间（秒）</label>
            <input type="number" v-model="endTime" :min="startTime" step="0.1" />
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useAppStore } from '../../stores/app';

const store = useAppStore();

const startTime = ref(0);
const endTime = ref(0);

const visible = computed(() => store.currentFeature === 'trim');

function close() {
  store.setFeature('trim');
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
.form-row {
  display: flex;
  gap: 16px;
}
.form-group {
  flex: 1;
}
.form-group label {
  display: block;
  margin-bottom: 6px;
  color: #888;
  font-size: 12px;
}
.form-group input {
  width: 100%;
  padding: 8px 12px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
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
