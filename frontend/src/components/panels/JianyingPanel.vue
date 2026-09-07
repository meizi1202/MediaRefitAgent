<template>
  <Transition name="slide-up">
    <div class="panel jianying-panel" v-if="visible">
      <div class="panel-header">
        <span>剪映对接</span>
        <button class="close-btn" @click="close">×</button>
      </div>
      <div class="panel-body">
        <!-- 功能切换 -->
        <div class="tab-row">
          <button
            class="tab-btn"
            :class="{ active: mode === 'subtitle' }"
            @click="switchMode('subtitle')"
          >
            添加字幕
          </button>
          <button
            class="tab-btn"
            :class="{ active: mode === 'transition' }"
            @click="switchMode('transition')"
          >
            添加转场
          </button>
          <button
            class="tab-btn"
            :class="{ active: mode === 'both' }"
            @click="switchMode('both')"
          >
            字幕+转场
          </button>
        </div>

        <!-- 字幕设置 -->
        <template v-if="mode === 'subtitle' || mode === 'both'">
          <div class="section-title">字幕样式</div>

          <!-- 字幕样式选择 -->
          <div class="form-group">
            <label>字体</label>
            <div class="style-grid">
              <button
                v-for="(item, key) in SUBTITLE_STYLES"
                :key="key"
                class="style-btn"
                :class="{ active: subtitleStyle === key }"
                @click="setSubtitleStyle(key)"
              >
                <span class="style-name">{{ item.name }}</span>
                <span class="style-font">{{ item.font }} / {{ item.size }}px</span>
              </button>
            </div>
          </div>

          <!-- 字幕颜色 -->
          <div class="form-group">
            <label>颜色</label>
            <div class="color-row">
              <input
                type="text"
                v-model="subtitleColor"
                class="color-input"
                placeholder="#70a19c"
              />
              <input
                type="color"
                v-model="subtitleColor"
                class="color-picker"
              />
            </div>
          </div>

          <!-- 字号大小 -->
          <div class="form-group">
            <label>字号</label>
            <input
              type="number"
              v-model.number="fontSize"
              class="number-input"
              min="8"
              max="72"
            />
          </div>
        </template>

        <!-- 转场设置 -->
        <template v-if="mode === 'transition' || mode === 'both'">
          <div class="section-title">转场效果</div>

          <!-- 转场类型 -->
          <div class="form-group">
            <label>转场类型</label>
            <select v-model="transitionType" class="select-input">
              <option value="">无转场</option>
              <option v-for="t in TRANSITION_LIST" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>

          <!-- 转场时长 -->
          <div class="form-group">
            <label>转场时长（毫秒）</label>
            <input
              type="number"
              v-model.number="transitionDuration"
              class="number-input"
              min="100"
              max="5000"
              step="100"
            />
          </div>
        </template>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useAppStore } from '../../stores/app';

const store = useAppStore();

const visible = computed(() => store.currentFeature === 'jianying');

// 功能模式
type JianyingMode = 'subtitle' | 'transition' | 'both';
const mode = ref<JianyingMode>('subtitle');

// 字幕样式
const subtitleStyle = ref<string>('default');
const subtitleColor = ref<string>('#70a19c');
const fontSize = ref<number>(10);

const SUBTITLE_STYLES = {
  default: { name: '默认样式', font: '新青年体', size: 10, color: '#70a19c' },
  xin_qing_nian: { name: '新青年体', font: '新青年体', size: 10, color: '#70a19c' },
  si_yuan: { name: '思源黑体', font: '思源黑体', size: 10, color: '#FFFFFF' },
};

// 转场设置
const transitionType = ref<string>('');
const transitionDuration = ref<number>(500);

const TRANSITION_LIST = [
  '叠化', '模糊', '故障', '向下流动', '向上', '向左', '向右',
  '圆形遮罩', '水墨', '放射', '星光', '拉伸',
  '左移', '右移', '上移', '下移', '开幕', '收缩',
];

function switchMode(newMode: JianyingMode) {
  mode.value = newMode;
  // subtitle 模式下清除转场参数
  if (newMode === 'subtitle') {
    transitionType.value = '';
    transitionDuration.value = 500;
    store.setTransitionType('');
    store.setTransitionDuration(0);
  }
  syncToStore();
}

// 同步到 store
function syncToStore() {
  store.setJianyingMode(mode.value);
  store.setSubtitleParams({
    style: subtitleStyle.value,
    color: subtitleColor.value,
    fontName: SUBTITLE_STYLES[subtitleStyle.value as keyof typeof SUBTITLE_STYLES]?.font || '新青年体',
    fontSize: fontSize.value,
  });
  // subtitle 模式下强制清除转场参数，其他模式才传
  if (mode.value === 'subtitle') {
    store.setTransitionType('');
    store.setTransitionDuration(0);
  } else if (transitionType.value) {
    store.setTransitionType(transitionType.value);
    store.setTransitionDuration(transitionDuration.value);
  }
}

// 监听参数变化
watch([mode, subtitleStyle, subtitleColor, fontSize, transitionType, transitionDuration], () => {
  syncToStore();
});

function close() {
  store.setFeature('jianying');
}
</script>

<style scoped>
.panel {
  background: #1a1a1a;
  border-top: 1px solid #2a2a2a;
  border-bottom: 1px solid #2a2a2a;
  max-height: 500px;
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
.tab-row {
  display: flex;
  gap: 6px;
  margin-bottom: 16px;
}
.tab-btn {
  flex: 1;
  padding: 8px 12px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 6px;
  color: #888;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.tab-btn.active {
  border-color: #4CAF50;
  background: #2a4a2a;
  color: #fff;
}
.section-title {
  color: #666;
  font-size: 11px;
  margin-bottom: 8px;
  margin-top: 4px;
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
.style-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.style-btn {
  padding: 10px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}
.style-btn.active {
  border-color: #4CAF50;
  background: #2a4a2a;
}
.style-name {
  display: block;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
}
.style-font {
  display: block;
  color: #888;
  font-size: 10px;
  margin-top: 2px;
}
.color-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.color-input {
  flex: 1;
  padding: 8px 12px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
}
.color-input:focus {
  outline: none;
  border-color: #4CAF50;
}
.color-picker {
  width: 36px;
  height: 36px;
  padding: 2px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 6px;
  cursor: pointer;
}
.number-input, .select-input {
  width: 100%;
  padding: 8px 12px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
  box-sizing: border-box;
}
.number-input:focus, .select-input:focus {
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
  max-height: 500px;
  opacity: 1;
}
</style>
