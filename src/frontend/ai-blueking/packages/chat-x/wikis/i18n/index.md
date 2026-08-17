# 国际化

`@blueking/chat-x` 内置了中英文国际化支持。

<script setup lang="ts">
import { ref, computed } from 'vue';
import { t } from '@blueking/chat-x';

// 模拟当前语言（实际由 Cookie 在页面加载时确定）
const simulateLang = ref<'zh' | 'en'>('zh');

const langKeys = ['发送', '停止', '复制', '重新生成', '点赞', '不满意', '引用', '返回底部', '停止生成', '深度思考', '思考中', '已思考完成', '思考失败', '复制成功', '复制失败', '调用中', '调用成功', '调用失败', '上传文件', '更多'] as const;

const enMap: Record<string, string> = {
  发送: 'Send', 停止: 'Stop', 复制: 'Copy', 重新生成: 'Regenerate',
  点赞: 'Like', 不满意: 'Unsatisfied', 引用: 'Quote', 返回底部: 'Return to bottom',
  停止生成: 'Stop generating', 深度思考: 'Deep Thinking', 思考中: 'Thinking...',
  已思考完成: 'Thinking Completed', 思考失败: 'Thinking Failed',
  复制成功: 'Copy Success', 复制失败: 'Copy Failed',
  调用中: 'Calling...', 调用成功: 'Call Success', 调用失败: 'Call Failed',
  上传文件: 'Upload File', 更多: 'More',
};

const translate = (key: string) => simulateLang.value === 'en' ? enMap[key] : key;

// 实际 t() 的当前输出
const actualKeys = ['复制', '发送', '停止', '重新生成'] as const;
</script>

## 语言检测

语言在**页面加载时**读取 `blueking_language` Cookie 一次性确定，运行时切换需刷新页面：

```typescript
// src/common/lang.ts
import { getCookieByName } from '../utils';
export const isEn = getCookieByName('blueking_language') === 'en';

// src/lang/lang.ts
export const t = (key: keyof typeof lang) => {
  if (isEn) return lang[key]; // 英文环境返回英文
  return key; // 中文环境直接返回 key（key 本身即中文）
};
```

## 翻译函数 `t()`

`t()` 接受类型安全的中文 key，返回当前语言对应的文本：

```typescript
import { t } from '@blueking/chat-x';

t('复制'); // 中文: '复制'  | 英文: 'Copy'
t('发送'); // 中文: '发送'  | 英文: 'Send'
t('复制成功'); // 中文: '复制成功' | 英文: 'Copy Success'

// TypeScript 类型约束：只接受已定义的 key
t('未定义的文本'); // ✗ 编译报错
```

<div class="demo">
  <div style="padding: 16px;">
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
      <span style="font-size: 13px; color: #63656e;">模拟语言：</span>
      <label style="display: flex; align-items: center; gap: 4px; cursor: pointer;">
        <input type="radio" v-model="simulateLang" value="zh" /> 中文
      </label>
      <label style="display: flex; align-items: center; gap: 4px; cursor: pointer;">
        <input type="radio" v-model="simulateLang" value="en" /> English
      </label>
    </div>
    <div style="display: flex; flex-wrap: wrap; gap: 8px;">
      <span
        v-for="key in langKeys"
        :key="key"
        style="display: inline-flex; align-items: center; padding: 4px 12px; background: #f0f1f5; border-radius: 4px; font-size: 13px; color: #313238;"
      >
        <span style="color: #979ba5; margin-right: 4px;">{{ key }} →</span>
        {{ translate(key) }}
      </span>
    </div>
    <div style="margin-top: 12px; padding: 8px 12px; background: #fff8e6; border-radius: 4px; font-size: 12px; color: #fe9c00;">
      提示：实际 t() 的语言由页面加载时的 Cookie 决定，上方为模拟效果。
    </div>
  </div>
</div>

## 内置翻译表

共 {{ Object.keys(enMap).length }}+ 个翻译 key，覆盖组件库所有内部文本。

### 通用操作

| 中文 key   | 英文             |
| ---------- | ---------------- |
| `发送`     | Send             |
| `停止`     | Stop             |
| `停止生成` | Stop generating  |
| `复制`     | Copy             |
| `复制成功` | Copy Success     |
| `复制失败` | Copy Failed      |
| `删除`     | Delete           |
| `编辑`     | Edit             |
| `提交`     | Submit           |
| `取消`     | Cancel           |
| `引用`     | Quote            |
| `分享`     | Share            |
| `点赞`     | Like             |
| `不满意`   | Unsatisfied      |
| `重新生成` | Regenerate       |
| `返回底部` | Return to bottom |
| `返回内容` | Return Content   |
| `更多`     | More             |
| `暂无数据` | No Data          |

### 消息时间

| 中文 key | 英文      |
| -------- | --------- |
| `昨天`   | Yesterday |

