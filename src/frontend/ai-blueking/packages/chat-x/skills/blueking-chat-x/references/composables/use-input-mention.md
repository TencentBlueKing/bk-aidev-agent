# useInputMention

> 导入：`import { useInputMentionConsumer, useInputMentionProvider } from '@blueking/chat-x'` ｜ since 0.0.51

useInputMentionProvider 由持有输入框的容器（ChatContainer）提供 insertMention， useInputMentionConsumer 在任意后代取出；无 Provider（只读 / 分享态）时返回 undefined，调用方据此隐藏「引用」入口。 消息区文件卡片与侧栏产物面板即用它把文件以标签形式追加进输入框。 源码位置：src/composables/use-input-mention.ts。

**关联**：chat-container（根容器提供 insertMention，内部转发给 ChatInput 实例）、chat-input（实际执行插入的组件，expose insertMention）、file-artifact-panel（侧栏产物面板据此展示「引用」按钮）、assistant-message（消息内文件卡片据此展示「引用」按钮）

---

# useInputMention 资源插入输入框

> **分类**：composable

把「把某个资源 `@` 进输入框」这件事从组件层级里解耦出来：消息区的文件卡片、侧栏的产物面板可能嵌套得很深，逐层透传输入框实例既啰嗦又容易漏。

## 工作原理

```
ChatContainer（根）
  ├── useInputMentionProvider({
  │     insertMention: item => chatInputRef.value?.insertMention?.(item),
  │   })
  │     └── provide(INPUT_MENTION_TOKEN, context)
  │
  ├── ChatInput（ref="chatInputRef"）
  │     └── expose insertMention → AiSlashInput.appendMention（追加到文档末尾）
  │
  └── MessageContainer → … → ArtifactFileCard / FileArtifactPanel
        └── useInputMentionConsumer() → InputMentionContext | undefined
              └── 有值才渲染「引用」按钮
```

无 Provider 时 `useInputMentionConsumer()` 返回 `undefined`，因此只读 / 分享态（没有输入框）自动不显示引用入口，不需要额外开关。

## 消费方用法

```vue
<template>
  <span
    v-if="inputMention"
    v-tippy="{ content: t('引用') }"
    @click.stop="handleCite"
  >
    <CiteIcon />
  </span>
</template>

<script setup lang="ts">
  import { toArtifactMenuItem, useInputMentionConsumer } from '@blueking/chat-x';

  const props = defineProps<{ file: AIFileInfo }>();

  // 无输入框上下文时为 undefined，据此隐藏入口
  const inputMention = useInputMentionConsumer();

  const handleCite = () => {
    inputMention?.insertMention(toArtifactMenuItem(props.file));
  };
</script>
```

::: warning id 必须与菜单一致
把文件转成菜单条目时统一走 [`toArtifactMenuItem`](/utils/#会话产物收集)：`id` 不一致会导致 `@` 菜单的去重与已插入标签的匹配同时失效（同一个文件既能重复插入、又无法从候选中剔除）。
:::

## 自建容器用法

不使用 [ChatContainer](/components/setup/chat-container)、自行组合 `MessageContainer` + `ChatInput` 时，需要自己提供上下文：

```vue
<script setup lang="ts">
  import { useTemplateRef } from 'vue';
  import { ChatInput, useInputMentionProvider } from '@blueking/chat-x';

  const chatInputRef = useTemplateRef<InstanceType<typeof ChatInput>>('chatInputRef');

  useInputMentionProvider({
    insertMention: item => chatInputRef.value?.insertMention?.(item),
  });
</script>
```

## API

```typescript
export const INPUT_MENTION_TOKEN: unique symbol;

export type InputMentionContext = {
  /** 把一个条目以标签形式追加到输入框，效果等同于用户通过 `@` 菜单选中它 */
  insertMention: (item: IInputMenuItem) => void;
};

export function useInputMentionProvider(context: InputMentionContext): InputMentionContext;

export function useInputMentionConsumer(): InputMentionContext | undefined;
```

| 函数                        | 说明                                                                   |
| --------------------------- | ---------------------------------------------------------------------- |
| `useInputMentionProvider`   | 在祖先 `setup` 中调用，`provide` 上下文并原样返回，便于就地复用         |
| `useInputMentionConsumer`   | 在任意后代 `setup` 中调用，无 Provider 时返回 `undefined`               |

## 注意事项

1. **插入位置不依赖光标**：底层走 `AiSlashInput.appendMention`，标签追加到文档末尾——外部调用时编辑器通常没有焦点，依赖光标会插错位置。
2. **插入的资源可能不在 `menuSources` 里**：`ChatInput` 的 `update:modelValue` 第二参数只回传能在 `menuSources` 中反查到的条目。`ChatContainer` 会自动收集消息里的会话产物，所以经容器使用时产物标签能被反查到。
3. **必须在 `setup` 中调用**：与 Vue `provide` / `inject` 的要求一致。

## 关联组件

- [ChatContainer](../components/setup/chat-container) — 默认的 Provider
- [ChatInput](../components/input/chat-input) — `insertMention` 的实际执行者
- [FileArtifactPanel](../components/message/file-artifact-panel) — 侧栏产物面板的引用入口
- [Utils 工具函数](../utils/) — `collectMessageArtifacts` / `toArtifactMenuItem`
