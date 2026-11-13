import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { fetchCategories } from '@/api/catalog'
import type { Category } from '@/types/catalog'

export const useCatalogStore = defineStore('catalog', () => {
  const categories = ref<Category[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  let pending: Promise<void> | null = null

  async function load(): Promise<void> {
    if (loaded.value) {
      return
    }
    if (pending) {
      return pending
    }
    loading.value = true
    pending = fetchCategories()
      .then((data) => {
        categories.value = data
        loaded.value = true
      })
      .finally(() => {
        loading.value = false
        pending = null
      })
    return pending
  }

  function find(id: number): Category | undefined {
    const walk = (items: Category[]): Category | undefined => {
      for (const item of items) {
        if (item.id === id) {
          return item
        }
        const found = walk(item.children)
        if (found) {
          return found
        }
      }
      return undefined
    }
    return walk(categories.value)
  }

  const roots = computed(() => categories.value)

  return { categories, roots, loading, loaded, load, find }
})
