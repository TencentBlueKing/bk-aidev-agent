import { createRouter, createWebHistory } from "vue-router"

const Entry = () => import(/* webpackChunkName: "Entry" */ "../views/index.vue")
const SideSliderDemo = () => import(/* webpackChunkName: "SideSliderDemo" */ "../views/side-slider-demo.vue")
const PageDemo = () => import(/* webpackChunkName: "PageDemo" */ "../views/page-demo.vue")
const ChatWindow = () => import(/* webpackChunkName: "ChatWindow" */ "../views/ChatWindow.vue")
const Forbidden = () => import(/* webpackChunkName: "Forbidden" */ "../views/403.vue")
const Share = () => import(/* webpackChunkName: "Share" */ "../views/share.vue")

export default createRouter({
  history: createWebHistory(window.SITE_URL),
  routes: [
    {
      path: "/",
      component: Entry,
      redirect: "/side-slider",
      children: [
        {
          path: "side-slider",
          name: "side-slider",
          component: SideSliderDemo,
        },
        {
          path: "page",
          name: "page",
          component: ChatWindow,
        },
      ],
    },
    {
      path: "/share-page/:shareCode",
      name: "share-page",
      component: Share,
    },
    {
      path: "/403",
      name: "403",
      component: Forbidden,
    },
  ],
})
