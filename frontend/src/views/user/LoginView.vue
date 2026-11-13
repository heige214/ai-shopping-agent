<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'

import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils/error'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const loading = ref(false)
const form = reactive({
  username: '',
  password: '',
})

async function handleSubmit(): Promise<void> {
  if (loading.value) {
    return
  }
  if (!form.username.trim() || !form.password) {
    showToast('请输入用户名和密码')
    return
  }

  loading.value = true
  try {
    await auth.login({ username: form.username.trim(), password: form.password })
    showToast('登录成功')
    const fallback =
      auth.user?.role === 'agent' || auth.user?.role === 'admin'
        ? '/agent/orders'
        : '/'
    const redirect =
      typeof route.query.redirect === 'string' &&
      route.query.redirect.startsWith('/') &&
      !route.query.redirect.startsWith('//')
        ? route.query.redirect
        : fallback
    await router.replace(redirect)
  } catch (error) {
    showToast(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function goRegister(): void {
  const redirect = route.query.redirect
  router.push({
    path: '/register',
    query: typeof redirect === 'string' ? { redirect } : {},
  })
}
</script>

<template>
  <div class="login-page">
    <div class="login-logo">AI</div>
    <h1 class="login-title">AI 找货</h1>
    <p class="login-subtitle">说出你想找的，AI 帮你挑</p>

    <van-form class="login-form" @submit="handleSubmit">
      <van-field
        v-model="form.username"
        name="username"
        placeholder="用户名"
        autocomplete="username"
        autocapitalize="off"
        autocorrect="off"
        :spellcheck="false"
        maxlength="50"
        class="login-field"
      />
      <van-field
        v-model="form.password"
        type="password"
        name="password"
        placeholder="密码"
        autocomplete="current-password"
        maxlength="128"
        class="login-field"
      />
      <van-button
        block
        type="primary"
        native-type="submit"
        :loading="loading"
        class="login-button"
      >
        登录
      </van-button>
    </van-form>

    <van-button
      block
      plain
      type="primary"
      :disabled="loading"
      class="register-button"
      @click="goRegister"
    >
      注册新账号
    </van-button>
    <p class="login-hint">
      演示账号：demo / demo123<br />
      客服账号：agent / agent123
    </p>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  background: var(--color-card);
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 30px;
}

.login-logo {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  background: var(--color-primary-gradient);
  color: #fff;
  font-weight: 800;
  font-size: 21px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 14px;
}

.login-title {
  font-size: 22px;
  margin: 0 0 4px;
}

.login-subtitle {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 0 0 26px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.login-field {
  border-radius: 12px;
  background: var(--color-field-bg);
}

:deep(.login-field::after) {
  display: none;
}

:deep(.login-field .van-field__control) {
  font-size: 13px;
}

.login-button {
  height: 44px;
  margin-top: 6px;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 600;
}

.register-button {
  height: 44px;
  margin-top: 9px;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 600;
  border-color: var(--color-primary-border);
}

.login-hint {
  text-align: center;
  font-size: 10.5px;
  color: var(--color-text-tertiary);
  margin-top: 16px;
}
</style>
