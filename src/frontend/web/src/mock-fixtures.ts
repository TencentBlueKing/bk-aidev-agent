/**
 * 文档站 Mock 的固定数据：智能体信息、模型、预置会话与回复文案。
 * 字段遵循 AIDev 后端（snake_case），由 chat-helper 的 transform 转为前端结构。
 */

export interface MockSessionRecord {
  session_code: string;
  session_name: string;
  is_temporary: boolean;
  created_at: string;
  updated_at: string;
  model?: string;
  session_content_count?: number;
  [key: string]: unknown;
}

export interface MockMessageRecord {
  id: string;
  message_id: string;
  session_code: string;
  role: string;
  content: unknown;
  status: string;
  created_at: string;
  property?: unknown;
  [key: string]: unknown;
}

export const SQL_COMMAND_ID = 'sql_diagnosis';

export const MOCK_AGENT_INFO = {
  agent_name: '小鲸 Demo 助手',
  agent_type: 'single',
  conversation_settings: {
    opening_remark: '你好，我是文档站的 Mock 助手。回复为固定演示文案，切换到「真实智能体」可体验真实回答。',
    predefined_questions: ['怎样从业务页面打开小鲸？', '快捷指令有哪几种触发方式？'],
    enable_chat_session: true,
    enable_word_selection_popup: true,
    commands: [
      {
        id: SQL_COMMAND_ID,
        agent_id: 1,
        name: 'SQL 报错诊断',
        alias: 'SQL 报错诊断',
        icon: '',
        status: 'enabled',
        content: null,
        components: [
          {
            type: 'textarea',
            key: 'sql',
            name: 'SQL 语句',
            placeholder: '粘贴执行失败的 SQL',
            default: null,
            required: true,
            fill_back: false,
            fill_regx: null,
            rows: 4,
            min: null,
            max: null,
            options: null,
          },
          {
            type: 'textarea',
            key: 'error',
            name: '报错信息',
            placeholder: '粘贴数据库返回的报错',
            default: null,
            required: true,
            fill_back: false,
            fill_regx: null,
            rows: 2,
            min: null,
            max: null,
            options: null,
          },
        ],
      },
    ],
  },
};

import { MOCK_FLOW_AGENT_INFO } from './mock-flow';

/** 第二套智能体（路径前缀 ~data/），用于演示切换 url 后实例重建 */
export const MOCK_DATA_AGENT_INFO = {
  agent_name: '数据助手 Demo',
  agent_type: 'single',
  conversation_settings: {
    opening_remark: '你好，我是数据助手（Mock）。可以帮你解释 SQL、排查查询报错。',
    predefined_questions: ['这条 SQL 为什么慢？'],
    enable_chat_session: true,
    enable_word_selection_popup: false,
    commands: [],
  },
};

export const MOCK_AGENT_PROFILES: Record<string, typeof MOCK_AGENT_INFO | typeof MOCK_DATA_AGENT_INFO | typeof MOCK_FLOW_AGENT_INFO> = {
  default: MOCK_AGENT_INFO,
  data: MOCK_DATA_AGENT_INFO,
  flow: MOCK_FLOW_AGENT_INFO,
};

export const MOCK_LLMS = [
  {
    id: 1,
    llm_code: 'mock-model',
    llm_name: 'Mock 模型',
    llm_type: 'chat.completion',
    description: '文档站 Mock 模型，回复为固定演示文案',
    property: {},
  },
];

export const SEED_SESSION_CODE = 'demo_capacity_review';

export function createSeedSessions(now: () => string): { session: MockSessionRecord; messages: MockMessageRecord[] }[] {
  const time = new Date(Date.parse(now()) - 7 * 24 * 3600 * 1000).toISOString();
  return [
    {
      session: {
        session_code: SEED_SESSION_CODE,
        session_name: '上周容量评估',
        is_temporary: false,
        created_at: time,
        updated_at: time,
      },
      messages: [
        {
          id: 'seed-1',
          message_id: 'seed-1',
          session_code: SEED_SESSION_CODE,
          role: 'user',
          content: '下季度 alarm-dispatcher 需要扩容多少实例？',
          status: 'complete',
          created_at: time,
        },
        {
          id: 'seed-2',
          message_id: 'seed-2',
          session_code: SEED_SESSION_CODE,
          role: 'assistant',
          content:
            '按近 30 天峰值 QPS 增长 18% 估算，建议从 6 个实例扩到 8 个，并把单实例堆内存从 4G 调到 6G。\n\n（这是 Mock 预置的历史会话，用于演示 `show(sessionCode)`。）',
          status: 'complete',
          created_at: time,
        },
      ],
    },
  ];
}

