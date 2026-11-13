export const COLOR_HEX: Record<string, string> = {
  黑色: '#111111',
  白色: '#F5F5F5',
  米白: '#EFE8DA',
  浅灰: '#C8C8C8',
  深灰: '#555555',
  灰色: '#8A8A8A',
  藏青: '#1F2A44',
  蓝色: '#2F5FAF',
  浅蓝: '#A8C4E0',
  卡其: '#C3B091',
  棕色: '#6B4A2F',
  绿色: '#3E6B4F',
  酒红: '#6E2639',
  驼色: '#B08D62',
  粉色: '#E8B4B8',
  黄色: '#D9A441',
  红色: '#C0392B',
}

export function colorHex(name: string): string {
  return COLOR_HEX[name] ?? '#D8DCE1'
}
