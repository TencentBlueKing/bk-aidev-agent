/**
 * 示例页目录：/demos/ 侧边栏与总览页共同的数据来源。
 * 新增示例页时只改这里；status 为 planned 的条目不会出现在侧栏与总览。
 */

export type DemoMode = '浮窗' | '嵌入' | '原子';
export type DemoGroupId = 'start' | 'integration' | 'business' | 'ui';

export interface DemoGroup {
  id: DemoGroupId;
  /** 侧栏分组标题 */
  title: string;
  /** 总览页分组副标题 */
  subtitle?: string;
}

export interface DemoEntry {
  id: string;
  title: string;
  link: string;
  group: DemoGroupId;
  summary: string;
  modes: DemoMode[];
  recipes: number;
  /** Mock 下可完整体验 */
  mockReady: boolean;
  status: 'available' | 'planned';
  /** 集成形态大卡片 */
  pick?: { when: string; illustration: 'floating' | 'embedded' | 'atomic' };
}

export interface SidebarGroup {
  text: string;
  items: { text: string; link: string }[];
}

export const OVERVIEW_LINK = '/demos/';

export const DEMO_GROUPS: DemoGroup[] = [
  { id: 'start', title: '示例' },
  { id: 'integration', title: '集成形态', subtitle: '先按产品形态选一种集成方式' },
  { id: 'business', title: '业务联动', subtitle: '让业务页面主动驱动小鲸' },
  { id: 'ui', title: '界面与渲染', subtitle: '定制头部、消息与侧栏' },
];

export const DEMO_ENTRIES: DemoEntry[] = [
  {
    id: 'overview',
    title: '总览',
    link: OVERVIEW_LINK,
    group: 'start',
    summary: '按场景找示例',
    modes: [],
    recipes: 0,
    mockReady: true,
    status: 'available',
  },
  {
    id: 'floating',
    title: 'AIBlueking 浮窗',
    link: '/demos/full-panel',
    group: 'integration',
    summary: '悬浮球 + 可拖拽面板，开箱即带会话管理与划词。',
    modes: ['浮窗'],
    recipes: 2,
    mockReady: true,
    status: 'available',
    pick: { when: '适合：给整个 SaaS 加一个全局 AI 助手', illustration: 'floating' },
  },
  {
    id: 'embedded',
    title: 'ChatBot 页面嵌入',
    link: '/demos/basic-usage',
    group: 'integration',
    summary: '把聊天区嵌进业务页面，Header 与会话列表由业务自建。',
    modes: ['嵌入'],
    recipes: 2,
    mockReady: true,
    status: 'available',
    pick: { when: '适合：独立的 AI 工作台 / 详情页内的助手区', illustration: 'embedded' },
  },
  {
    id: 'atomic',
    title: '原子组件组装',
    link: '/demos/atomic-assembly',
    group: 'integration',
    summary: '用 chat-x + chat-helper 自行拼装，对接任意 AG-UI 网关。',
    modes: ['原子'],
    recipes: 1,
    mockReady: true,
    status: 'available',
    pick: { when: '适合：产品形态与小鲸差异很大，需要深度定制', illustration: 'atomic' },
  },
  {
    id: 'programmatic-control',
    title: '编程式控制',
    link: '/demos/programmatic-control',
    group: 'business',
    summary: '从业务页打开小鲸、带上下文提问、用快捷指令诊断报错。',
    modes: ['浮窗'],
    recipes: 3,
    mockReady: true,
    status: 'available',
  },
  {
    id: 'request-options',
    title: '请求参数与上下文',
    link: '/demos/request-options',
    group: 'business',
    summary: '动态 Header、GET / POST 参数与消息 context 的注入时机。',
    modes: ['浮窗', '嵌入'],
    recipes: 2,
    mockReady: true,
    status: 'available',
  },
  {
    id: 'session-events',
    title: '会话与事件',
    link: '/demos/session-events',
    group: 'business',
    summary: '首条消息后的自动命名、手动重命名与会话切换事件。',
    modes: ['浮窗', '嵌入'],
    recipes: 2,
    mockReady: true,
    status: 'available',
  },
  {
    id: 'error-handling',
    title: '错误处理与环境切换',
    link: '/demos/error-handling',
    group: 'business',
    summary: '注入接口故障观察 sdk-error；切换 url 后实例重建。',
    modes: ['浮窗', '嵌入'],
    recipes: 2,
    mockReady: true,
    status: 'available',
  },
  {
    id: 'header-slots',
    title: 'Header 与插槽',
    link: '/demos/header-slots',
    group: 'ui',
    summary: 'headerLeft / headerActions 的位置差异、渲染模式对入口的影响。',
    modes: ['浮窗'],
    recipes: 2,
    mockReady: true,
    status: 'available',
  },
  {
    id: 'custom-message',
    title: '消息自定义渲染',
    link: '/demos/custom-message',
    group: 'ui',
    summary: '把模型输出渲染成图表、表单、iframe；代码块头部加「插入」按钮。',
    modes: ['嵌入'],
    recipes: 2,
    mockReady: true,
    status: 'available',
  },
  {
    id: 'side-render',
    title: '侧栏 Tab 自定义',
    link: '/demos/side-render',
    group: 'ui',
    summary: '流程智能体节点详情：内置拉取与自定义拉取两种接法。',
    modes: ['嵌入'],
    recipes: 2,
    mockReady: true,
    status: 'available',
  },
];

const isAvailable = (entry: DemoEntry) => entry.status === 'available';

/** /demos/ 侧边栏：只含已上线页面，空分组省略，顺序与目录一致 */
export function buildDemosSidebar(entries: DemoEntry[] = DEMO_ENTRIES, groups: DemoGroup[] = DEMO_GROUPS): SidebarGroup[] {
  return groups
    .map(group => ({
      text: group.title,
      items: entries.filter(e => e.group === group.id && isAvailable(e)).map(e => ({ text: e.title, link: e.link })),
    }))
    .filter(group => group.items.length > 0);
}

/** 总览页卡片：已上线且不含总览自身 */
export function listGalleryEntries(entries: DemoEntry[] = DEMO_ENTRIES): DemoEntry[] {
  return entries.filter(e => isAvailable(e) && e.link !== OVERVIEW_LINK);
}
