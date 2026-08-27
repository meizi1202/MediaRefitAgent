<template>
  <Transition name="slide-up">
    <div class="panel editor-panel" v-if="visible">
      <div class="panel-header">
        <span>智能剪辑参数</span>
        <button class="close-btn" @click="close">×</button>
      </div>
      <div class="panel-body">
        <!-- 剪辑模式 -->
        <div class="form-group">
          <label>剪辑模式</label>
          <div class="mode-grid">
            <button
              v-for="(item, key) in EDITOR_MODES"
              :key="key"
              class="mode-btn"
              :class="{ active: editorMode === key }"
              @click="editorMode = key"
            >
              <span class="mode-name">{{ item.name }}</span>
              <span class="mode-desc">{{ item.desc }}</span>
            </button>
          </div>
        </div>

        <!-- 目标时长（highlight 模式显示） -->
        <div class="form-group" v-if="editorMode === 'highlight'">
          <label>目标时长（秒）</label>
          <input
            type="number"
            v-model.number="editorDuration"
            class="duration-input"
            placeholder="默认60秒"
            min="5"
            max="3600"
          />
        </div>

        <!-- 字幕样式（highlight/subtitle 模式显示） -->
        <div class="form-group" v-if="editorMode === 'highlight' || editorMode === 'subtitle'">
          <label>字幕样式</label>
          <div class="option-row">
            <button
              v-for="(label, key) in SUBTITLE_STYLES"
              :key="key"
              class="option-btn"
              :class="{ active: subtitleStyle === key }"
              @click="subtitleStyle = key"
            >{{ label }}</button>
          </div>
        </div>

        <!-- 转场类型（highlight/transition 模式显示） -->
        <div class="form-group" v-if="editorMode === 'highlight' || editorMode === 'transition'">
          <label>转场类型</label>
          <div class="option-row">
            <button
              v-for="(label, key) in TRANSITION_TYPES"
              :key="key"
              class="option-btn"
              :class="{ active: transitionType === key }"
              @click="transitionType = key"
            >{{ label }}</button>
          </div>
        </div>

        <!-- 音乐风格（bgm 模式显示） -->
        <div class="form-group" v-if="editorMode === 'bgm'">
          <label>音乐风格</label>
          <div class="option-row">
            <button
              v-for="(label, key) in BGM_MOODS"
              :key="key"
              class="option-btn"
              :class="{ active: bgmMood === key }"
              @click="bgmMood = key"
            >{{ label }}</button>
          </div>
        </div>

        <!-- BGM 音量（bgm 模式显示） -->
        <div class="form-group" v-if="editorMode === 'bgm'">
          <label>BGM音量</label>
          <div class="range-row">
            <input
              type="range"
              v-model.number="bgmVolume"
              class="range-input"
              min="0"
              max="100"
              value="50"
            />
            <span class="range-value">{{ bgmVolume }}%</span>
          </div>
        </div>

        <!-- 配音音色（tts 模式显示） -->
        <div class="form-group" v-if="editorMode === 'tts'">
          <label>配音音色</label>
          <div class="option-row">
            <button
              v-for="(label, key) in TTS_VOICES"
              :key="key"
              class="option-btn"
              :class="{ active: ttsVoice === key }"
              @click="ttsVoice = key"
            >{{ label }}</button>
          </div>
        </div>

        <!-- 配音文本（tts 模式显示） -->
        <div class="form-group" v-if="editorMode === 'tts'">
          <label>配音文本</label>
          <textarea
            v-model="ttsText"
            class="text-input"
            placeholder="输入配音文本内容..."
            rows="2"
          ></textarea>
        </div>

        <!-- 滤镜预设（filter 模式显示） -->
        <div class="form-group" v-if="editorMode === 'filter'">
          <label>滤镜预设</label>
          <div class="option-row wrap">
            <button
              v-for="(label, key) in FILTER_PRESETS"
              :key="key"
              class="option-btn"
              :class="{ active: filterPreset === key }"
              @click="filterPreset = key"
            >{{ label }}</button>
          </div>
        </div>

        <!-- 封面选项（cover 模式显示） -->
        <div class="form-group" v-if="editorMode === 'cover'">
          <label>封面选项</label>
          <div class="option-row">
            <button
              v-for="(label, key) in COVER_MODES"
              :key="key"
              class="option-btn"
              :class="{ active: coverMode === key }"
              @click="coverMode = key"
            >{{ label }}</button>
          </div>
        </div>

        <!-- 目标平台（analyze 模式显示） -->
        <div class="form-group" v-if="editorMode === 'analyze'">
          <label>目标平台</label>
          <div class="option-row wrap">
            <button
              v-for="(label, key) in PLATFORMS"
              :key="key"
              class="option-btn"
              :class="{ active: platform === key }"
              @click="platform = key"
            >{{ label }}</button>
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

