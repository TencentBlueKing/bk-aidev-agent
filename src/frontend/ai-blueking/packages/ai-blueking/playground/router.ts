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
      path: '/examples/header-left-slot',
      name: 'HeaderLeftSlot',
      component: () => import('./views/HeaderLeftSlotView.vue'),
      meta: { title: 'headerLeft 插槽', group: 'example' },
    },
  ],
});

export default router;
