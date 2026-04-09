import { createApp } from 'vue';

import '@blueking/ai-blueking/dist/vue3/style.css';
import App from './App.vue';
import router from './router';

const app = createApp(App);
app.use(router);
app.mount('#app');
