import { createRouter, createWebHashHistory } from 'vue-router';

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      redirect: '/integrated',
    },
    {
      path: '/integrated',
      name: 'Integrated',
      component: () => import('./views/IntegratedView.vue'),
      meta: { title: '集成模式', group: 'demo' },
    },
    {
      path: '/standalone',
      name: 'Standalone',
      component: () => import('./views/StandaloneView.vue'),
      meta: { title: '独立模式', group: 'demo' },
    },
    {
      path: '/examples/basic',
      name: 'ExampleBasic',
      component: () => import('./views/ExampleBasicView.vue'),
      meta: { title: '基础用法', group: 'example' },
    },
    {
      path: '/examples/advanced',
      name: 'ExampleAdvanced',
      component: () => import('./views/ExampleAdvancedView.vue'),
      meta: { title: '高级用法', group: 'example' },
    },
    {
      path: '/examples/code-header-slot',
      name: 'CodeHeaderSlot',
      component: () => import('./views/CodeHeaderSlotView.vue'),
      meta: { title: 'codeHeader 插槽', group: 'example' },
    },
    {
      path: '/examples/url-switch',
      name: 'UrlSwitch',
      component: () => import('./views/UrlSwitchView.vue'),
      meta: { title: 'URL 动态切换', group: 'example' },
    },
    {
      path: '/examples/request-options',
      name: 'RequestOptions',
      component: () => import('./views/RequestOptionsView.vue'),
      meta: { title: 'requestOptions 响应式', group: 'example' },
    },
    {
      path: '/examples/header-left-slot',
      name: 'HeaderLeftSlot',
      component: () => import('./views/HeaderLeftSlotView.vue'),
      meta: { title: 'headerLeft 插槽', group: 'example' },
    },
    {
      path: '/examples/render-mode',
      name: 'RenderMode',
      component: () => import('./views/RenderModeView.vue'),
      meta: { title: 'RenderMode 渲染模式', group: 'example' },
    },
    {
      path: '/examples/error-handling',
      name: 'ErrorHandling',
      component: () => import('./views/ErrorHandlingView.vue'),
      meta: { title: '错误处理', group: 'example' },
    },
    {
      path: '/examples/custom-message-slot',
      name: 'CustomMessageSlot',
      component: () => import('./views/CustomMessageSlotView.vue'),
      meta: { title: '自定义消息渲染', group: 'example' },
    },
    {
      path: '/examples/side-render',
      name: 'SideRender',
      component: () => import('./views/SideRenderView.vue'),
      meta: { title: '侧栏渲染 side-render', group: 'example' },
    },
  ],
});

export default router;
