<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'

import {
  deleteAddress,
  fetchAddresses,
  updateAddress,
} from '@/api/commerce'
import AddressFormPopup from '@/components/commerce/AddressFormPopup.vue'
import type { Address } from '@/types/commerce'
import { formatFullAddress } from '@/utils/commerce'
import { getErrorMessage } from '@/utils/error'

const router = useRouter()

const addresses = ref<Address[]>([])
const loading = ref(true)
const showForm = ref(false)
const editingAddress = ref<Address | null>(null)

function goBack(): void {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.replace('/me')
  }
}

async function loadAddresses(): Promise<void> {
  loading.value = true
  try {
    addresses.value = await fetchAddresses()
  } catch (error) {
    showToast(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  editingAddress.value = null
  showForm.value = true
}

function openEdit(address: Address): void {
  editingAddress.value = address
  showForm.value = true
}

function handleSaved(): void {
  showForm.value = false
  void loadAddresses()
}

async function setDefault(address: Address): Promise<void> {
  try {
    await updateAddress(address.id, { is_default: true })
    showToast('已设为默认地址')
    await loadAddresses()
  } catch (error) {
    showToast(getErrorMessage(error))
  }
}

async function remove(address: Address): Promise<void> {
  try {
    await showConfirmDialog({
      title: '删除地址',
      message: `确定删除「${address.receiver_name}」的收货地址吗？`,
    })
  } catch {
    return
  }
  try {
    await deleteAddress(address.id)
    showToast('地址已删除')
    await loadAddresses()
  } catch (error) {
    showToast(getErrorMessage(error))
  }
}

onMounted(loadAddresses)
</script>

<template>
  <div class="page addresses-page">
    <header class="page-header">
      <button type="button" class="icon-button" aria-label="返回" @click="goBack">
        <van-icon name="arrow-left" size="18" />
      </button>
      <span class="header-title">收货地址</span>
      <span class="header-spacer" />
    </header>

    <div v-if="loading && !addresses.length" class="state-panel">
      <van-loading size="22">加载中...</van-loading>
    </div>

    <div v-else-if="addresses.length" class="address-list">
      <article
        v-for="address in addresses"
        :key="address.id"
        class="address-card"
      >
        <div class="address-head">
          <div class="address-person">
            <span>{{ address.receiver_name }}</span>
            <span class="address-phone">{{ address.phone }}</span>
          </div>
          <van-tag v-if="address.is_default" type="primary">默认</van-tag>
        </div>
        <div class="address-detail">{{ formatFullAddress(address) }}</div>
        <div class="address-actions">
          <button
            v-if="!address.is_default"
            type="button"
            class="address-action"
            @click="setDefault(address)"
          >
            设为默认
          </button>
          <button
            type="button"
            class="address-action"
            @click="openEdit(address)"
          >
            编辑
          </button>
          <button
            type="button"
            class="address-action danger"
            @click="remove(address)"
          >
            删除
          </button>
        </div>
      </article>
    </div>

    <van-empty v-else description="还没有收货地址" />

    <footer class="address-footer">
      <van-button block type="primary" class="add-button" @click="openCreate">
        新增地址
      </van-button>
    </footer>

    <AddressFormPopup
      v-model:show="showForm"
      :address="editingAddress"
      @saved="handleSaved"
    />
  </div>
</template>

<style scoped>
.addresses-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--color-bg);
  padding-bottom: 84px;
  padding-bottom: calc(84px + env(safe-area-inset-bottom));
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

.header-spacer {
  width: 44px;
}

.state-panel {
  padding: 80px 0;
  display: flex;
  justify-content: center;
}

.address-list {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.address-card {
  background: var(--color-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: 14px;
}

.address-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.address-person {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
}

.address-phone {
  font-weight: 400;
  color: var(--color-text-secondary);
}

.address-detail {
  margin-top: 7px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--color-text-secondary);
}

.address-actions {
  margin-top: 11px;
  padding-top: 9px;
  border-top: 1px solid var(--color-border);
  display: flex;
  justify-content: flex-end;
  gap: 16px;
}

.address-action {
  border: 0;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 11px;
  padding: 2px 0;
}

.address-action.danger {
  color: var(--color-price);
}

.address-footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--color-card);
  border-top: 1px solid var(--color-border);
  padding: 10px 14px;
  padding-bottom: calc(10px + env(safe-area-inset-bottom));
  z-index: 20;
}

.add-button {
  height: 40px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
}
</style>
