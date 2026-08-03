# 测试指南

项目使用 vitest + happy-dom + @vue/test-utils 进行单元测试。

---

## 运行测试

```bash
# 运行测试
pnpm test

# 监听模式
pnpm test:watch
```

---

## 测试文件结构

```
src/__tests__/helpers.ts                    # Mock 工厂（createMockChatHelper 等）
src/manager/business/__tests__/             # 业务管理器测试
  ├── chat-business-manager.spec.ts
  ├── share-business-manager.spec.ts
  └── shortcut-manager.spec.ts
src/components/composables/__tests__/       # Composable 测试
  ├── use-chatbot-init.spec.ts
  ├── use-chatbot-state.spec.ts
  ├── use-message-sender.spec.ts
  ├── use-shortcuts.spec.ts
  ├── use-tool-actions.spec.ts
  └── use-share-selection.spec.ts
```

---

## Mock 工厂

项目提供了统一的 Mock 工厂函数（位于 `src/__tests__/helpers.ts`）：

```typescript
import { createMockChatHelper, createMockChatBusinessManager, createMockEmit } from '../__tests__/helpers';

// 创建完整的 mock chatHelper（agent/session/message 模块）
const chatHelper = createMockChatHelper();

// 创建 mock 业务管理器
const chatBM = createMockChatBusinessManager();

// 创建 mock emit 函数
const emit = createMockEmit();
```

---

## 测试含生命周期的 Composable（withSetup 模式）

由于 Vue composable 需要在 `setup()` 上下文中运行，测试时需要使用 `withSetup` 包装：

```typescript
import { defineComponent } from 'vue';
import { mount, flushPromises } from '@vue/test-utils';

function withSetup(composableFn: () => any) {
  let result: any;
  const Comp = defineComponent({
    setup() {
      result = composableFn();
      return () => null;
    },
  });
  const wrapper = mount(Comp);
  return { result, wrapper };
}

// 使用
const { result, wrapper } = withSetup(() => useChatbotInit({ ... }));
await flushPromises();
expect(result.isInitialized.value).toBe(true);
wrapper.unmount();
```

---

## 测试编写指南

### Manager 测试示例

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ChatBusinessManager } from '../chat-business-manager';
import { createMockChatHelper } from '../../../__tests__/helpers';

describe('ChatBusinessManager', () => {
  let chatHelper: ReturnType<typeof createMockChatHelper>;
  let manager: ChatBusinessManager;

  beforeEach(() => {
    chatHelper = createMockChatHelper();
    manager = new ChatBusinessManager(
      chatHelper.agent,
      chatHelper.message,
      chatHelper.session,
    );
  });

  it('should send message', async () => {
    await manager.sendMessage('hello', 'session-1');
    expect(chatHelper.agent.chat).toHaveBeenCalledWith('hello', 'session-1');
  });
});
```

### Composable 测试示例

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { defineComponent } from 'vue';
import { useChatbotInit } from '../use-chatbot-init';
import { createMockEmit } from '../../../__tests__/helpers';

function withSetup(fn: () => any) {
  let result: any;
  const wrapper = mount(defineComponent({
    setup() { result = fn(); return () => null; },
  }));
  return { result, wrapper };
}

describe('useChatbotInit', () => {
  it('should initialize', async () => {
    const { result, wrapper } = withSetup(() =>
      useChatbotInit({
        props: { url: '/api/' },
        emit: createMockEmit(),
        scrollToBottom: vi.fn(),
      })
    );
    await flushPromises();
    expect(result.isInitialized.value).toBe(true);
    wrapper.unmount();
  });
});
```