const REPLY_ALERT = `根据告警信息初步判断：

1. 10.0.0.12 的 CPU 在 15 分钟内持续高于 95%，同时 G1 Old 区 GC 停顿从 1.8s 增长到 2.6s，疑似内存不足导致频繁 Full GC，CPU 被 GC 线程占满。
2. \`alarm-dispatcher\` 线程池队列已满，说明处理能力下降后告警开始积压，属于连带现象。

**建议排查步骤**

- 执行 \`jstat -gcutil <pid> 1000\`，观察 Old 区使用率是否持续接近 100%；
- 导出 heap dump，确认是否有缓存或大对象未释放；
- 扩容或重启前，先在蓝鲸监控里设置 30 分钟告警屏蔽，避免重复通知。

> Mock 回复：较长的流式输出，方便演示「停止生成」。`;

const fence = (json: unknown) => '```custom-component\n' + JSON.stringify(json) + '\n```';

/** 关键词 → 固定回复：用于演示自定义消息渲染与代码块头部插槽 */
export const KEYWORD_REPLIES: { match: RegExp; reply: string }[] = [
  {
    match: /混合/,
    reply: [
      '以下是本周发布的分析报告：',
      '',
      '## 发布失败率',
      fence({ type: 'chart', chartType: 'bar', title: '近 5 天发布失败次数', data: { labels: ['周一', '周二', '周三', '周四', '周五'], values: [3, 1, 4, 2, 0] } }),
      '',
      '## 需要你确认',
      fence({ type: 'form', title: '是否回滚周三的发布？', fields: [{ label: '回滚范围', type: 'select', options: ['仅失败实例', '全部实例'] }], actions: ['确认回滚', '暂不处理'] }),
      '',
      '> Mock 回复：文本、图表、表单混排',
    ].join('\n'),
  },
  {
    match: /图表/,
    reply: [
      '近 7 天告警量如下，周三出现明显峰值：',
      '',
      fence({ type: 'chart', chartType: 'bar', title: '近 7 天告警量', data: { labels: ['一', '二', '三', '四', '五', '六', '日'], values: [42, 38, 96, 51, 47, 20, 18] } }),
      '',
      '建议优先排查周三 14:00 前后的变更记录。',
    ].join('\n'),
  },
  {
    match: /表单/,
    reply: [
      '执行扩容前请确认以下参数：',
      '',
      fence({
        type: 'form',
        title: '扩容确认',
        fields: [
          { label: '目标环境', type: 'select', options: ['测试环境', '生产环境'] },
          { label: '扩容实例数', type: 'text', placeholder: '2' },
        ],
        actions: ['确认扩容', '取消'],
      }),
    ].join('\n'),
  },
  {
    match: /面板|iframe/,
    reply: [
      '已为你嵌入实时监控面板：',
      '',
      fence({ type: 'iframe', title: '主机实时监控', src: '/demo-assets/mini-dashboard.html', height: 220 }),
      '',
      '面板为站内静态页面，真实场景中替换为业务的仪表盘地址即可。',
    ].join('\n'),
  },
  {
    match: /代码/,
    reply: [
      '下面是一个带超时的请求封装，可以直接插入编辑器：',
      '',
      '```ts',
      'export async function fetchWithTimeout(url: string, ms = 5000): Promise<Response> {',
      '  const controller = new AbortController();',
      '  const timer = setTimeout(() => controller.abort(), ms);',
      '  try {',
      '    return await fetch(url, { signal: controller.signal });',
      '  } finally {',
      '    clearTimeout(timer);',
      '  }',
      '}',
      '```',
    ].join('\n'),
  },
];

const REPLY_DEFAULT = `这是文档站 Mock 的固定回复。

切换到页面顶部「演示环境」中的 **真实智能体**（站点配置了 \`BK_AIDEV_API_URL\` 时可用），即可获得真实回答。`;

