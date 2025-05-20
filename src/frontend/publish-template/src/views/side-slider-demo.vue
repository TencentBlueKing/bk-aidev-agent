<template>
  <div class="Layout">
    <div class="VPContent is-home" id="VPContent">
      <div class="VPHome">
        <!-- 头部英雄区域 -->
        <div class="VPHero has-image VPHomeHero">
          <div class="container">
            <div class="main">
              <h1 class="heading">
                <span class="name clip">AI 小鲸</span>
                <span class="text">智能对话组件</span>
              </h1>
              <p class="tagline">开箱即用的 Vue 智能对话解决方案，支持 Vue2/Vue3</p>
              <div class="actions">
                <div class="action">
                  <a class="VPButton medium brand" @click="aiBlueking?.handleShow()">立即体验</a>
                </div>
              </div>
            </div>
            <div class="image">
              <div class="image-container">
                <div class="image-bg"></div>
                <img class="VPImage image-src" :src="AILogo" alt="AI Blueking">
              </div>
            </div>
          </div>
        </div>

        <!-- 特性卡片区域 -->
        <div class="VPFeatures VPHomeFeatures">
          <div class="container">
            <div class="items">
              <div class="grid-6 item">
                <div class="VPLink no-icon VPFeature">
                  <article class="box">
                    <div class="icon">💬</div>
                    <h2 class="title">实时对话</h2>
                    <p class="details">支持流式输出，让对话更自然流畅</p>
                  </article>
                </div>
              </div>
              <div class="grid-6 item">
                <div class="VPLink no-icon VPFeature">
                  <article class="box">
                    <div class="icon">📎</div>
                    <h2 class="title">内容引用</h2>
                    <p class="details">选中文本即可快速引用并提问</p>
                  </article>
                </div>
              </div>
              <div class="grid-6 item">
                <div class="VPLink no-icon VPFeature">
                  <article class="box">
                    <div class="icon">⚡️</div>
                    <h2 class="title">快捷操作</h2>
                    <p class="details">支持预设常用功能和提示词</p>
                  </article>
                </div>
              </div>
              <div class="grid-6 item">
                <div class="VPLink no-icon VPFeature">
                  <article class="box">
                    <div class="icon">🖱️</div>
                    <h2 class="title">可拖拽界面</h2>
                    <p class="details">自由调整窗口位置和大小</p>
                  </article>
                </div>
              </div>
              <div class="grid-6 item">
                <div class="VPLink no-icon VPFeature">
                  <article class="box">
                    <div class="icon">📦</div>
                    <h2 class="title">开箱即用</h2>
                    <p class="details">传入 Agent 地址即可快速接入业务</p>
                  </article>
                </div>
              </div>
              <div class="grid-6 item">
                <div class="VPLink no-icon VPFeature">
                  <article class="box">
                    <div class="icon">🔄</div>
                    <h2 class="title">跨框架支持</h2>
                    <p class="details">同时支持 Vue2 和 Vue3 框架</p>
                  </article>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 文档区域占位 -->
        <div class="vp-doc container" style="--vp-offset: calc(50% - 1272.5px);">
          <div style="position:relative;">
            <div></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 页脚 -->
    <footer class="VPFooter">
      <div class="container">
        <p class="message">All Rights Reserved. 腾讯蓝鲸 版权所有</p>
        <p class="copyright">Copyright © 2025 Blueking</p>
      </div>
    </footer>

    <!-- AIBlueking组件 -->
    <AIBlueking
      ref="aiBlueking"
      :hide-nimbus="false"
      :url="url"
    />
  </div>
</template>

<script lang="ts" setup>
  import { ref } from 'vue';
  import AILogo from '../assets/svg/ai-logo.svg';

  import AIBlueking, { AIBluekingExpose } from '@blueking/ai-blueking';
  import '@blueking/ai-blueking/dist/vue3/style.css';


  const aiBlueking = ref<AIBluekingExpose | null>(null);

  const url = ref(window.BK_API_PREFIX);

  const quickActions = (shortcut: { label: string; prompt: string; key: string }, cite: string) => {
    aiBlueking.value?.handleShow();

    aiBlueking.value?.sendChat({
      message: shortcut.label,
      cite,
      shortcut,
    });
  };

</script>