// 初始化时从 store 同步当前值
const editorMode = ref<string>(store.selectedEditorMode || 'highlight');
const editorDuration = ref<number | null>(store.selectedEditorDuration ?? null);
const subtitleStyle = ref<string>(store.selectedSubtitleStyle || 'default');
const transitionType = ref<string>(store.selectedTransitionType || 'fade');
const bgmMood = ref<string>(store.selectedBGMMood || 'auto');
const bgmVolume = ref<number>(store.selectedBGMVolume ?? 50);
const ttsVoice = ref<string>(store.selectedTTSVoice || 'zh-CN-XiaoxiaoNeural');
const ttsText = ref<string>(store.selectedTTSText || '');
const filterPreset = ref<string>(store.selectedFilterPreset || 'none');
const coverMode = ref<string>(store.selectedCoverMode || 'single');
const platform = ref<string>(store.selectedPlatform || 'douyin');

const visible = computed(() => store.currentFeature === 'editor');

const EDITOR_MODES = {
  highlight: { name: '精彩片段', desc: '提取高光片段' },
  subtitle: { name: '自动字幕', desc: '生成字幕' },
  transition: { name: '添加转场', desc: '添加转场效果' },
  bgm: { name: '智能配乐', desc: '匹配背景音乐' },
  tts: { name: '配音', desc: '文字转语音' },
  filter: { name: '滤镜', desc: '应用视觉滤镜' },
  analyze: { name: '内容分析', desc: '分析视频内容' },
  cover: { name: '封面生成', desc: '生成吸引人的封面' },
  'title-package': { name: '片头片尾', desc: '添加包装元素' },
};

const SUBTITLE_STYLES: Record<string, string> = {
  default: '默认',
  minimal: '简洁',
};

const TRANSITION_TYPES: Record<string, string> = {
  fade: '淡入淡出',
  slide: '滑动',
  zoom: '缩放',
};

const BGM_MOODS: Record<string, string> = {
  auto: '自动',
  happy: '欢快',
  calm: '平静',
  energetic: '动感',
};

const TTS_VOICES: Record<string, string> = {
  'zh-CN-XiaoxiaoNeural': '晓晓(女声)',
  'zh-CN-YunxiNeural': '云希(男声)',
};

const FILTER_PRESETS: Record<string, string> = {
  none: '无',
  vintage: '复古',
  cinematic: '电影感',
  fresh: '清新',
  bw: '黑白',
  warm: '暖色',
  cold: '冷色',
};

const COVER_MODES: Record<string, string> = {
  single: '单张封面',
  candidates: '多张候选',
};

const PLATFORMS: Record<string, string> = {
  douyin: '抖音',
  kuaishou: '快手',
  bilibili: 'B站',
  xiaohongshu: '小红书',
};

// 同步到 store
watch(editorMode, (val) => store.setEditorMode(val));
watch(editorDuration, (val) => { if (val !== null) store.setEditorDuration(val); });
watch(subtitleStyle, (val) => store.setSubtitleStyle(val));
watch(transitionType, (val) => store.setTransitionType(val));
watch(bgmMood, (val) => store.setBGMMood(val));
watch(bgmVolume, (val) => store.setBGMVolume(val));
watch(ttsVoice, (val) => store.setTTSVoice(val));
watch(ttsText, (val) => store.setTTSText(val));
watch(filterPreset, (val) => store.setFilterPreset(val));
watch(coverMode, (val) => store.setCoverMode(val));
watch(platform, (val) => store.setPlatform(val));

function close() {
  store.setFeature('editor');
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
.mode-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 6px;
}
.mode-btn {
  padding: 8px 6px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}
.mode-btn.active {
  border-color: #4CAF50;
  background: #2a4a2a;
}
.mode-name {
  display: block;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}
.mode-desc {
  display: block;
  color: #888;
  font-size: 10px;
  margin-top: 2px;
}
.option-row {
  display: flex;
  gap: 6px;
}
.option-row.wrap {
  flex-wrap: wrap;
}
.option-btn {
  padding: 6px 12px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 4px;
  color: #888;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.option-btn.active {
  border-color: #4CAF50;
  background: #2a4a2a;
  color: #fff;
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
.text-input {
  width: 100%;
  padding: 8px 12px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 6px;
  color: #fff;
  font-size: 13px;
  box-sizing: border-box;
  resize: vertical;
}
.text-input:focus {
  outline: none;
  border-color: #4CAF50;
}
.range-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.range-input {
  flex: 1;
  accent-color: #4CAF50;
}
.range-value {
  color: #4CAF50;
  font-size: 12px;
  min-width: 36px;
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
