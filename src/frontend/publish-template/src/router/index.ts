import {
  createRouter,
  createWebHistory,
} from 'vue-router';

const Entry = () => import(/* webpackChunkName: "Entry" */ '../views/index.vue');
const SideSliderDemo = () => import(/* webpackChunkName: "SideSliderDemo" */ '../views/side-slider-demo.vue');
const PageDemo = () => import(/* webpackChunkName: "PageDemo" */ '../views/page-demo.vue');

export default createRouter({
  history: createWebHistory(window.SITE_URL),
  routes: [
    {
      path: '/',
      component: Entry,
      redirect: '/page',
      children: [
        {
          path: 'side-slider',
          name: 'side-slider',
          component: SideSliderDemo,
        },
        {
          path: 'page',
          name: 'page',
          component: PageDemo,
        },
      ]
    }
  ],
});
