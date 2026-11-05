/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { type ComputedRef, type MaybeRefOrGetter, computed, onScopeDispose, shallowRef, toValue, watch } from 'vue';

/** 主聊天区最小宽度，与浮窗收起时的默认 minWidth 对齐 */
export const MAIN_CHAT_MIN_WIDTH = 400;
/** 侧栏最小宽度 */
export const ASIDE_MIN_WIDTH = 400;

export interface ChatContainerResizeProps {
  disabled?: boolean;
  initialDivide?: number | string;
  /** 侧栏最大宽度 */
  max?: number;
  /** 主聊天区最小宽度，默认 400。侧栏拖拽不会把主栏挤到这个值以下 */
  mainMin?: number;
  /** 侧栏最小宽度 */
  min?: number;
}

export interface AsideMaxWidthOptions {
  /** ResizeLayout 侧栏最小值 */
  asideMin: number;
  /** 聊天容器当前宽度；未知时为 0 */
  containerWidth: number;
  /** 主聊天区需要保留的宽度 */
  mainMin: number;
  /** 调用方传入的侧栏最大宽度 */
  userMax?: number;
}

/** 绑定到 bkui ResizeLayout 的属性，不含 mainMin */
export type AsideLayoutProps = Omit<ChatContainerResizeProps, 'mainMin'> & {
  collapsible: boolean;
  immediate: boolean;
  min: number;
  placement: 'right';
};

/**
 * 侧栏最大宽度。容器宽度已知时，给主聊天区留出 mainMin。
 * 容器放不下「侧栏最小值 + 主栏最小值」时，不再把 max 压到侧栏 min 以下。
 * 容器宽度未知时只尊重调用方传入的 max。
 */
export function resolveAsideMaxWidth(options: AsideMaxWidthOptions): number | undefined {
  const { asideMin, containerWidth, mainMin, userMax } = options;
  if (containerWidth <= 0) {
    return userMax;
  }
  const fitMain = Math.max(containerWidth - mainMin, asideMin);
  if (userMax === undefined) {
    return fitMain;
  }
  return Math.min(userMax, fitMain);
}

/**
 * 监听聊天容器宽度，产出 ResizeLayout 属性：侧栏 max 会给主聊天区留出 mainMin。
 */
export function useAsideResizeProps(
  containerRef: MaybeRefOrGetter<HTMLElement | null | undefined>,
  resizeProps: MaybeRefOrGetter<ChatContainerResizeProps | undefined>,
): ComputedRef<AsideLayoutProps> {
  const containerWidth = shallowRef(0);

  let observer: null | ResizeObserver = null;
  const disconnect = () => {
    observer?.disconnect();
    observer = null;
  };
  watch(
    () => toValue(containerRef),
    element => {
      disconnect();
      if (!element || typeof ResizeObserver === 'undefined') {
        return;
      }
      observer = new ResizeObserver(([entry]) => {
        containerWidth.value = entry?.contentRect.width ?? 0;
      });
      observer.observe(element);
    },
    // 模板 ref 在渲染后才赋值，pre flush 会错过首次挂载
    { flush: 'post', immediate: true },
  );
  onScopeDispose(disconnect);

  return computed(() => {
    const { mainMin = MAIN_CHAT_MIN_WIDTH, ...layoutProps } = toValue(resizeProps) ?? {};
    const min = layoutProps.min ?? ASIDE_MIN_WIDTH;
    const max = resolveAsideMaxWidth({
      asideMin: min,
      containerWidth: containerWidth.value,
      mainMin,
      userMax: layoutProps.max,
    });
    return {
      collapsible: false,
      immediate: true,
      ...layoutProps,
      min,
      ...(max === undefined ? {} : { max }),
      // 侧栏固定从右侧展开，不再支持左侧
      placement: 'right',
    };
  });
}
