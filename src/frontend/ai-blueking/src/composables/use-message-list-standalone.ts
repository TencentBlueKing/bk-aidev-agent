import { useStyle, useClickProxy } from '@blueking/ai-ui-sdk/hooks';

/**
 * MessageList 组件独立使用的组合式函数
 * 自动处理样式初始化和点击代理，简化单独使用 MessageList 的流程
 */
export function useMessageListStandalone(
  options: {
    /** 是否自动初始化样式 */
    autoInitStyle?: boolean;
    /** 是否自动初始化点击代理 */
    autoInitClickProxy?: boolean;
    /** 点击代理的禁用类名 */
    disabledClassName?: string;
  } = {}
) {
  const { autoInitStyle = true, autoInitClickProxy = true, disabledClassName = '' } = options;

  const init = () => {
    console.log('autoInitStyle', autoInitStyle);
    // 初始化样式
    if (autoInitStyle) {
      useStyle();
    }

    // 初始化点击代理
    if (autoInitClickProxy) {
      useClickProxy(disabledClassName);
    }
  };

  // 立即执行，而不是等到 onMounted
  init();

  return {
    init,
    reinitialize: () => {
      init();
    },
  };
}
