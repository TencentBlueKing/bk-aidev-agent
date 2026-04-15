/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

/**
 * vue-draggable-resizable 类型声明
 * 用于 TypeScript 支持
 */

declare module 'vue-draggable-resizable' {
  import type { DefineComponent } from 'vue';

  interface VueDraggableResizableProps {
    active?: boolean;
    axis?: 'both' | 'none' | 'x' | 'y';
    className?: string;
    classNameActive?: string;
    classNameDraggable?: string;
    classNameDragging?: string;
    classNameHandle?: string;
    classNameResizable?: string;
    classNameResizing?: string;
    disableUserSelect?: boolean;
    dragCancel?: string;
    draggable?: boolean;
    dragHandle?: string;
    enableNativeDrag?: boolean;
    grid?: number[];
    h?: number | string;
    handles?: string[];
    lockAspectRatio?: boolean;
    maxHeight?: number;
    maxWidth?: number;
    minHeight?: number;
    minWidth?: number;
    parent?: boolean | string;
    preventDeactivation?: boolean;
    resizable?: boolean;
    scale?: number;
    w?: number | string;
    x?: number;
    y?: number;
    z?: number | string;
    onDrag?: (x: number, y: number) => void;
    onDragStart?: (x: number, y: number) => void;
    onDragStop?: (x: number, y: number) => void;
    onResize?: (x: number, y: number, w: number, h: number) => void;
    onResizeStart?: (x: number, y: number, w: number, h: number) => void;
    onResizeStop?: (x: number, y: number, w: number, h: number) => void;
  }

  const VueDraggableResizable: DefineComponent<VueDraggableResizableProps>;
  export default VueDraggableResizable;
}

// 样式声明
declare module 'vue-draggable-resizable/style.css' {
  const content: string;
  export default content;
}
