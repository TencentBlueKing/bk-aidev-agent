# AI 骨架屏规范

> 本文档描述 chat-x 中骨架屏（Skeleton Screen）的实现规范，便于在其他项目中复用。**无独立组件**，采用纯 CSS 类 + 布局复用的方案。

---

## 1. 概述

| 项目 | 说明 |
|------|------|
| 实现方式 | 纯 CSS，无 Vue/React 组件 |
| 核心类名 | `ai-skeleton-element` |
| 动效 | 横向流光（shimmer）动画 |
| 扩展 | 通过组合类控制尺寸、圆角 |

---

## 2. 交互规范

### 2.1 何时使用骨架屏

- **异步加载**：接口请求中、数据尚未就绪时
- **切换占位**：Tab 切换、详情拉取中
- **列表占位**：原因标签、选项列表等异步获取时

### 2.2 状态切换

```
loading = true  → 渲染骨架屏占位块
loading = false → 渲染真实内容
```

- 用 `v-if="loading"` / `v-else` 或 `loading ? 骨架 : 内容` 做互斥切换
- 骨架屏数量应尽量贴近最终内容结构（如列表 8 项、详情 6 行）

### 2.3 布局一致性

- 骨架块尺寸、间距应与真实内容布局保持一致
- 通过组件内 scoped 样式定义尺寸类，叠加 `.ai-skeleton-element`

---

## 3. 样式规范

### 3.1 全局样式（必须引入）

将以下内容放入全局样式文件（如 `global.scss`），或在使用骨架屏的入口统一导入：

```scss
.ai-skeleton-element {
  position: relative;
  display: flex;
  width: 100%;
  overflow: hidden;

  &::after {
    position: absolute;
    inset-inline: -150%;
    top: 0;
    bottom: 0;
    content: '';
    background: linear-gradient(
      90deg,
      rgb(0 0 0 / 6%) 25%,
      rgb(0 0 0 / 15%) 37%,
      rgb(0 0 0 / 6%) 63%
    );
    animation-name: ai-skeleton-loading;
    animation-duration: 1.4s;
    animation-timing-function: ease;
    animation-iteration-count: infinite;
  }

  &.skeleton-element-lg {
    border-radius: 50%;
  }
}

@keyframes ai-skeleton-loading {
  0% {
    transform: translateX(-37.5%);
  }
  100% {
    transform: translateX(37.5%);
  }
}
```

### 3.2 样式说明

| 属性 | 作用 |
|------|------|
| `::after` 伪元素 | 承载流光效果，不占用布局 |
| `inset-inline: -150%` | 伪元素超出容器，实现左右扫过 |
| `linear-gradient` | 25%→37%→63% 形成亮-暗-亮条纹 |
| `ai-skeleton-loading` | 水平位移，形成流动感 |
| `skeleton-element-lg` | 圆形变体（如头像占位） |

### 3.3 流光颜色

- 默认：`rgb(0 0 0 / 6%)`、`rgb(0 0 0 / 15%)`
- 深色背景项目可自行调整为 `rgb(255 255 255 / ...)` 等

---

## 4. 使用指南

### 4.1 基础用法

1. 保证全局样式已引入
2. 在占位元素上添加 `ai-skeleton-element`
3. 在组件样式中定义尺寸（width、height、border-radius 等）

### 4.2 Vue 模板示例

#### 场景 A：列表项占位（如标签列表）

```vue
<template>
  <div class="list-container">
    <template v-if="loading">
      <div
        v-for="i in 8"
        :key="i"
        class="list-item ai-skeleton-element"
      />
    </template>
    <template v-else>
      <div
        v-for="item in items"
        :key="item.id"
        class="list-item"
      >
        {{ item.name }}
      </div>
    </template>
  </div>
</template>

<style lang="scss" scoped>
.list-container {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;

  .ai-skeleton-element {
    width: 70px;
    height: 22px;
    border-radius: 2px;
  }

  .list-item {
    /* 真实项样式，与骨架尺寸一致 */
    height: 22px;
    padding: 0 8px;
    border-radius: 2px;
  }
}
</style>
```

#### 场景 B：详情区块占位（标题 + 多行）

```vue
<template>
  <div class="detail-panel">
    <template v-if="loading">
      <h3 class="detail-title">
        <span>标题：</span>
        <span class="skeleton-title ai-skeleton-element" />
      </h3>
      <div class="skeleton-section">
        <div class="skeleton-heading ai-skeleton-element" />
        <div
          v-for="i in 6"
          :key="i"
          class="skeleton-row ai-skeleton-element"
        />
      </div>
      <div class="skeleton-section">
        <div class="skeleton-heading ai-skeleton-element" />
        <div
          v-for="i in 4"
          :key="i"
          class="skeleton-row ai-skeleton-element"
        />
      </div>
    </template>
    <template v-else>
      <!-- 真实内容 -->
    </template>
  </div>
</template>

<style lang="scss" scoped>
.skeleton-title {
  display: inline-block;
  width: 120px;
  height: 20px;
  vertical-align: middle;
  border-radius: 2px;
}

.skeleton-section {
  margin-bottom: 16px;
}

.skeleton-heading {
  width: 80px;
  height: 22px;
  margin-bottom: 8px;
  border-radius: 2px;
}

.skeleton-row {
  height: 20px;
  margin-bottom: 12px;
  border-radius: 2px;
}
</style>
```

#### 场景 C：圆形占位（如头像）

```vue
<template>
  <div
    v-if="loading"
    class="avatar-placeholder ai-skeleton-element skeleton-element-lg"
  />
  <img
    v-else
    :src="avatarUrl"
    class="avatar-img"
  />
</template>

<style lang="scss" scoped>
.avatar-placeholder,
.avatar-img {
  width: 40px;
  height: 40px;
}
</style>
```

### 4.3 尺寸参考速查

| 用途 | width | height | 说明 |
|------|-------|--------|------|
| 标签/按钮 | 70px | 22px | 列表项占位 |
| 标题 | 120px | 20px | 行内标题 |
| 小节标题 | 80px | 22px | 区块 heading |
| 内容行 | 100% | 20px | 多行文本占位，margin-bottom: 12px |
| 头像 | 40px | 40px | 叠加 `skeleton-element-lg` 得圆形 |

---

## 5. 实现检查清单（供 AI / Vibecoding）

- [ ] 全局样式已引入（`.ai-skeleton-element` + `@keyframes ai-skeleton-loading`）
- [ ] 使用 `loading` 状态控制 `v-if` / `v-else` 切换骨架与真实内容
- [ ] 骨架元素同时具有 `ai-skeleton-element` 和尺寸类
- [ ] 尺寸类在组件 scoped 样式中定义，与真实内容布局一致
- [ ] 列表占位数量合理（如 6–8 项），避免过多或过少
- [ ] 圆形占位使用 `skeleton-element-lg` 修饰

---

## 6. 项目内参考位置

| 文件 | 用途 |
|------|------|
| `packages/chat-x/src/styles/global.scss` | 骨架屏全局样式定义 |
| `packages/chat-x/src/components/message-tools/user-feedback/user-feedback.vue` | 标签列表 8 项骨架 |
| `packages/chat-x/src/components/chat-content/bk-flow-content/bk-flow-node-detail.vue` | 详情标题 + 多行骨架 |
