import DefaultTheme from 'vitepress/theme'
import { defineAsyncComponent, h } from 'vue'

import './styles/vars.css'
import './styles/custom.css'
import './demo-kit/demo-kit.css'

import BackToAidev from './components/BackToAidev.vue'
import FeatureCard from './components/FeatureCard.vue'
import VersionBadge from './components/VersionBadge.vue'
import Changelog from './components/Changelog.vue'
import DemoGallery from './demo-kit/DemoGallery.vue'
import DemoRuntimeHost from './demo-kit/DemoRuntimeHost.vue'

/** 配方组件按需加载：只有用到的页面才会拉取组件库 */
const RECIPES = {
  DemoEnvBar: () => import('./demo-kit/DemoEnvBar.vue'),
  RecipeOpenAndReady: () => import('./recipes/programmatic-control/RecipeOpenAndReady.vue'),
  RecipeAlertDiagnosis: () => import('./recipes/programmatic-control/RecipeAlertDiagnosis.vue'),
  RecipeSqlShortcut: () => import('./recipes/programmatic-control/RecipeSqlShortcut.vue'),
  RecipeFloatingConsole: () => import('./recipes/floating/RecipeFloatingConsole.vue'),
  RecipePanelLayout: () => import('./recipes/floating/RecipePanelLayout.vue'),
  RecipeMinimalEmbed: () => import('./recipes/embedded/RecipeMinimalEmbed.vue'),
  RecipeEmbeddedWorkbench: () => import('./recipes/embedded/RecipeEmbeddedWorkbench.vue'),
  RecipeAtomicAssembly: () => import('./recipes/atomic/RecipeAtomicAssembly.vue'),
  RecipeTenantRequest: () => import('./recipes/business/RecipeTenantRequest.vue'),
  RecipePageContext: () => import('./recipes/business/RecipePageContext.vue'),
  RecipeAutoRename: () => import('./recipes/business/RecipeAutoRename.vue'),
  RecipeSessionControl: () => import('./recipes/business/RecipeSessionControl.vue'),
  RecipeFaultInjection: () => import('./recipes/business/RecipeFaultInjection.vue'),
  RecipeAgentSwitch: () => import('./recipes/business/RecipeAgentSwitch.vue'),
  RecipeHeaderSlots: () => import('./recipes/ui/RecipeHeaderSlots.vue'),
  RecipeRenderMode: () => import('./recipes/ui/RecipeRenderMode.vue'),
  RecipeCustomMessage: () => import('./recipes/messages/RecipeCustomMessage.vue'),
  RecipeCodeHeader: () => import('./recipes/messages/RecipeCodeHeader.vue'),
  RecipeFlowRun: () => import('./recipes/side-render/RecipeFlowRun.vue'),
  RecipeSideRenderCustom: () => import('./recipes/side-render/RecipeSideRenderCustom.vue'),
}

export default {
  extends: DefaultTheme,
  Layout: () =>
    h(DefaultTheme.Layout, null, {
      'nav-bar-content-after': () => h(BackToAidev, { variant: 'nav' }),
      'nav-screen-content-after': () => h(BackToAidev, { variant: 'screen' }),
      // 页面中有浮窗配方时才挂载唯一的 AIBlueking 实例
      'layout-bottom': () => h(DemoRuntimeHost),
    }),
  async enhanceApp({ app }) {
    app.component('FeatureCard', FeatureCard)
    app.component('VersionBadge', VersionBadge)
    app.component('Changelog', Changelog)
    app.component('DemoGallery', DemoGallery)

    // bkui-vue / chat-x 依赖浏览器环境，避免 SSR 构建访问 document
    if (import.meta.env.SSR) return

    const bkui = (await import('bkui-vue')).default
    await import('bkui-vue/dist/style.variable.css')
    await import('@blueking/chat-x/dist/index.css')
    app.use(bkui)

    for (const [name, loader] of Object.entries(RECIPES)) {
      app.component(name, defineAsyncComponent(loader))
    }
  },
}
