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
  enhanceApp({ app }) {
    app.component('DemoContainer', DemoContainer)
    app.component('FeatureCard', FeatureCard)
    app.component('VersionBadge', VersionBadge)
    app.component('Changelog', Changelog)
    app.component('Playground', Playground)
  }
} 