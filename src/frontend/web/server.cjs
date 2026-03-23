/**
 * 文档站生产/预览用静态服务 + Mock（/mock-agui/api）。
 * VitePress 自带的 `vitepress preview` 不会加载 Vite dev 中间件，原子组装演示会 404；请用 `pnpm preview` 或本脚本。
 */
const express = require('express');
const path = require('path');
const RateLimit = require('express-rate-limit');

const { createMockAguiRouter } = require('./docs/.vitepress/mock-agui-routes.cjs');

const app = express();
const PORT = process.env.PORT || 5000;
const distDir = path.resolve(__dirname, './dist');

app.use(express.json());

// 原子组装文档演示：Mock AG-UI + REST（与 VitePress dev 中 middleware 行为一致）
const mockAgui = express.Router();
mockAgui.use(createMockAguiRouter());
app.use('/mock-agui/api', mockAgui);

// 全局变量中间件（如果需要）
app.use((req, res, next) => {
  const scriptName = (req.headers['x-script-name'] || '').replace(/\//g, '');
  req.GLOBAL_VAR = {
    BK_STATIC_URL: scriptName ? `/${scriptName}` : '',
    SITE_URL: scriptName ? `/${scriptName}` : ''
  };
  next();
});

// 静态文件服务
app.use(express.static(distDir, {
  index: false, // 禁用默认的index.html自动响应
  maxAge: '1h'  // 静态资源缓存1小时
}));

// 处理所有路由，确保SPA正常工作
const spaRateLimiter = RateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // max 100 requests per windowMs
});

app.use(spaRateLimiter, (req, res, next) => {
  // 排除静态资源请求
  if (req.path.startsWith('/assets/')) {
    return next();
  }
  // 排除favicon等特殊文件
  if (req.path.match(/\.[a-z0-9]+$/i)) {
    return next();
  }
  // 返回index.html，并设置不缓存
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
  res.setHeader('Pragma', 'no-cache');
  res.setHeader('Expires', '0');
  res.sendFile(path.join(distDir, 'index.html'));
});

// 错误处理
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).send('Something went wrong!');
});

app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});