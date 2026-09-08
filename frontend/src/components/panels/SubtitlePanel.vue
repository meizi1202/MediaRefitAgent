<template>
  <Transition name="slide-up">
    <div class="panel subtitle-panel" v-if="visible">
      <div class="panel-header">
        <span>字幕生成参数</span>
        <button class="close-btn" @click="close">×</button>
      </div>
      <div class="panel-body">
        <div class="form-group">
          <label>字幕样式</label>
          <div class="style-grid">
            <button
              v-for="(item, key) in SUBTITLE_STYLES"
              :key="key"
              class="style-btn"
              :class="{ active: subtitleStyle === key }"
              @click="subtitleStyle = key"
            >
              <span class="style-name">{{ item.name }}</span>
              <span class="style-font">{{ item.font }} / {{ item.size }}px</span>
            </button>
          </div>
        </div>
        <div class="form-group">
          <label>字幕颜色</label>
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
        <div class="form-group">
          <label>字体名称</label>
          <input
            type="text"
            v-model="fontName"
            class="text-input"
            placeholder="新青年体"
          />
        </div>
        <div class="form-group">
          <label>字号大小</label>
          <input
            type="number"
            v-model.number="fontSize"
            class="number-input"
            placeholder="10"
            min="8"
            max="72"
          />
        </div>
        <div class="form-group">
          <label>对齐方式</label>
          <div class="align-grid">
            <button
              v-for="align in ALIGN_OPTIONS"
              :key="align.value"
              class="align-btn"
              :class="{ active: alignment === align.value }"
              @click="alignment = align.value"
            >
              {{ align.label }}
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

const store = useAppStore();

const subtitleStyle = ref<string>('default');
const subtitleColor = ref<string>('#70a19c');
const fontName = ref<string>('新青年体');
const fontSize = ref<number>(10);
const alignment = ref<string>('center');

const visible = computed(() => store.currentFeature === 'subtitle');

const SUBTITLE_STYLES = {
  default: {
    name: '默认样式',
    font: '新青年体',
    size: 10,
    color: '#70a19c'
  },
  xin_qing_nian: {
    name: '新青年体',
    font: '新青年体',
    size: 10,
    color: '#70a19c'
  },
  si_yuan: {
    name: '思源黑体',
    font: '思源黑体',
    size: 12,
    color: '#FFFFFF'
  },
};

const ALIGN_OPTIONS = [
  { value: 'left', label: '左对齐' },
  { value: 'center', label: '居中' },
  { value: 'right', label: '右对齐' },
];

// 监听字幕样式变化，自动填充参数
watch(subtitleStyle, (key) => {
  const style = SUBTITLE_STYLES[key as keyof typeof SUBTITLE_STYLES];
  if (style) {
    fontName.value = style.font;
    fontSize.value = style.size;
    subtitleColor.value = style.color;
  }
});

// 监听参数变化，保存到 store
watch([subtitleStyle, subtitleColor, fontName, fontSize, alignment], () => {
  store.setSubtitleParams({
    style: subtitleStyle.value,
    color: subtitleColor.value,
    fontName: fontName.value,
    fontSize: fontSize.value,
    alignment: alignment.value,
  });
});

function close() {
  store.setFeature('subtitle');
}
</script>

<style scoped>
.panel {
  background: #1a1a1a;
  border-top: 1px solid #2a2a2a;
  border-bottom: 1px solid #2a2a2a;
  max-height: 320px;
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
.text-input {
  width: 100%;
  padding: 8px 12px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
  box-sizing: border-box;
}
.text-input:focus {
  outline: none;
  border-color: #4CAF50;
}
.number-input {
  width: 100%;
  padding: 8px 12px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
  box-sizing: border-box;
}
.number-input:focus {
  outline: none;
  border-color: #4CAF50;
}
.align-grid {
  display: flex;
  gap: 8px;
}
.align-btn {
  flex: 1;
  padding: 8px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 6px;
  color: #888;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.align-btn.active {
  border-color: #4CAF50;
  background: #2a4a2a;
  color: #fff;
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
  max-height: 320px;
  opacity: 1;
}
</style>
