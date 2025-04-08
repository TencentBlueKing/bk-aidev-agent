<template>
  <div class="feature-cards">
    <div class="feature-card">
      <div class="card-icon">🎯</div>
      <h3>纯前端测试</h3>
      <p>无需后端服务，专注于组件功能验证</p>
    </div>
    <div class="feature-card">
      <div class="card-icon">🛠</div>
      <h3>完整配置</h3>
      <p>包含所有可配置项，方便调试样式和交互</p>
    </div>
    <div class="feature-card">
      <div class="card-icon">📝</div>
      <h3>模拟数据</h3>
      <p>使用静态数据模拟各种对话场景</p>
    </div>
  </div>
</template>

<script setup lang="ts"></script>

<style lang="scss" scoped>
  .feature-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 24px;
    margin-bottom: 40px;
  }

  .feature-card {
    padding: 24px;
    text-align: center;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
    transition: transform 0.2s;

    &:hover {
      transform: translateY(-4px);
    }

    .card-icon {
      margin-bottom: 16px;
      font-size: 32px;
    }

    h3 {
      margin-bottom: 12px;
      font-size: 18px;
      color: #333;
    }

    p {
      line-height: 1.6;
      color: #666;
    }
  }
</style>