<style lang="postcss" scoped>
  .Layout {
    display: flex;
    flex-direction: column;
    min-height: calc(100vh - 52px);
  }

  .VPContent {
    flex: 1;
  }

  /* 英雄区域样式 */
  .VPHero {
    padding: 40px 0;
    text-align: center;
    position: relative;
    overflow: hidden;
  }

  .VPHero .container {
    display: flex;
    max-width: 1200px;
    margin: 0 auto;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
  }

  .VPHero .main {
    flex: 1;
    text-align: left;
  }

  .VPHero .heading {
    font-size: 56px;
    line-height: 1.2;
    font-weight: 600;
    margin-bottom: 16px;
    background-image: linear-gradient(120deg, #3884FF, #5E3BFF);
    color: transparent;
    -webkit-background-clip: text;
    background-clip: text;
  }

  .VPHero .name {
    display: block;
    font-size: 64px;
    font-weight: 700;
  }

  .VPHero .text {
    font-size: 42px;
    font-weight: 600;
  }

  .VPHero .tagline {
    font-size: 24px;
    color: #666;
    margin-bottom: 32px;
  }

  .VPHero .actions {
    display: flex;
    gap: 16px;
  }

  .VPButton {
    display: inline-block;
    padding: 10px 24px;
    border-radius: 20px;
    font-size: 16px;
    font-weight: 500;
    transition: all 0.2s;
    cursor: pointer;
    text-decoration: none;
  }

  .VPButton.brand {
    background-color: #3884FF;
    color: white;
  }

  .VPButton.brand:hover {
    background-color: #2e6ed4;
  }

  .VPButton.alt {
    background-color: rgba(56, 132, 255, 0.1);
    color: #3884FF;
    border: 1px solid rgba(56, 132, 255, 0.3);
  }

  .VPButton.alt:hover {
    background-color: rgba(56, 132, 255, 0.15);
    border-color: rgba(56, 132, 255, 0.5);
  }

  .VPHero .image {
    flex: 1;
    display: flex;
    justify-content: center;
    max-width: 400px;
  }

  .VPHero .image-container {
    position: relative;
    width: 320px;
    height: 320px;
  }

  .VPHero .image-bg {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: radial-gradient(circle, rgba(56, 132, 255, 0.2) 0%, rgba(94, 59, 255, 0.1) 50%, rgba(255, 255, 255, 0) 70%);
    border-radius: 50%;
  }

  .VPHero .image-src {
    position: relative;
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  /* 特性区域样式 */
  .VPFeatures {
    padding: 64px 24px;
  }

  .VPFeatures .container {
    max-width: 1200px;
    margin: 0 auto;
  }

  .VPFeatures .items {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 24px;
  }

  .VPFeature .box {
    padding: 24px;
    background-color: #fff;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
    transition: transform 0.2s, box-shadow 0.2s;
  }

  .VPFeature .box:hover {
    transform: translateY(-5px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
  }

  .VPFeature .icon {
    font-size: 32px;
    margin-bottom: 16px;
  }

  .VPFeature .title {
    font-size: 20px;
    font-weight: 600;
    margin-bottom: 12px;
    color: #333;
  }

  .VPFeature .details {
    font-size: 16px;
    color: #666;
    line-height: 1.6;
  }

  /* 页脚样式 */
  .VPFooter {
    padding: 32px 24px;
    background-color: #f2f3f5;
    text-align: center;
  }

  .VPFooter .container {
    max-width: 1200px;
    margin: 0 auto;
  }

  .VPFooter .message {
    font-size: 16px;
    color: #666;
    margin-bottom: 8px;
  }

  .VPFooter .copyright {
    font-size: 14px;
    color: #999;
  }

  /* 响应式设计 */
  @media (max-width: 960px) {
    .VPHero .container {
      flex-direction: column;
      text-align: center;
    }

    .VPHero .main {
      text-align: center;
      margin-bottom: 40px;
    }

    .VPHero .heading {
      font-size: 42px;
    }

    .VPHero .name {
      font-size: 48px;
    }

    .VPHero .text {
      font-size: 32px;
    }

    .VPHero .actions {
      justify-content: center;
    }

    .VPFeatures .items {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (max-width: 640px) {
    .VPHero .heading {
      font-size: 32px;
    }

    .VPHero .name {
      font-size: 36px;
    }

    .VPHero .text {
      font-size: 24px;
    }

    .VPHero .tagline {
      font-size: 18px;
    }

    .VPFeatures .items {
      grid-template-columns: 1fr;
    }
  }
</style>
