import { ref } from 'vue';
import { api } from '../api';
import { useAppStore } from '../stores/app';
import type { VideoResult, Feature } from '../types';

export function useVideo() {
  const store = useAppStore();

  async function transform(formData: FormData): Promise<VideoResult | null> {
    store.setLoading(true);
    try {
      const result = await api.transform(formData);
      store.setVideoData(result);
      return result;
    } catch (e) {
      console.error('Transform failed:', e);
      return null;
    } finally {
      store.setLoading(false);
    }
  }

  async function compress(formData: FormData): Promise<VideoResult | null> {
    store.setLoading(true);
    try {
      const result = await api.compress(formData);
      store.setVideoData(result);
      return result;
    } catch (e) {
      console.error('Compress failed:', e);
      return null;
    } finally {
      store.setLoading(false);
    }
  }

  async function trim(formData: FormData): Promise<VideoResult | null> {
    store.setLoading(true);
    try {
      const result = await api.trim(formData);
      store.setVideoData(result);
      return result;
    } catch (e) {
      console.error('Trim failed:', e);
      return null;
    } finally {
      store.setLoading(false);
    }
  }

  async function concat(formData: FormData): Promise<VideoResult | null> {
    store.setLoading(true);
    try {
      const result = await api.concat(formData);
      store.setVideoData(result);
      return result;
    } catch (e) {
      console.error('Concat failed:', e);
      return null;
    } finally {
      store.setLoading(false);
    }
  }

  async function videoInfo(formData: FormData) {
    store.setLoading(true);
    try {
      return await api.videoInfo(formData);
    } catch (e) {
      console.error('VideoInfo failed:', e);
      return null;
    } finally {
      store.setLoading(false);
    }
  }

  async function agentChat(formData: FormData) {
    store.setLoading(true);
    try {
      return await api.agentChat(formData);
    } catch (e) {
      console.error('AgentChat failed:', e);
      return null;
    } finally {
      store.setLoading(false);
    }
  }

  function clearVideo() {
    store.setVideoData(null);
  }

  function selectFile(file: File | null) {
    store.setSelectedFile(file);
  }

  function selectFiles(files: File[]) {
    store.setSelectedFiles(files);
  }

  return {
    videoData: store.currentVideoData,
    isLoading: store.isLoading,
    selectedFile: store.selectedFile,
    selectedFiles: store.selectedFiles,
    currentFeature: store.currentFeature,
    selectedStrategy: store.selectedStrategy,
    selectedOrientation: store.selectedOrientation,
    selectedCompression: store.selectedCompression,
    transform,
    compress,
    trim,
    concat,
    videoInfo,
    agentChat,
    clearVideo,
    selectFile,
    selectFiles,
  };
}
