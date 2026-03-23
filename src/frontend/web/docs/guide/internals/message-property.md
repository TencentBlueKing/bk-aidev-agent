# 消息属性系统

消息属性（Message Property）是 AI 小鲸 v2.0 中用于为消息附加额外元数据的机制。通过消息属性，你可以实现引用上下文、快捷指令参数传递等高级功能。

## IMessageProperty 接口

```typescript
interface IMessageProperty {
  extra?: {
    /** 引用内容：支持纯文本或结构化引用 */
    cite?: string | {
      type: 'structured';
      title: string;
      data: { key: string; value: string }[];
    };
    /** 快捷指令 ID */
    command?: string;
    /** 上下文参数列表 */
    context?: Array<{ key: string; value: unknown }>;
    /** 快捷指令对象 */
    shortcut?: Shortcut;
  };
}
```

## 纯文本引用

最简单的引用方式，直接传入文本字符串作为引用内容：

```typescript
const property: IMessageProperty = {
  extra: {
    cite: '这是需要引用的文本内容，例如一段代码或文档片段',
  },
};

// 通过 ChatBot 发送带引用的消息
chatBotRef.value?.sendMessage('请解释这段代码', { property });
```

### 效果

消息发送后，AI 会收到用户的提问文本以及引用的上下文，引用内容会在消息气泡中以特殊样式展示。

### 使用场景

- 引用代码片段让 AI 分析
- 引用文档段落让 AI 总结
- 引用错误日志让 AI 排查问题

## 结构化引用

对于复杂的引用内容，可以使用结构化引用，以键值对的形式组织数据：

```typescript
const property: IMessageProperty = {
  extra: {
    cite: {
      type: 'structured',
      title: '服务器监控信息',
      data: [
        { key: 'CPU 使用率', value: '85%' },
        { key: '内存使用率', value: '72%' },
        { key: '磁盘使用率', value: '91%' },
        { key: '活跃连接数', value: '1,234' },
        { key: '错误率', value: '0.5%' },
      ],
    },
  },
};

chatBotRef.value?.sendMessage('请分析这台服务器的状态，给出优化建议', { property });
```

### 效果

结构化引用会以表格或卡片的形式展示在消息气泡中，数据结构清晰、可读性强。

### 使用场景

- 引用监控数据让 AI 分析
- 引用表格数据让 AI 处理
- 引用配置信息让 AI 审查

## 快捷指令上下文

当用户通过快捷指令发送消息时，可以附带指令 ID 和上下文参数：

```typescript
const property: IMessageProperty = {
  extra: {
    command: 'code-review',  // 快捷指令 ID
    context: [
      { key: 'language', value: 'typescript' },
      { key: 'input', value: '被审查的代码内容...' },
      { key: 'standard', value: '企业编码规范 v2.0' },
    ],
  },
};

chatBotRef.value?.sendMessage('请审查以下代码', { property });
```

### 带完整快捷指令对象

```typescript
const shortcut: Shortcut = {
  id: 'code-review',
  name: '代码审查',
  description: '审查代码质量并给出改进建议',
  template: '请按照 {{standard}} 审查以下 {{language}} 代码：\n{{input}}',
};

const property: IMessageProperty = {
  extra: {
    command: shortcut.id,
    shortcut: shortcut,
    context: [
      { key: 'language', value: 'python' },
      { key: 'input', value: 'def foo(x):\n  return x+1' },
      { key: 'standard', value: 'PEP 8' },
    ],
  },
};

chatBotRef.value?.sendMessage('代码审查', { property });
```

## 数据流

消息属性从用户界面到后端的完整数据流如下：

![消息属性数据流](/images/guide/message-property-flow.png)

### 详细步骤说明

1. **UI 构建属性**：用户操作（如选中文本引用、选择快捷指令）触发 property 对象的构建
2. **Manager 接收**：`ChatBusinessManager.sendMessage` 接收消息内容和 property
3. **模块调用**：通过 `agentModule.chat` 将 property 作为 `data` 参数的一部分传递
4. **HTTP 请求**：property 被序列化到 HTTP POST 请求的 Body 中
5. **后端处理**：后端 Agent 服务解析 property，根据 cite、command、context 等字段调整 AI 的行为

## 用例与代码示例

### 用例一：代码片段引用

用户选中页面上的代码，点击"向 AI 提问"：

```typescript
function askAIAboutCode(selectedCode: string) {
  chatBotRef.value?.sendMessage('请解释这段代码的功能', {
    property: {
      extra: {
        cite: selectedCode,
      },
    },
  });
}
```

### 用例二：工单信息引用

从工单系统引用结构化信息：

```typescript
function askAIAboutTicket(ticket: Ticket) {
  chatBotRef.value?.sendMessage('请帮我分析这个工单并给出处理建议', {
    property: {
      extra: {
        cite: {
          type: 'structured',
          title: `工单 #${ticket.id}`,
          data: [
            { key: '标题', value: ticket.title },
            { key: '优先级', value: ticket.priority },
            { key: '状态', value: ticket.status },
            { key: '描述', value: ticket.description },
            { key: '创建时间', value: ticket.createdAt },
          ],
        },
      },
    },
  });
}
```

### 用例三：快捷指令执行

用户从快捷指令面板选择指令后自动填充参数：

```typescript
function executeShortcut(shortcut: Shortcut, params: Record<string, string>) {
  const context = Object.entries(params).map(([key, value]) => ({
    key,
    value,
  }));

  chatBotRef.value?.sendMessage(shortcut.name, {
    property: {
      extra: {
        command: shortcut.id,
        shortcut,
        context,
      },
    },
  });
}

// 使用示例
executeShortcut(
  { id: 'translate', name: '翻译', description: '翻译文本', template: '...' },
  { input: 'Hello, world!', targetLang: '中文' }
);
```

### 用例四：组合引用与指令

同时引用上下文内容并指定处理指令：

```typescript
function reviewCodeWithStandard(code: string, standard: string) {
  chatBotRef.value?.sendMessage('代码审查', {
    property: {
      extra: {
        cite: code,
        command: 'code-review',
        context: [
          { key: 'standard', value: standard },
          { key: 'language', value: detectLanguage(code) },
        ],
      },
    },
  });
}
```

### 用例五：通过 setCiteText 设置引用

除了在 `sendMessage` 中传入 property，还可以通过 `setCiteText` 预设引用文本：

```typescript
// 先设置引用（会在输入框上方显示引用预览）
chatBotRef.value?.setCiteText('需要引用的内容...');

// 之后用户手动输入问题并发送时，引用会自动附带
// 也可以调用 focusInput 引导用户输入
chatBotRef.value?.focusInput();
```
