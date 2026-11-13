import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { addFavorite, fetchFavorites, removeFavorite } from '@/api/catalog'
import type { ProductSummary } from '@/types/catalog'

export const useFavoritesStore = defineStore('favorites', () => {
  const items = ref<ProductSummary[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  let pending: Promise<void> | null = null

  const ids = computed(() => new Set(items.value.map((item) => item.id)))

  async function load(force = false): Promise<void> {
    if (loaded.value && !force) {
      return
    }
    if (pending && !force) {
      return pending
    }
    loading.value = true
    pending = fetchFavorites()
      .then((data) => {
        items.value = data
        loaded.value = true
      })
      .finally(() => {
        loading.value = false
        pending = null
      })
    return pending
  }

  function isFavorite(id: number): boolean {
    return ids.value.has(id)
  }

  async function toggle(product: ProductSummary): Promise<boolean> {
    const state = isFavorite(product.id)
      ? await removeFavorite(product.id)
      : await addFavorite(product.id)
    if (state.favorited) {
      if (!isFavorite(product.id)) {
        items.value = [product, ...items.value]
      }
    } else {
      items.value = items.value.filter((item) => item.id !== product.id)
    }
    loaded.value = true
    return state.favorited
  }

  function clear(): void {
    items.value = []
    loaded.value = false
  }

  return { items, loading, loaded, ids, load, isFavorite, toggle, clear }
})
