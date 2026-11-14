import http from '@/api/http'
import type { ImageUploadResult, VoiceUploadResult } from '@/types/guide'

export async function uploadImage(file: File): Promise<ImageUploadResult> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post<ImageUploadResult>('/uploads/image', form, {
    timeout: 60_000,
  })
  return data
}

export async function uploadVoice(file: File): Promise<VoiceUploadResult> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post<VoiceUploadResult>('/uploads/voice', form, {
    timeout: 120_000,
  })
  return data
}
