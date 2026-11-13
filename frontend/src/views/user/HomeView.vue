<template>
  <div class="page home-page">
    <header class="home-header">
      <div class="brand">
        <div class="brand-logo">AI</div>
        <div>
          <div class="brand-title">AI 找货</div>
          <div class="brand-sub">对话式导购助手</div>
        </div>
      </div>
    </header>
    <main class="home-body">
      <div class="empty-card">
        <div class="empty-avatar">AI</div>
        <h2>AI 导购即将上线</h2>
        <p>当前为 M0 项目骨架</p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.home-page {
  min-height: 100vh;
  background: var(--color-bg);
}

.home-header {
  height: 58px;
  background: #fff;
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid #eef0f3;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-logo {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--color-primary-gradient);
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-title {
  font-size: 15px;
  font-weight: 700;
  line-height: 1.1;
}

.brand-sub {
  font-size: 10px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}

.home-body {
  padding: 16px;
}

.empty-card {
  background: #fff;
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: 36px 20px;
  text-align: center;
}

.empty-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  margin: 0 auto 14px;
  background: var(--color-primary-gradient);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-card h2 {
  font-size: 16px;
  margin: 0 0 6px;
}

.empty-card p {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 0;
}
</style>
