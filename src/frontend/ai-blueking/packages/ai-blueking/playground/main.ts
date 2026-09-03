import { createApp } from 'vue';

// JS 已 alias 到源码 vue3.ts：SFC 样式 + chat-x/dist/index.css 会随组件注入。
// 不要再引 dist/vue3/style.css，否则会套用上次 build 的旧规则（例如已删除的 .toolcall-header-title）。
import App from './App.vue';
import router from './router';

const app = createApp(App);
app.use(router);
app.mount('#app');
