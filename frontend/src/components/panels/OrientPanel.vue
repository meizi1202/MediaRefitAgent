<template>
  <Transition name="slide-up">
    <div class="panel orient-panel" v-if="visible">
      <div class="panel-header">
        <span>横竖屏转换参数</span>
        <button class="close-btn" @click="close">×</button>
      </div>
      <div class="panel-body">
        <div class="form-row">
          <div class="form-group">
            <label>目标方向</label>
            <div class="radio-group">
              <button
                class="radio-item"
                :class="{ active: orientation === 'portrait' }"
                @click="orientation = 'portrait'"
              >
                竖屏
              </button>
              <button
                class="radio-item"
                :class="{ active: orientation === 'landscape' }"
                @click="orientation = 'landscape'"
              >
                横屏
              </button>
            </div>
          </div>

          <div class="form-group">
            <label>转换策略</label>
            <div class="strategy-grid">
              <button
                v-for="(label, key) in STRATEGY_LABELS"
                :key="key"
                class="strategy-btn"
                :class="{ active: strategy === key }"
                @click="strategy = key as Strategy"
              >
                {{ label }}
              </button>
            </div>
          </div>
        </div>

        <div class="form-group">
          <label>比例预设</label>
          <div class="ratio-group">
            <button
              v-for="ratio in currentRatios"
              :key="ratio"
              class="ratio-btn"
              :class="{ active: selectedRatio === ratio }"
              @click="selectedRatio = ratio"
            >
              {{ ratio }}
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
import { STRATEGY_LABELS, type Strategy, type Orientation } from '../../types';

const store = useAppStore();

const orientation = ref<Orientation>('portrait');
const strategy = ref<Strategy>('pad');
const selectedRatio = ref('9:16');

const visible = computed(() => store.currentFeature === 'orient');

const RATIO_PRESETS = {
  portrait: ['9:16', '4:5', '1:1', '2:3'],
  landscape: ['16:9', '21:9', '4:3', '3:2'],
};

const currentRatios = computed(() => RATIO_PRESETS[orientation.value]);

watch(orientation, (val) => {
  selectedRatio.value = RATIO_PRESETS[val][0];
});

// 参数变化时自动保存到 store
watch([orientation, strategy, selectedRatio], () => {
  store.setOrientation(orientation.value);
  store.setStrategy(strategy.value);
  store.setSelectedRatio(selectedRatio.value);
});

function close() {
  store.setFeature('orient');
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
  gap: 20px;
  margin-bottom: 12px;
}
.form-row .form-group {
  flex: 1;
  margin-bottom: 0;
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
.radio-group {
  display: flex;
  gap: 6px;
}
.radio-item {
  flex: 1;
  padding: 8px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 12px;
  color: #ccc;
}
.radio-item.active {
  border-color: #4CAF50;
  background: #2a4a2a;
  color: #4CAF50;
}
.strategy-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
}
.strategy-btn {
  padding: 6px 8px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 11px;
  color: #ccc;
}
.strategy-btn.active {
  border-color: #4CAF50;
  color: #4CAF50;
}
.ratio-group {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.ratio-btn {
  padding: 6px 12px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 12px;
  color: #ccc;
}
.ratio-btn.active {
  border-color: #4CAF50;
  color: #4CAF50;
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
