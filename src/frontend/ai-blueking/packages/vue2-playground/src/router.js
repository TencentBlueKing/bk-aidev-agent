import Vue from 'vue';
import VueRouter from 'vue-router';

Vue.use(VueRouter);

const router = new VueRouter({
  mode: 'hash',
  routes: [
    {
      path: '/',
      redirect: '/full',
    },
    {
      path: '/full',
      name: 'Full',
      component: () => import('./views/FullView.vue'),
      meta: { title: 'AIBlueking 完整模式', group: 'demo' },
    },
    {
      path: '/nimbus-hook',
      name: 'NimbusHook',
      component: () => import('./views/NimbusHookView.vue'),
      meta: { title: 'Nimbus 点击自定义', group: 'demo' },
    },
    {
      path: '/embedded',
      name: 'Embedded',
      component: () => import('./views/EmbeddedView.vue'),
      meta: { title: 'ChatBot 嵌入模式', group: 'demo' },
    },
  ],
});

export default router;
