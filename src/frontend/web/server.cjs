const express = require('express');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 5000;
const distDir = path.resolve(__dirname, './dist');

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
// 对于带有内容哈希的静态资源，maxAge: '1h' 是合适的，
// 因为 VitePress 在文件内容变化时会更改文件名，
// 这样浏览器会请求新的文件。
app.use(express.static(distDir, {
  index: false, // 禁用默认的index.html自动响应
  maxAge: '1h'  // 静态资源缓存1小时 (用到 /assets/ 目录下的文件)
}));

// 处理所有路由，确保SPA正常工作
app.use((req, res, next) => {
  // 排除静态资源请求，让 express.static 处理它们
  if (req.path.startsWith('/assets/') || req.path.match(/\.[a-z0-9]+$/i)) {
    return next();
  }

  // 返回index.html
  // 这是关键一步：设置 Cache-Control 头，确保 index.html 不被浏览器缓存
  res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate'); // HTTP 1.1
  res.setHeader('Pragma', 'no-cache');     // HTTP 1.0 (兼容旧浏览器)
  res.setHeader('Expires', '0');           // Proxies (明确告诉代理不要缓存)

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
