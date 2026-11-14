<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

import { uploadVoice } from '@/api/uploads'

const props = defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  (
    event: 'recorded',
    payload: { audio_url: string; transcript: string },
  ): void
  (event: 'error', message: string): void
}>()

const recording = ref(false)
const uploading = ref(false)
const seconds = ref(0)
const errorText = ref('')

let recorder: MediaRecorder | null = null
let stream: MediaStream | null = null
let chunks: Blob[] = []
let timer: ReturnType<typeof setInterval> | null = null
let cancelled = false
let maxTimer: ReturnType<typeof setTimeout> | null = null

const durationText = computed(() => {
  const value = Math.min(seconds.value, 99)
  return `00:${String(value).padStart(2, '0')}`
})

function clearTimer(): void {
  if (timer !== null) {
    clearInterval(timer)
    timer = null
  }
  if (maxTimer !== null) {
    clearTimeout(maxTimer)
    maxTimer = null
  }
}

function stopStream(): void {
  stream?.getTracks().forEach((track) => track.stop())
  stream = null
}

function fail(message: string): void {
  errorText.value = message
  emit('error', message)
}

async function start(): Promise<void> {
  if (props.disabled || recording.value || uploading.value) {
    return
  }
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    fail('当前浏览器不支持录音')
    return
  }
  errorText.value = ''
  cancelled = false
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  } catch {
    fail('无法使用麦克风，请检查权限')
    return
  }

  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
  ]
  const mimeType =
    candidates.find((item) => MediaRecorder.isTypeSupported(item)) || ''
  try {
    recorder = mimeType
      ? new MediaRecorder(stream, { mimeType })
      : new MediaRecorder(stream)
  } catch {
    stopStream()
    fail('当前浏览器不支持录音')
    return
  }

  chunks = []
  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) {
      chunks.push(event.data)
    }
  }
  recorder.onstop = () => {
    void finishRecording()
  }

  recorder.start()
  recording.value = true
  seconds.value = 0
  timer = setInterval(() => {
    seconds.value += 1
  }, 1000)
  maxTimer = setTimeout(() => {
    stopRecording()
  }, 60_000)
}

function stopRecording(): void {
  if (!recording.value || !recorder) {
    return
  }
  recording.value = false
  clearTimer()
  if (recorder.state !== 'inactive') {
    recorder.stop()
  }
}

function cancel(): void {
  cancelled = true
  chunks = []
  recording.value = false
  clearTimer()
  if (recorder && recorder.state !== 'inactive') {
    recorder.stop()
  }
  recorder = null
  stopStream()
}

async function finishRecording(): Promise<void> {
  const audioType = (recorder?.mimeType || 'audio/webm').split(';')[0]
  recorder = null
  stopStream()
  if (cancelled) {
    uploading.value = false
    return
  }
  if (!chunks.length) {
    fail('没有录到声音，请重试')
    return
  }

  uploading.value = true
  try {
    const extension = audioType === 'audio/mp4' ? 'mp4' : 'webm'
    const blob = new Blob(chunks, { type: audioType })
    const file = new File([blob], `voice.${extension}`, { type: audioType })
    const result = await uploadVoice(file)
    emit('recorded', {
      audio_url: result.url,
      transcript: result.transcript,
    })
  } catch {
    fail('语音转写失败，请重试')
  } finally {
    chunks = []
    uploading.value = false
  }
}

onBeforeUnmount(() => {
  cancelled = true
  clearTimer()
  if (recorder && recorder.state !== 'inactive') {
    recorder.stop()
  }
  stopStream()
})
</script>

<template>
  <button
    type="button"
    class="voice-button"
    aria-label="语音输入"
    :disabled="disabled || uploading"
    @click="start"
  >
    <van-icon :name="uploading ? 'loading' : 'audio'" size="19" />
  </button>

  <van-popup
    :show="recording || uploading"
    position="bottom"
    :close-on-click-overlay="false"
    class="voice-popup"
  >
    <div class="voice-panel">
      <div class="voice-title">
        {{ uploading ? '正在转写…' : '正在录音' }}
      </div>
      <div class="voice-timer">{{ durationText }}</div>
      <div v-if="!uploading" class="voice-wave">
        <span v-for="index in 12" :key="index" />
      </div>
      <p class="voice-hint">
        {{ uploading ? '请稍候，转写完成后可编辑再发送' : '说完后点「完成」，转写不会自动发送' }}
      </p>
      <div v-if="errorText" class="voice-error">{{ errorText }}</div>
      <div v-if="!uploading" class="voice-actions">
        <button type="button" class="voice-cancel" @click="cancel">
          取消
        </button>
        <button
          type="button"
          class="voice-stop"
          aria-label="完成录音"
          @click="stopRecording"
        >
          完成
        </button>
      </div>
    </div>
  </van-popup>
</template>

<style scoped>
.voice-button {
  width: 34px;
  height: 38px;
  flex: 0 0 auto;
  border: 0;
  background: transparent;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.voice-button:disabled {
  opacity: 0.4;
}

.voice-popup {
  border-radius: 18px 18px 0 0;
}

.voice-panel {
  padding: 22px 20px calc(24px + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.voice-title {
  font-size: 15px;
  font-weight: 700;
}

.voice-timer {
  font-size: 26px;
  font-weight: 800;
  color: var(--color-primary);
  font-variant-numeric: tabular-nums;
}

.voice-wave {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 30px;
}

.voice-wave span {
  width: 4px;
  height: 10px;
  border-radius: 2px;
  background: var(--color-primary);
  animation: voice-wave 0.9s ease-in-out infinite alternate;
}

.voice-wave span:nth-child(2n) {
  animation-delay: 0.15s;
}

.voice-wave span:nth-child(3n) {
  animation-delay: 0.3s;
}

@keyframes voice-wave {
  from {
    height: 8px;
    opacity: 0.45;
  }
  to {
    height: 26px;
    opacity: 1;
  }
}

.voice-hint {
  margin: 0;
  font-size: 11px;
  color: var(--color-text-secondary);
  text-align: center;
}

.voice-error {
  color: var(--color-price);
  font-size: 11px;
}

.voice-actions {
  margin-top: 8px;
  width: 100%;
  display: flex;
  gap: 10px;
}

.voice-cancel,
.voice-stop {
  flex: 1;
  height: 42px;
  border-radius: 21px;
  font-size: 13px;
  font-weight: 700;
}

.voice-cancel {
  border: 1px solid var(--color-border);
  background: var(--color-field-bg);
  color: var(--color-text-secondary);
}

.voice-stop {
  border: 0;
  background: var(--color-primary-gradient);
  color: #fff;
}
</style>
