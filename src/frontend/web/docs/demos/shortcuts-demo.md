<script setup>
import { ref, onMounted, defineAsyncComponent } from 'vue';

const AIBlueking = defineAsyncComponent({
  loader: () => import('@blueking/ai-blueking'),
});

onMounted(() => {
  // Use dynamic import() which runs only on the client here
  import('@blueking/ai-blueking/dist/vue3/style.css');
});

const apiUrl = import.meta.env.BK_API_URL_TMPL || ''

const shortcuts = ref([
  {
    id: 'explanation',
    name: '解释',
    icon: 'bkai-help',
    components: [
      {
        type: 'textarea',
        key: 'content',
        label: '内容',
        fillBack: true,
        placeholder: '请输入需要解释的内容'
      }
    ]
  },
  {
    id: 'translate-en',
    name: '翻译成英文',
    icon: 'bkai-translate',
    components: [
      {
        type: 'textarea',
        key: 'text',
        label: '待翻译文本',
        fillBack: true,
        placeholder: '请输入需要翻译的内容'
      }
    ]
  },
  {
    id: 'optimize-code',
    name: '代码优化',
    icon: 'bkai-code',
    components: [
      {
        type: 'textarea',
        key: 'code',
        label: '代码',
        fillBack: true,
        placeholder: '请输入需要优化的代码'
      },
      {
        type: 'select',
        key: 'language',
        label: '语言',
        placeholder: '请选择编程语言',
        options: [
          { label: 'JavaScript', value: 'javascript' },
          { label: 'TypeScript', value: 'typescript' },
          { label: 'Python', value: 'python' },
          { label: 'Java', value: 'java' }
        ]
      }
    ]
  }
]);

const handleShortcutClick = (shortcut) => {
  console.log('快捷操作被点击:', shortcut.name);
};

const triggerShortcut = () => {
  // 找到对应ID的快捷操作
  const shortcut = shortcuts.value.find(s => s.id === 'explanation');
  if (!shortcut) return;
  
  // 可以手动设置要填充的文本
  const textComponent = shortcut.components.find(c => c.fillBack);
  if (textComponent) {
    textComponent.selectedText = '这是一段需要解释的文本';
  }
  
  // 触发快捷操作
  aiBlueking.value.handleShortcutClick(shortcut);
};
</script>

# 快捷操作 Demo

::: warning 版本更新提示
v1.1.0版本对快捷操作进行了重大更新，现在支持自定义表单组件，请确保您使用的是最新的接口定义。
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
    id: 'explanation',
    name: '解释',
    icon: 'bkai-help',
    components: [
      {
        type: 'textarea',
        key: 'content',
        label: '内容',
        fillBack: true,
        placeholder: '请输入需要解释的内容'
      }
    ]
  },
  {
    id: 'translate-en',
    name: '翻译成英文',
    icon: 'bkai-translate',
    components: [
      {
        type: 'textarea',
        key: 'text',
        label: '待翻译文本',
        fillBack: true,
        placeholder: '请输入需要翻译的内容'
      }
    ]
  },
  {
    id: 'optimize-code',
    name: '代码优化',
    icon: 'bkai-code',
    components: [
      {
        type: 'textarea',
        key: 'code',
        label: '代码',
        fillBack: true,
        placeholder: '请输入需要优化的代码'
      },
      {
        type: 'select',
        key: 'language',
        label: '语言',
        placeholder: '请选择编程语言',
        options: [
          { label: 'JavaScript', value: 'javascript' },
          { label: 'TypeScript', value: 'typescript' },
          { label: 'Python', value: 'python' },
          { label: 'Java', value: 'java' }
        ]
      }
    ]
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
  console.log('快捷操作被点击:', shortcut.name);
};
```

### 4. 编程式调用快捷操作
如果需要编程式调用快捷操作，可以使用 `handleShortcutClick` 方法：

```js
// 获取组件引用
const aiBlueking = ref(null);

// 触发快捷操作
const triggerShortcut = () => {
  // 找到对应ID的快捷操作
  const shortcut = shortcuts.value.find(s => s.id === 'explanation');
  if (!shortcut) return;
  
  // 可以手动设置要填充的文本
  const textComponent = shortcut.components.find(c => c.fillBack);
  if (textComponent) {
    textComponent.selectedText = '这是一段需要解释的文本';
  }
  
  // 触发快捷操作
  aiBlueking.value.handleShortcutClick(shortcut);
};
```

具体可以参考 [编程式调用指南](/guide/advanced-usage/programmatic-control)

## 注意事项

- 在v1.1版本中，快捷操作使用组件配置（`components`）替代了原先的 `prompt` 字段
- 每个组件都有自己的类型和属性，目前支持 `text`、`textarea`、`number` 和 `select` 四种类型
- 要实现选中文本填充功能，需要设置组件的 `fillBack: true` 属性
- 表单收集的数据将以数组形式发送到后端，每个项为一个对象，包含组件对应的数据
- context 参数同样以数组形式传递，与表单数据合并后发送到后端
- 如果没有配置 `shortcuts`，即使 `enablePopup` 为 true 也不会显示菜单
- 图标需要使用项目已有的图标类名（建议使用 `bkai-` 前缀的图标）
