<template>
  <Transition name="slide-up">
    <div class="panel condense-panel" v-if="visible">
      <div class="panel-header">
        <span>智能缩编参数</span>
        <button class="close-btn" @click="close">×</button>
      </div>
      <div class="panel-body">
        <div class="form-group">
          <label>缩编策略</label>
          <div class="strategy-grid">
            <button
              v-for="(item, key) in CONDENSE_STRATEGIES"
              :key="key"
              class="strategy-btn"
              :class="{ active: strategy === key }"
              @click="strategy = key"
            >
              <span class="strategy-name">{{ item.name }}</span>
              <span class="strategy-desc">{{ item.desc }}</span>
            </button>
          </div>
        </div>
        <div class="form-group">
          <label>目标时长（秒）</label>
          <input
            type="number"
            v-model.number="targetDuration"
            class="duration-input"
            placeholder="默认60秒"
            min="5"
            max="3600"
          />
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useAppStore } from '../../stores/app';

const store = useAppStore();

const strategy = ref<string>('');
const targetDuration = ref<number | null>(null);

const visible = computed(() => store.currentFeature === 'condense');

const CONDENSE_STRATEGIES = {
  content_condense: { name: '内容缩编', desc: '保留精彩片段，精简内容' },
  smart_compress: { name: '智能压缩', desc: '智能压缩，保持内容完整' },
};

// 监听策略变化，保存到 store
watch(strategy, (val) => {
  store.setCondenseStrategy(val);
});

// 监听目标时长变化，保存到 store
watch(targetDuration, (val) => {
  if (val !== null) {
    store.setCondenseDuration(val);
  }
});

function close() {
  store.setFeature('condense');
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
.strategy-grid {
  display: flex;
  gap: 8px;
}
.strategy-btn {
  flex: 1;
  padding: 10px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}
.strategy-btn.active {
  border-color: #4CAF50;
  background: #2a4a2a;
}
.strategy-name {
  display: block;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
}
.strategy-desc {
  display: block;
  color: #888;
  font-size: 11px;
  margin-top: 2px;
}
.duration-input {
  width: 100%;
  padding: 8px 12px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
  box-sizing: border-box;
}
.duration-input:focus {
  outline: none;
  border-color: #4CAF50;
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
