<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'

import { fetchProducts } from '@/api/catalog'
import ProductCard from '@/components/catalog/ProductCard.vue'
import CartBadge from '@/components/commerce/CartBadge.vue'
import { useCartStore } from '@/stores/cart'
import { useCatalogStore } from '@/stores/catalog'
import type { ProductSort, ProductSummary } from '@/types/catalog'
import { getErrorMessage } from '@/utils/error'

const route = useRoute()
const router = useRouter()
const catalog = useCatalogStore()
const cart = useCartStore()

const categoryId = computed(() => Number(route.params.id))
const category = computed(() => catalog.find(categoryId.value))
const parentCategory = computed(() => {
  const current = category.value
  if (!current?.parent_id) {
    return null
  }
  return catalog.find(current.parent_id)
})

const keyword = ref('')
const sort = ref<ProductSort>('recommended')
const items = ref<ProductSummary[]>([])
const page = ref(1)
const total = ref(0)
const listLoading = ref(false)
const finished = ref(false)
const loadError = ref('')
let requestSeq = 0

const sortOptions = [
  { text: '推荐', value: 'recommended' },
  { text: '价格升序', value: 'price_asc' },
  { text: '价格降序', value: 'price_desc' },
]

const headerTitle = computed(() => category.value?.name || '商品列表')
const headerSub = computed(() => parentCategory.value?.name || '')

function goBack(): void {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.replace('/')
  }
}

async function loadMore(): Promise<void> {
  if (finished.value) {
    return
  }
  const seq = ++requestSeq
  const nextPage = page.value
  listLoading.value = true
  loadError.value = ''
  try {
    const data = await fetchProducts({
      category_id: categoryId.value,
      q: keyword.value.trim() || undefined,
      page: nextPage,
      page_size: 20,
      sort: sort.value,
    })
    if (seq !== requestSeq) {
      return
    }
    if (nextPage === 1) {
      items.value = data.items
    } else {
      items.value.push(...data.items)
    }
    total.value = data.total
    page.value = nextPage + 1
    finished.value =
      items.value.length >= data.total || data.items.length === 0
  } catch (error) {
    if (seq !== requestSeq) {
      return
    }
    loadError.value = getErrorMessage(error)
    finished.value = true
    showToast(loadError.value)
  } finally {
    if (seq === requestSeq) {
      listLoading.value = false
    }
  }
}

function reload(): void {
  requestSeq++
  page.value = 1
  items.value = []
  total.value = 0
  finished.value = false
  loadError.value = ''
  void loadMore()
}

function handleSearch(): void {
  reload()
}

function handleSortChange(): void {
  reload()
}

watch(
  () => route.params.id,
  () => {
    reload()
  },
)

onMounted(async () => {
  if (!Number.isInteger(categoryId.value) || categoryId.value <= 0) {
    await router.replace('/')
    return
  }
  await catalog.load()
  cart.load().catch(() => undefined)
  reload()
})
</script>

<template>
  <div class="page category-page">
    <header class="page-header">
      <button type="button" class="icon-button" aria-label="返回" @click="goBack">
        <van-icon name="arrow-left" size="18" />
      </button>
      <div class="header-title">
        <h1>{{ headerTitle }}</h1>
        <span v-if="headerSub">{{ headerSub }}</span>
      </div>
      <CartBadge />
    </header>

    <div class="filter-bar">
      <van-search
        v-model="keyword"
        placeholder="搜索商品、品牌"
        shape="round"
        background="transparent"
        @search="handleSearch"
        @clear="handleSearch"
      />
      <van-dropdown-menu>
        <van-dropdown-item
          v-model="sort"
          :options="sortOptions"
          @change="handleSortChange"
        />
      </van-dropdown-menu>
    </div>

    <div class="list-summary">共 {{ total }} 件商品</div>

    <van-list
      v-model:loading="listLoading"
      :finished="finished"
      :immediate-check="false"
      :finished-text="items.length ? '没有更多了' : ''"
      @load="loadMore"
    >
      <div v-if="items.length" class="product-grid">
        <ProductCard
          v-for="product in items"
          :key="product.id"
          :product="product"
        />
      </div>
      <van-empty
        v-else-if="finished && !loadError"
        description="没有找到符合条件的商品"
      />
    </van-list>
  </div>
</template>

<style scoped>
.category-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--color-bg);
  padding-bottom: 20px;
}

.page-header {
  height: 58px;
  background: var(--color-card);
  display: flex;
  align-items: center;
  padding: 0 8px;
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: 10;
}

.icon-button {
  width: 44px;
  height: 44px;
  border: 0;
  background: transparent;
  color: var(--color-text);
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-title {
  flex: 1;
  min-width: 0;
  text-align: center;
}

.header-title h1 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
}

.header-title span {
  display: block;
  font-size: 9px;
  color: var(--color-text-secondary);
  margin-top: 1px;
}

.filter-bar {
  background: var(--color-card);
  padding: 2px 6px 4px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.filter-bar :deep(.van-search) {
  flex: 1;
  padding: 6px 4px;
}

.filter-bar :deep(.van-dropdown-menu) {
  width: 92px;
  flex: 0 0 auto;
}

.filter-bar :deep(.van-dropdown-menu__bar) {
  box-shadow: none;
  background: transparent;
}

.list-summary {
  padding: 10px 14px 2px;
  font-size: 10px;
  color: var(--color-text-secondary);
}

.product-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding: 8px 14px 16px;
}
</style>
