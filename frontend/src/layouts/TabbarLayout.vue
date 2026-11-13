<template>
  <div class="app-shell">
    <main class="app-main">
      <router-view />
    </main>
    <van-tabbar route active-color="#FF5A1F" inactive-color="#9AA0A6">
      <van-tabbar-item replace to="/" icon="chat-o">AI 找货</van-tabbar-item>
      <van-tabbar-item replace to="/me" icon="user-o">我的</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--color-bg);
}

.app-main {
  padding-bottom: 56px;
}

:deep(.van-tabbar) {
  height: 56px;
}
</style>
