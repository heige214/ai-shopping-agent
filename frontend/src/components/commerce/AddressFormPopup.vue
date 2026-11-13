<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { showToast } from 'vant'

import { createAddress, updateAddress } from '@/api/commerce'
import type { Address } from '@/types/commerce'
import { getErrorMessage } from '@/utils/error'

const props = defineProps<{
  show: boolean
  address?: Address | null
}>()

const emit = defineEmits<{
  (event: 'update:show', value: boolean): void
  (event: 'saved', address: Address): void
}>()

const visible = computed({
  get: () => props.show,
  set: (value: boolean) => emit('update:show', value),
})

const loading = ref(false)
const form = reactive({
  receiver_name: '',
  phone: '',
  province: '',
  city: '',
  district: '',
  detail: '',
  is_default: false,
})

function resetForm(): void {
  form.receiver_name = props.address?.receiver_name ?? ''
  form.phone = props.address?.phone ?? ''
  form.province = props.address?.province ?? ''
  form.city = props.address?.city ?? ''
  form.district = props.address?.district ?? ''
  form.detail = props.address?.detail ?? ''
  form.is_default = props.address?.is_default ?? false
}

watch(
  () => [props.show, props.address] as const,
  ([show]) => {
    if (show) {
      resetForm()
    }
  },
  { immediate: true },
)

function validate(): boolean {
  if (!form.receiver_name.trim()) {
    showToast('请填写收货人')
    return false
  }
  if (!/^1[3-9]\d{9}$/.test(form.phone.trim())) {
    showToast('请填写正确的 11 位手机号')
    return false
  }
  if (!form.province.trim() || !form.city.trim() || !form.district.trim()) {
    showToast('请填写完整的省 / 市 / 区')
    return false
  }
  if (!form.detail.trim()) {
    showToast('请填写详细地址')
    return false
  }
  return true
}

async function handleSubmit(): Promise<void> {
  if (loading.value || !validate()) {
    return
  }
  loading.value = true
  try {
    const payload = {
      receiver_name: form.receiver_name.trim(),
      phone: form.phone.trim(),
      province: form.province.trim(),
      city: form.city.trim(),
      district: form.district.trim(),
      detail: form.detail.trim(),
      is_default: form.is_default,
    }
    const address = props.address
      ? await updateAddress(props.address.id, payload)
      : await createAddress(payload)
    showToast(props.address ? '地址已更新' : '地址已添加')
    emit('saved', address)
    visible.value = false
  } catch (error) {
    showToast(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <van-popup
    v-model:show="visible"
    position="bottom"
    round
    class="address-popup"
  >
    <div class="popup-head">
      <h2>{{ props.address ? '编辑地址' : '新增地址' }}</h2>
      <button
        type="button"
        class="popup-close"
        aria-label="关闭"
        @click="visible = false"
      >
        <van-icon name="cross" />
      </button>
    </div>

    <van-cell-group inset class="address-form">
      <van-field
        v-model="form.receiver_name"
        label="收货人"
        placeholder="请填写收货人姓名"
        maxlength="50"
      />
      <van-field
        v-model="form.phone"
        label="手机号"
        type="tel"
        placeholder="请填写 11 位手机号"
        maxlength="11"
      />
      <van-field
        v-model="form.province"
        label="省"
        placeholder="如：上海市（省）"
        maxlength="50"
      />
      <van-field
        v-model="form.city"
        label="市"
        placeholder="如：上海市（市）"
        maxlength="50"
      />
      <van-field
        v-model="form.district"
        label="区"
        placeholder="如：浦东新区"
        maxlength="50"
      />
      <van-field
        v-model="form.detail"
        label="详细地址"
        type="textarea"
        rows="2"
        autosize
        placeholder="街道、门牌号、楼栋房间号"
        maxlength="255"
        show-word-limit
      />
      <van-cell title="设为默认地址" center>
        <template #right-icon>
          <van-switch v-model="form.is_default" size="20" />
        </template>
      </van-cell>
    </van-cell-group>

    <div class="popup-actions">
      <van-button
        block
        type="primary"
        :loading="loading"
        @click="handleSubmit"
      >
        保存
      </van-button>
    </div>
  </van-popup>
</template>

<style scoped>
.address-popup {
  padding: 16px 14px calc(16px + env(safe-area-inset-bottom));
  max-height: 90vh;
  overflow-y: auto;
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

.address-form {
  margin: 0;
}

.popup-actions {
  margin-top: 14px;
}

.popup-actions :deep(.van-button) {
  height: 44px;
  border-radius: 9px;
  font-size: 14px;
}
</style>
