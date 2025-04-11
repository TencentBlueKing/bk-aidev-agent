/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

// 添加对?raw查询参数的支持
declare module '*.MD?raw' {
  const content: string
  export default content
}

// 添加小写的支持
declare module '*.md?raw' {
  const content: string
  export default content
} 