interface StructuredCite {
  type?: string;
  title?: string;
  data?: { key: string; value: string }[];
}

interface MessageExtra {
  cite?: string | StructuredCite;
  command?: string;
  context?: Record<string, unknown>[] | Record<string, unknown>;
}

function readExtra(property: unknown): MessageExtra {
  if (!property || typeof property !== 'object') return {};
  const extra = (property as { extra?: unknown }).extra;
  return extra && typeof extra === 'object' ? (extra as MessageExtra) : {};
}

const contextItems = (extra: MessageExtra): Record<string, unknown>[] => (Array.isArray(extra.context) ? extra.context : []);

function contextValue(extra: MessageExtra, key: string): string {
  const item = contextItems(extra).find(c => c && typeof c === 'object' && (c as { __key?: unknown }).__key === key);
  const value = item ? (item as { __value?: unknown }).__value : undefined;
  return typeof value === 'string' ? value : '';
}

function textOf(content: unknown): string {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content
      .map(part => (part && typeof part === 'object' && typeof (part as { text?: unknown }).text === 'string' ? (part as { text: string }).text : ''))
      .join('');
  }
  return '';
}

/** 把 property.extra.context 压成「k=v，k=v」，兼容结构化条目（__key / __value）与普通键值 */
export function describeContext(context: unknown): string {
  const pairs: string[] = [];
  const push = (key: unknown, value: unknown) => {
    if (typeof key === 'string' && key && !key.startsWith('__') && key !== 'context_type') pairs.push(`${key}=${String(value)}`);
  };
  const items = Array.isArray(context) ? context : context && typeof context === 'object' ? [context] : [];
  for (const item of items) {
    if (!item || typeof item !== 'object') continue;
    const record = item as Record<string, unknown>;
    if (typeof record.__key === 'string') push(record.__key, record.__value);
    else Object.entries(record).forEach(([k, v]) => push(k, v));
  }
  return pairs.join('，');
}

/**
 * 根据最后一条用户消息挑选 Mock 回复，让读者能确认上下文确实传到了后端。
 */
export function pickMockReply(message: Pick<MockMessageRecord, 'content' | 'property'> | undefined): string {
  if (!message) return REPLY_DEFAULT;
  const extra = readExtra(message.property);
  const text = textOf(message.content);

  if (extra.command === SQL_COMMAND_ID) {
    const sql = contextValue(extra, 'sql');
    const error = contextValue(extra, 'error');
    if (!sql && !error) {
      return '收到快捷指令「SQL 报错诊断」，但 SQL 与报错都为空。请在表单中填写后再发送。\n\n> Mock 回复';
    }
    return `收到快捷指令「SQL 报错诊断」（SQL ${sql.length} 字，报错 ${error.length} 字）。

报错 \`1054 Unknown column 'create_time'\` 表示 \`alarm_event\` 表中不存在该字段，常见原因：

1. 字段实际名为 \`created_at\`；
2. 新增字段的数据库迁移没有在当前环境执行。

建议先执行 \`SHOW COLUMNS FROM alarm_event;\` 确认字段名，再修正 SELECT 与 ORDER BY 两处。

> Mock 回复`;
  }

  const contextText = describeContext(extra.context);
  const withContext = (reply: string) => (contextText ? `收到上下文：${contextText}。\n\n${reply}` : reply);

  if (text.includes('诊断告警')) return withContext(REPLY_ALERT);

  const keyword = KEYWORD_REPLIES.find(k => k.match.test(text));
  if (keyword) return withContext(keyword.reply);

  if (extra.cite) {
    const citeText = typeof extra.cite === 'string' ? extra.cite : (extra.cite.data ?? []).map(d => d.value).join('\n');
    return `收到引用内容（${citeText.length} 字）和你的问题：「${text.slice(0, 40)}」。

这几行日志里 GC 停顿在持续变长，并且线程池队列已满，优先检查堆内存是否不足。

> Mock 回复`;
  }

  return withContext(text ? `你说：「${text.slice(0, 60)}」\n\n${REPLY_DEFAULT}` : REPLY_DEFAULT);
}
