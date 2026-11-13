<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  src: string | null
  alt: string
}>()

const failed = ref(false)

watch(
  () => props.src,
  () => {
    failed.value = false
  },
)
</script>

<template>
  <div class="product-image">
    <img
      v-if="src && !failed"
      :src="src"
      :alt="alt"
      loading="lazy"
      @error="failed = true"
    />
    <div v-else class="product-image-fallback">
      <span>{{ alt.slice(0, 1) }}</span>
    </div>
  </div>
</template>

<style scoped>
.product-image {
  width: 100%;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  background: var(--color-field-bg);
}

.product-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.product-image-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #fff1e8, #ffd9c4);
  color: var(--color-primary);
  font-size: 24px;
  font-weight: 800;
}
</style>
