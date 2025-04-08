<script setup>
import { ref, onMounted, defineAsyncComponent } from 'vue';

const AIBlueking = defineAsyncComponent({
  loader: () => import('@blueking/ai-blueking'),
});

onMounted(() => {
  // Use dynamic import() which runs only on the client here
  import('@blueking/ai-blueking/dist/vue3/style.css');
});

const prefix = (import.meta.env.BK_API_URL_TMPL || '')
  .replace('{api_name}', import.meta.env.BK_API_GATEWAY_NAME || '')
  .replace('http', 'https');
const apiUrl = `${prefix}/prod/bk_plugin/plugin_api/assistant/`;

const shortcuts = ref([
  {
    label: '解释',
    key: 'explanation',
    prompt: '请解释以下内容：{{ SELECTED_TEXT }}',
    icon: 'icon-help'
  },
  {
    label: '翻译成英文',
    key: 'translate-en',
    prompt: '请将以下内容翻译成英文：{{ SELECTED_TEXT }}',
    icon: 'icon-translate'
  },
  {
    label: '代码优化',
    key: 'optimize-code',
    prompt: '请优化以下代码：{{ SELECTED_TEXT }}'
  }
]);

const handleShortcutClick = (shortcut) => {
  console.log('快捷操作被点击:', shortcut.label);
};
</script>

# 快捷操作 Demo

:::tip
本页面可以直接体验小鲸的聊天功能，可以直接划词体验快捷操作功能
:::

这个示例展示如何配置和使用 AI 小鲸的快捷操作功能，包括文本选中弹出菜单和预设快捷按钮。

<ClientOnly>
<AIBlueking 
  :url="apiUrl"
  :shortcuts="shortcuts"
  :enable-popup="true"
  @shortcut-click="handleShortcutClick"
/>
</ClientOnly>


## 关键代码讲解

### 1. 配置快捷操作

```js
const shortcuts = ref([
  {
    label: '解释',
    key: 'explanation',
    prompt: '请解释以下内容：{{ SELECTED_TEXT }}',
    icon: 'icon-help'
  },
  {
    label: '翻译成英文',
    key: 'translate-en',
    prompt: '请将以下内容翻译成英文：{{ SELECTED_TEXT }}',
    icon: 'icon-translate'
  },
  {
    label: '代码优化',
    key: 'optimize-code',
    prompt: '请优化以下代码：{{ SELECTED_TEXT }}'
  }
]);
```

### 2. 启用文本选中功能

```vue
<AIBlueking :url="apiUrl"
  :shortcuts="shortcuts"
  :enable-popup="true"/>
```

### 3. 监听快捷操作点击
如果需要监听快捷操作点击事件，可以添加 `@shortcut-click` 事件监听器。
```js
const handleShortcutClick = (shortcut) => {
  // 可以在这里添加自定义逻辑
  console.log('快捷操作被点击:', shortcut.label);
};
```

### 4. 编程式调用快捷操作
如果需要编程式调用快捷操作，可以调用 `sendChat` 方法，并传入 `shortcut` 参数。
具体可以参考 [编程式调用指南](/guide/advanced-usage/programmatic-control)

## 注意事项

- `SELECTED_TEXT` 是固定占位符，会自动替换为选中的文本， 必须保持以下格式
```
{{ SELECTED_TEXT }}
```
- 如果没有配置 `shortcuts`，即使 `enablePopup` 为 true 也不会显示菜单
- 图标需要使用项目已有的图标类名
