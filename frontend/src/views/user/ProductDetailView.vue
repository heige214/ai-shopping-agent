<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'

import { fetchProduct } from '@/api/catalog'
import ProductImage from '@/components/catalog/ProductImage.vue'
import { useFavoritesStore } from '@/stores/favorites'
import type { ProductDetail, ProductSku, SizeChartRow } from '@/types/catalog'
import { colorHex } from '@/utils/colors'
import { getErrorMessage } from '@/utils/error'
import { formatAttributeValue, formatPrice, formatRange } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const favorites = useFavoritesStore()

const product = ref<ProductDetail | null>(null)
const loading = ref(true)
const errorMessage = ref('')
const selectedColor = ref('')
const selectedSize = ref('')
const favorited = ref(false)
const showSizeChart = ref(false)

const colors = computed(() => {
  const seen = new Set<string>()
  const result: string[] = []
  for (const sku of product.value?.skus ?? []) {
    if (!seen.has(sku.color)) {
      seen.add(sku.color)
      result.push(sku.color)
    }
  }
  return result
})

const sizesForColor = computed<ProductSku[]>(() =>
  (product.value?.skus ?? []).filter((sku) => sku.color === selectedColor.value),
)

const selectedSku = computed<ProductSku | null>(
  () => sizesForColor.value.find((sku) => sku.size === selectedSize.value) ?? null,
)

const displayPrice = computed(
  () => selectedSku.value?.price ?? product.value?.price ?? 0,
)

const showSizeSelector = computed(() => {
  if (sizesForColor.value.length > 1) {
    return true
  }
  return sizesForColor.value.length === 1 && sizesForColor.value[0].size !== '均码'
})

const subtitle = computed(() => {
  const attributes = product.value?.attributes
  if (!attributes) {
    return ''
  }
  return ['material', 'fit', 'thickness', 'style', 'gender']
    .map((key) => attributes[key])
    .filter((value): value is string => typeof value === 'string' && value.length > 0)
    .join(' · ')
})

const attributeItems = computed(() => {
  const current = product.value
  if (!current) {
    return []
  }
  return current.attribute_schema.attributes
    .filter((attribute) => !['key_features', 'size'].includes(attribute.key))
    .map((attribute) => ({
      label: attribute.label,
      value: formatAttributeValue(current.attributes[attribute.key]),
    }))
    .filter((item) => item.value.length > 0)
})

const keyFeatures = computed(() => {
  const value = product.value?.attributes.key_features
  return Array.isArray(value) ? value.map(String) : []
})

const sizeChartColumns = computed(() => {
  if (product.value?.size_chart?.type === 'shoes') {
    return ['尺码', '脚长(mm)']
  }
  return ['尺码', '身高(cm)', '体重(kg)', '胸围(cm)', '腰围(cm)']
})

function chartRowValues(row: SizeChartRow): string[] {
  if (product.value?.size_chart?.type === 'shoes') {
    return [row.size, formatRange(row.foot_length)]
  }
  return [
    row.size,
    formatRange(row.height),
    formatRange(row.weight),
    formatRange(row.chest),
    formatRange(row.waist),
  ]
}

function goBack(): void {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.replace('/')
  }
}

function selectSize(size: string): void {
  selectedSize.value = size
}

async function toggleFavorite(): Promise<void> {
  if (!product.value) {
    return
  }
  try {
    favorited.value = await favorites.toggle(product.value)
    showToast(favorited.value ? '已收藏' : '已取消收藏')
  } catch (error) {
    showToast(getErrorMessage(error))
  }
}

function placeholder(message: string): void {
  showToast(message)
}

async function loadFavoriteState(id: number): Promise<void> {
  try {
    await favorites.load()
    favorited.value = favorites.isFavorite(id)
  } catch {
    favorited.value = product.value?.is_favorited ?? false
  }
}

async function loadProduct(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const detail = await fetchProduct(Number(route.params.id))
    product.value = detail
    selectedColor.value = detail.skus[0]?.color ?? ''
    const sizes = detail.skus.filter((sku) => sku.color === selectedColor.value)
    selectedSize.value =
      sizes.find((sku) => sku.stock > 0)?.size ?? sizes[0]?.size ?? ''
    favorited.value = detail.is_favorited
    await loadFavoriteState(detail.id)
  } catch (error) {
    errorMessage.value = getErrorMessage(error)
  } finally {
    loading.value = false
  }
}

