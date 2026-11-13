import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  addCartItem,
  fetchCart,
  removeCartItem,
  updateCartItem,
} from '@/api/commerce'
import type { Cart, CartItem } from '@/types/commerce'

function emptyCart(): Cart {
  return {
    items: [],
    total_quantity: 0,
    selected_count: 0,
    selected_amount: 0,
    all_selected: false,
  }
}

export const useCartStore = defineStore('cart', () => {
  const data = ref<Cart>(emptyCart())
  const loading = ref(false)
  const loaded = ref(false)
  let pending: Promise<void> | null = null

  const totalQuantity = computed(() => data.value.total_quantity)

  function recalculate(): void {
    const items = data.value.items
    const selected = items.filter((item) => item.selected)
    const amount = selected.reduce(
      (sum, item) => sum + item.price * item.quantity,
      0,
    )
    data.value.total_quantity = items.reduce(
      (sum, item) => sum + item.quantity,
      0,
    )
    data.value.selected_count = selected.length
    data.value.selected_amount = Math.round(amount * 100) / 100
    data.value.all_selected =
      items.length > 0 && selected.length === items.length
  }

  function replaceItem(item: CartItem): void {
    const index = data.value.items.findIndex((row) => row.id === item.id)
    if (index >= 0) {
      data.value.items[index] = item
    }
    recalculate()
  }

  async function load(force = false): Promise<void> {
    if (loaded.value && !force) {
      return
    }
    if (pending && !force) {
      return pending
    }
    loading.value = true
    pending = fetchCart()
      .then((cart) => {
        data.value = cart
        loaded.value = true
      })
      .finally(() => {
        loading.value = false
        pending = null
      })
    return pending
  }

  async function add(skuId: number, quantity = 1): Promise<CartItem> {
    const item = await addCartItem(skuId, quantity)
    await load(true)
    return item
  }

  async function update(
    itemId: number,
    payload: { quantity?: number; selected?: boolean },
  ): Promise<void> {
    replaceItem(await updateCartItem(itemId, payload))
  }

  async function remove(itemId: number): Promise<void> {
    await removeCartItem(itemId)
    data.value.items = data.value.items.filter((item) => item.id !== itemId)
    recalculate()
  }

  function clear(): void {
    data.value = emptyCart()
    loaded.value = false
  }

  return {
    data,
    loading,
    loaded,
    totalQuantity,
    load,
    add,
    update,
    remove,
    clear,
  }
})
