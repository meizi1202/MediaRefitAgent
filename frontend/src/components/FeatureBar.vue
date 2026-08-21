<template>
  <div class="feature-bar">
    <button
      v-for="(label, key) in FEATURE_LABELS"
      :key="key"
      class="feature-tab"
      :class="{ active: currentFeature === key }"
      @click="handleSelect(key as Feature)"
    >
      {{ label }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useAppStore } from '../stores/app';
import { FEATURE_LABELS, type Feature } from '../types';

const store = useAppStore();
const currentFeature = computed(() => store.currentFeature);

function handleSelect(feature: Feature) {
  if (store.currentFeature === feature) {
    store.setFeature(null);  // 再次点击同一个标签，取消选中
  } else {
    store.setFeature(feature);
  }
}
</script>