watch(selectedColor, () => {
  const sizes = sizesForColor.value
  if (!sizes.some((sku) => sku.size === selectedSize.value)) {
    selectedSize.value =
      sizes.find((sku) => sku.stock > 0)?.size ?? sizes[0]?.size ?? ''
  }
})

onMounted(loadProduct)
</script>

<template>
  <div class="page detail-page">
    <header class="page-header">
      <button type="button" class="icon-button" aria-label="返回" @click="goBack">
        <van-icon name="arrow-left" size="18" />
      </button>
      <span class="header-title">商品详情</span>
      <button
        type="button"
        class="icon-button"
        aria-label="购物车"
        @click="placeholder('购物车将在 M2 上线')"
      >
        <van-icon name="cart-o" size="18" />
      </button>
    </header>

    <div v-if="loading" class="state-panel">
      <van-loading size="22">加载中...</van-loading>
    </div>
    <van-empty v-else-if="errorMessage" :description="errorMessage" />
    <template v-else-if="product">
      <main class="detail-scroll">
        <van-swipe class="detail-swipe" :autoplay="0" indicator-color="#FF5A1F">
          <van-swipe-item v-for="image in product.images" :key="image">
            <ProductImage :src="image" :alt="product.title" />
          </van-swipe-item>
        </van-swipe>

        <section class="detail-body">
          <div class="price-row">
            <span class="price">
              <small>¥</small>{{ formatPrice(displayPrice) }}
            </span>
            <span class="sales">已售 {{ product.sales_count }}</span>
          </div>
          <h1 class="detail-title">{{ product.title }}</h1>
          <p v-if="subtitle" class="detail-sub">{{ subtitle }}</p>

          <div class="color-row">
            <span class="row-label">颜色</span>
            <button
              v-for="color in colors"
              :key="color"
              type="button"
              class="color-swatch"
              :class="{ active: selectedColor === color }"
              :style="{ background: colorHex(color) }"
              :aria-label="color"
              @click="selectedColor = color"
            />
            <span class="color-name">{{ selectedColor }}</span>
          </div>

          <div v-if="showSizeSelector" class="size-row">
            <span class="row-label">尺码</span>
            <button
              v-for="sku in sizesForColor"
              :key="sku.id"
              type="button"
              class="size-chip"
              :class="{ active: selectedSize === sku.size, disabled: sku.stock <= 0 }"
              :disabled="sku.stock <= 0"
              @click="selectSize(sku.size)"
            >
              {{ sku.size }}
            </button>
            <button
              v-if="product.size_chart"
              type="button"
              class="size-chart-link"
              @click="showSizeChart = true"
            >
              尺码表
            </button>
          </div>
          <div v-else class="size-row">
            <span class="row-label">尺码</span>
            <span class="single-size">均码</span>
          </div>

          <div class="stock-line">
            <template v-if="selectedSku">
              <span v-if="selectedSku.stock > 0">
                库存 {{ selectedSku.stock }} 件
              </span>
              <span v-else class="out-of-stock">当前尺码缺货</span>
            </template>
          </div>

          <div class="attribute-table">
            <div
              v-for="item in attributeItems"
              :key="item.label"
              class="attribute-row"
            >
              <span>{{ item.label }}</span>
              <span>{{ item.value }}</span>
            </div>
            <div v-if="keyFeatures.length" class="feature-row">
              <span>设计细节</span>
              <div class="feature-tags">
                <van-tag
                  v-for="feature in keyFeatures"
                  :key="feature"
                  plain
                  type="primary"
                >
                  {{ feature }}
                </van-tag>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer class="bottom-bar">
        <button
          type="button"
          class="bottom-icon"
          :aria-label="favorited ? '取消收藏' : '收藏'"
          @click="toggleFavorite"
        >
          <van-icon :name="favorited ? 'like' : 'like-o'" size="19" />
          <span>{{ favorited ? '已收藏' : '收藏' }}</span>
        </button>
        <button
          type="button"
          class="bottom-icon"
          @click="placeholder('客服将在 M6 上线')"
        >
          <van-icon name="service-o" size="19" />
          <span>客服</span>
        </button>
        <button
          type="button"
          class="bottom-button ghost"
          @click="placeholder('购物车将在 M2 上线')"
        >
          加入购物车
        </button>
        <button
          type="button"
          class="bottom-button primary"
          @click="placeholder('立即购买将在 M2 上线')"
        >
          立即购买
        </button>
      </footer>

      <van-popup
        v-model:show="showSizeChart"
        position="bottom"
        round
        class="size-chart-popup"
      >
        <div class="popup-head">
          <h2>尺码表</h2>
          <button type="button" class="popup-close" @click="showSizeChart = false">
            <van-icon name="cross" />
          </button>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th v-for="column in sizeChartColumns" :key="column">
                  {{ column }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in product.size_chart?.rows ?? []" :key="row.size">
                <td v-for="(value, index) in chartRowValues(row)" :key="index">
                  {{ value }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </van-popup>
    </template>
  </div>
</template>

<style scoped>
.detail-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--color-bg);
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
  text-align: center;
  font-size: 15px;
  font-weight: 700;
}

