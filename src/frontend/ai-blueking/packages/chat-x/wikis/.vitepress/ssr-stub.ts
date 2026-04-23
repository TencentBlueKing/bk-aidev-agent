/*
 * SSR 阶段的占位模块。
 *
 * bkui-vue（如 directives/index.js 顶层 `document.addEventListener`、
 * config-provider 同步访问 `document.documentElement`）
 * 与 mermaid（d3-selection 直接 select(document)）
 * 在模块顶层就会访问 document/window，Node 环境下会立即抛 ReferenceError，
 * 阻塞 vitepress build。
 *
 * 这里把 SSR 模式下的 import 重定向到本文件，所有真实第三方实现都被替换为 noop，
 * 配合 vitepress markdown 输出整体 <ClientOnly> 包裹，
 * 真正的渲染会在浏览器水合阶段加载真实模块进行，所以最终用户看到的页面与功能不受影响。
 */
import { defineComponent } from 'vue';

const NoopComponent = defineComponent({
  name: 'SsrNoopComponent',
  render: () => null,
});

const noop = () => undefined;

const proxyHandler: ProxyHandler<Record<PropertyKey, unknown>> = {
  get(_target, prop) {
    if (prop === '__esModule') return true;
    if (prop === Symbol.toPrimitive) return () => '';
    if (prop === 'default') return NoopComponent;
    if (typeof prop === 'string' && /^[A-Z]/.test(prop)) {
      return NoopComponent;
    }
    return noop;
  },
};

const stub = new Proxy({}, proxyHandler);

export default stub;

// chat-x 用到的 bkui-vue 具名导出
export const Button = NoopComponent;
export const Checkbox = NoopComponent;
export const Form = NoopComponent;
export const Input = NoopComponent;
export const Radio = NoopComponent;
export const Select = NoopComponent;
export const Switcher = NoopComponent;
export const Exception = NoopComponent;
export const ResizeLayout = NoopComponent;
export const Tab = NoopComponent;
export const Loading = NoopComponent;
export const Message = NoopComponent;

// bkui-vue config-provider / shared 常用 API
export const setPrefixVariable = noop;
export const provideGlobalConfig = noop;
export const useGlobalConfig = () => ({});
export const useLocale = () => ({ t: (s: string) => s });
export const usePrefix = () => ({ resolveClassName: (s: string) => s });
export const rootProviderKey = Symbol('ssr-root-provider-key');
export const defaultRootConfig = {};
export const withInstall = <T>(comp: T) => comp;
export const version = '0.0.0-ssr';

// mermaid 默认导出/具名导出占位
export const initialize = noop;
export const init = noop;
export const render = async () => ({ svg: '' });
export const parse = noop;
export const run = noop;
export const registerLayoutLoaders = noop;
export const registerIconPacks = noop;

// vue-tippy / tippy.js 占位
export const Tippy = NoopComponent;
export const useTippy = () => ({
  tippy: { value: undefined },
  refresh: noop,
  refreshContent: noop,
  setContent: noop,
  setProps: noop,
  destroy: noop,
  hide: noop,
  show: noop,
  disable: noop,
  enable: noop,
  unmount: noop,
  mount: noop,
  state: { value: {} },
});
export const directive = {
  mounted: noop,
  updated: noop,
  unmounted: noop,
};
export const tippy = noop;
