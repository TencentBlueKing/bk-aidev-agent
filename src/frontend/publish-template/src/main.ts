import {
  createApp,
} from 'vue'

import './css/index.css';

import bkui from 'bkui-vue';
// 全量引入 bkui-vue 样式
import 'bkui-vue/dist/style.css';

import router from './router';

import App from './app.vue';

createApp(App)
  .use(bkui)
  .use(router)
  .mount('.app');