.state-panel {
  padding: 80px 0;
  display: flex;
  justify-content: center;
}

.detail-scroll {
  padding-bottom: 78px;
  padding-bottom: calc(78px + env(safe-area-inset-bottom));
}

.detail-swipe {
  background: var(--color-card);
}

.detail-body {
  background: var(--color-card);
  margin-top: 8px;
  padding: 14px;
}

.price-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.price {
  color: var(--color-price);
  font-size: 23px;
  font-weight: 800;
}

.price small {
  font-size: 11px;
  margin-right: 2px;
}

.sales {
  font-size: 10px;
  color: var(--color-text-secondary);
}

.detail-title {
  margin: 8px 0 0;
  font-size: 16px;
  line-height: 1.35;
}

.detail-sub {
  margin: 5px 0 0;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.color-row,
.size-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.row-label {
  width: 30px;
  flex: 0 0 auto;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.color-swatch {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 2px solid transparent;
  padding: 0;
}

.color-swatch.active {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px #fff inset;
}

.color-name {
  font-size: 10.5px;
  color: var(--color-text-secondary);
}

.size-chip {
  min-width: 44px;
  height: 32px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  background: var(--color-field-bg);
  color: var(--color-text);
  font-size: 12px;
}

.size-chip.active {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-soft);
  font-weight: 700;
}

.size-chip.disabled {
  color: var(--color-text-tertiary);
  text-decoration: line-through;
}

.size-chart-link {
  border: 0;
  background: transparent;
  color: #3b6fd4;
  font-size: 10px;
  padding: 6px 2px;
}

.single-size {
  font-size: 12px;
  color: var(--color-text);
}

.stock-line {
  min-height: 18px;
  margin-top: 8px;
  font-size: 10px;
  color: var(--color-text-secondary);
}

.out-of-stock {
  color: var(--color-price);
}

.attribute-table {
  margin-top: 8px;
  border-top: 1px solid var(--color-border);
}

.attribute-row,
.feature-row {
  display: flex;
  gap: 12px;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border);
  font-size: 11px;
}

.attribute-row span:first-child,
.feature-row > span {
  color: var(--color-text-secondary);
  flex: 0 0 52px;
}

.attribute-row span:last-child {
  text-align: right;
  flex: 1;
}

.feature-row {
  align-items: flex-start;
}

.feature-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  justify-content: flex-end;
}

.bottom-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--color-card);
  border-top: 1px solid var(--color-border);
  padding: 6px 10px;
  padding-bottom: calc(6px + env(safe-area-inset-bottom));
  display: flex;
  align-items: center;
  gap: 6px;
  z-index: 20;
}

.bottom-icon {
  width: 44px;
  height: 44px;
  border: 0;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 9px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1px;
}

.bottom-button {
  flex: 1;
  height: 40px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  border: 0;
}

.bottom-button.ghost {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border: 1px solid var(--color-primary-border);
}

.bottom-button.primary {
  background: var(--color-primary-gradient);
  color: #fff;
}

.size-chart-popup {
  padding: 16px 14px calc(16px + env(safe-area-inset-bottom));
}

.popup-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.popup-head h2 {
  margin: 0;
  font-size: 16px;
}

.popup-close {
  width: 36px;
  height: 36px;
  border: 0;
  background: transparent;
  color: var(--color-text-secondary);
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
  text-align: center;
}

th,
td {
  padding: 8px 6px;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}

th {
  color: var(--color-text-secondary);
  font-weight: 600;
  background: var(--color-field-bg);
}
</style>
