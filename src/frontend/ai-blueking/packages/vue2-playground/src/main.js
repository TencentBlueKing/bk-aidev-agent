import Vue from 'vue';

import '@blueking/ai-blueking/dist/vue2/style.css';
import 'bk-magic-vue/dist/bk-magic-vue.min.css';

import App from './App.vue';
import router from './router';

new Vue({
  router,
  render: h => h(App),
}).$mount('#app');
