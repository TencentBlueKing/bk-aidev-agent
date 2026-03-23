import DefaultTheme from 'vitepress/theme'

import './styles/vars.css'
import './styles/custom.css'

import DemoContainer from './components/DemoContainer.vue'
import FeatureCard from './components/FeatureCard.vue'
import VersionBadge from './components/VersionBadge.vue'
import Changelog from './components/Changelog.vue'
import Playground from './components/Playground.vue'

export default {
  extends: DefaultTheme,
  async enhanceApp({ app }) {
    app.component('DemoContainer', DemoContainer)
    app.component('FeatureCard', FeatureCard)
    app.component('VersionBadge', VersionBadge)
    app.component('Changelog', Changelog)
    app.component('Playground', Playground)

    // bkui-vue / chat-x 依赖浏览器环境，避免 SSR 构建访问 document
    if (import.meta.env.SSR) return

    const bkui = (await import('bkui-vue')).default
    await import('bkui-vue/dist/style.variable.css')
    await import('@blueking/chat-x/dist/index.css')
    app.use(bkui)

    const { default: DemoCodeGroup } = await import('./components/DemoCodeGroup.vue')
    app.component('DemoCodeGroup', DemoCodeGroup)

    const { default: AtomicAssemblyDemoPanel } = await import('./components/AtomicAssemblyDemoPanel.vue')
    app.component('AtomicAssemblyDemo', AtomicAssemblyDemoPanel)
  },
} 