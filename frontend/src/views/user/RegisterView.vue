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
  nickname: '',
  password: '',
  confirmPassword: '',
})

async function handleSubmit(): Promise<void> {
  if (loading.value) {
    return
  }
  const username = form.username.trim()
  if (!username || !form.password) {
    showToast('请填写用户名和密码')
    return
  }
  if (!/^[A-Za-z0-9_]{3,50}$/.test(username)) {
    showToast('用户名需为 3-50 位字母、数字或下划线')
    return
  }
  if (form.nickname.trim().length > 50) {
    showToast('昵称不能超过 50 个字符')
    return
  }
  if (form.password.length < 6) {
    showToast('密码至少 6 位')
    return
  }
  if (new TextEncoder().encode(form.password).length > 72) {
    showToast('密码不能超过 72 字节')
    return
  }
  if (form.password !== form.confirmPassword) {
    showToast('两次输入的密码不一致')
    return
  }

  loading.value = true
  try {
    await auth.registerAndLogin({
      username,
      password: form.password,
      nickname: form.nickname.trim() || null,
    })
    showToast('注册成功')
    const redirect =
      typeof route.query.redirect === 'string' &&
      route.query.redirect.startsWith('/') &&
      !route.query.redirect.startsWith('//')
        ? route.query.redirect
        : '/'
    await router.replace(redirect)
  } catch (error) {
    showToast(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="register-page">
    <div class="register-logo">AI</div>
    <h1 class="register-title">注册新账号</h1>
    <p class="register-subtitle">注册后自动登录</p>

    <van-form class="register-form" @submit="handleSubmit">
      <van-field
        v-model="form.username"
        name="username"
        placeholder="用户名"
        autocomplete="username"
        autocapitalize="off"
        autocorrect="off"
        :spellcheck="false"
        maxlength="50"
        class="register-field"
      />
      <van-field
        v-model="form.nickname"
        name="nickname"
        placeholder="昵称（可选）"
        autocomplete="nickname"
        maxlength="50"
        class="register-field"
      />
      <van-field
        v-model="form.password"
        type="password"
        name="password"
        placeholder="密码"
        autocomplete="new-password"
        maxlength="128"
        class="register-field"
      />
      <van-field
        v-model="form.confirmPassword"
        type="password"
        name="confirmPassword"
        placeholder="确认密码"
        autocomplete="new-password"
        maxlength="128"
        class="register-field"
      />
      <van-button
        block
        type="primary"
        native-type="submit"
        :loading="loading"
        class="register-submit"
      >
        注册并登录
      </van-button>
    </van-form>

    <van-button
      block
      plain
      type="primary"
      :disabled="loading"
      class="back-button"
      @click="router.push('/login')"
    >
      返回登录
    </van-button>
  </div>
</template>

<style scoped>
.register-page {
  min-height: 100vh;
  background: var(--color-card);
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 30px;
}

.register-logo {
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

.register-title {
  font-size: 22px;
  margin: 0 0 4px;
}

.register-subtitle {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 0 0 26px;
}

.register-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.register-field {
  border-radius: 12px;
  background: var(--color-field-bg);
}

:deep(.register-field::after) {
  display: none;
}

:deep(.register-field .van-field__control) {
  font-size: 13px;
}

.register-submit {
  height: 44px;
  margin-top: 6px;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 600;
}

.back-button {
  height: 44px;
  margin-top: 9px;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 600;
  border-color: var(--color-primary-border);
}
</style>