> 仅「昨天」一档需要翻译，其余档位（`12:00` / `3-12 12:00` / `2025-3-12 12:00`）为纯数字格式，详见 [MessageTime](/components/feedback/message-time)。

### 对话 / 输入

| 中文 key               | 英文                         |
| ---------------------- | ---------------------------- |
| `问问小鲸`             | Ask AI                       |
| `说出您的想法`         | Tell us your thoughts        |
| `什么原因让你满意？`   | What makes you satisfied?    |
| `什么原因让你不满意？` | What makes you dissatisfied? |
| `上传文件`             | Upload File                  |
| `请求中...`            | Requesting...                |
| `深度思考`             | Deep Thinking                |

### AI 推理 / 思考

| 中文 key     | 英文               |
| ------------ | ------------------ |
| `思考中`     | Thinking...        |
| `已思考完成` | Thinking Completed |
| `思考失败`   | Thinking Failed    |
| `耗时`       | Duration           |

### Tool Call / MCP

| 中文 key     | 英文         |
| ------------ | ------------ |
| `调用工具：` | Call Tool:   |
| `调用 MCP：` | Call MCP:    |
| `调用中`     | Calling...   |
| `调用成功`   | Call Success |
| `调用失败`   | Call Failed  |
| `参数`       | Parameters   |
| `描述`       | Description  |

### 图片

| 中文 key        | 英文                 |
| --------------- | -------------------- |
| `图片加载中...` | Loading image...     |
| `图片加载失败`  | Failed to load image |

### 引用 / 检索

| 中文 key   | 英文             |
| ---------- | ---------------- |
| `预览内容` | Preview Content  |
| `跳转详情` | Jump to Detail   |
| `检索中`   | Searching        |
| `检索完成` | Search Completed |

### FlowAgent 流程节点

| 中文 key     | 英文              |
| ------------ | ----------------- |
| `执行情况`   | Execution Status  |
| `执行中`     | Running           |
| `成功`       | Success           |
| `失败`       | Failed            |
| `挂起`       | Pending           |
| `待执行`     | To Be Executed    |
| `详情`       | Details           |
| `有效证据`   | Valid Evidence    |
| `节点`       | Node              |
| `节点配置`   | Node Config       |
| `节点输出`   | Node Output       |
| `基础信息`   | Basic Info        |
| `流程模板`   | Flow Template     |
| `节点名称`   | Node Name         |
| `步骤名称`   | Step Name         |
| `执行方案`   | Execution Plan    |
| `是否可选`   | Optional          |
| `失败处理`   | Failure Handler   |
| `超时控制`   | Timeout Control   |
| `手动跳过`   | Manual Skip       |
| `是`         | Yes               |
| `否`         | No                |
| `输入参数`   | Input Params      |
| `输出参数`   | Output Params     |
| `结构化输出` | Structured Output |
| `参数名`     | Param Name        |
| `参数值`     | Param Value       |
| `名称`       | Name              |
| `变量说明`   | Description       |

## 切换语言

语言在模块导入时一次性读取 Cookie，**运行时修改 Cookie 不会生效**，需刷新页面：

<div class="demo">
  <div style="padding: 16px; display: flex; flex-direction: column; gap: 12px;">
    <div style="font-size: 13px; color: #63656e;">当前页面实际 t() 输出：</div>
    <div style="display: flex; flex-wrap: wrap; gap: 8px;">
      <span
        v-for="key in actualKeys"
        :key="key"
        style="padding: 4px 12px; background: #e1ecff; border-radius: 4px; font-size: 13px; color: #3a84ff;"
      >
        t('{{ key }}') = "{{ t(key) }}"
      </span>
    </div>
    <div style="padding: 12px; background: #f5f7fa; border-radius: 4px; font-size: 13px; color: #63656e; line-height: 1.8;">
      <div>切换为英文：</div>
      <code style="color: #313238;">document.cookie = 'blueking_language=en; path=/';</code>
      <div style="margin-top: 4px;">切换为中文：</div>
      <code style="color: #313238;">document.cookie = 'blueking_language=zh-cn; path=/';</code>
      <div style="margin-top: 8px; color: #fe9c00;">修改后需刷新页面生效。</div>
    </div>
  </div>
</div>

```typescript
// 切换为英文
document.cookie = 'blueking_language=en; path=/';

// 切换为中文
document.cookie = 'blueking_language=zh-cn; path=/';

// 刷新后生效
location.reload();
```

## 注意事项

1. **加载时确定**：`isEn` 是模块级常量，页面加载时读取 Cookie 一次，之后不再变化
2. **key 即中文**：中文环境下 `t()` 直接返回 key 本身，无需额外存储中文翻译
3. **类型安全**：`t()` 参数类型为 `keyof typeof lang`，传入未定义的 key 会产生 TypeScript 编译错误
4. **组件内部已处理**：所有组件库内部文本均已调用 `t()`，无需额外配置
5. **不支持扩展**：`lang` 对象使用 `as const` 约束，如需自定义翻译文本，需在业务层封装自己的翻译函数
