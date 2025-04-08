# 框架集成与注意事项

AI 小鲸 (AI Blueking) 同时支持 Vue 2 和 Vue 3 项目，但在集成时需要注意一些关键差异。

## Vue 2 与 Vue 3 的主要区别

1.  **引入方式**:
    *   **Vue 3**: 从包的根路径导入组件。
        ```javascript
        import AIBlueking from '@blueking/ai-blueking';
        ```
    *   **Vue 2**: 需要从 `/vue2` 子路径导入。
        ```javascript
        import AIBlueking from '@blueking/ai-blueking/vue2';
        ```

2.  **样式引入**:
    *   **Vue 3**: 引入 `dist/vue3/style.css`。
        ```javascript
        import '@blueking/ai-blueking/dist/vue3/style.css';
        ```
    *   **Vue 2**: 引入 `dist/vue2/style.css`。
        ```javascript
        import '@blueking/ai-blueking/dist/vue2/style.css';
        ```

3.  **获取组件实例与调用方法**:
    *   **Vue 3 (Composition API with `<script setup>`)**: 使用 `ref` 获取实例，通过 `.value` 访问。
        ```typescript
        import { ref } from 'vue';
        import type { AIBluekingInstance } from '@blueking/ai-blueking'; // 可选的类型导入

        const aiBlueking = ref<AIBluekingInstance | null>(null);
        aiBlueking.value?.handleShow();
        const contents = aiBlueking.value?.sessionContents;
        ```
    *   **Vue 3 (Options API)**: 使用 `this.$refs` 获取实例。
       ```javascript
       this.$refs.aiBlueking.handleShow();
       const contents = this.$refs.aiBlueking.sessionContents;
       ```
    *   **Vue 2 (Options API)**: 使用 `this.$refs` 获取实例。
        ```javascript
        this.$refs.aiBlueking.handleShow();
        const contents = this.$refs.aiBlueking.sessionContents;
        ```

4.  **组件定义方式**:
    *   **Vue 3**: 通常使用 Composition API (`<script setup>`) 或 Options API。
    *   **Vue 2**: 使用 Options API。

## 通用注意事项

无论使用哪个框架版本，请注意以下几点：

1.  **必须设置 `url` 属性**: 这是 AI 小鲸与后端服务通信的基础，必须提供一个有效的接口地址。
2.  **全局组件**: 为了获得最佳体验，建议将 `<AIBlueking>` 组件放置在应用的根组件（如 `App.vue`）或布局组件中，确保它在整个应用的生命周期内只被实例化一次，并且可以在任何页面被调用。
3.  **快捷操作占位符**: 在配置 `shortcuts` 时，使用 `{{ SELECTED_TEXT }}` 作为模板字符串中的占位符，它将被实际引用的文本替换。
4.  **样式依赖**: AI 小鲸的样式可能依赖于您项目的基础 UI 库（如 bk-magic-vue），请确保相关基础样式已正确加载。如果遇到样式问题，请检查 CSS 引入