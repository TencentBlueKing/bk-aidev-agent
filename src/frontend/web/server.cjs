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
app.use(express.static(distDir, {
  index: false, // 禁用默认的index.html自动响应
  maxAge: '1h'  // 静态资源缓存1小时
}));

// 处理所有路由，确保SPA正常工作
app.use((req, res, next) => {
  // 排除静态资源请求
  if (req.path.startsWith('/assets/')) {
    return next();
  }
  // 排除favicon等特殊文件
  if (req.path.match(/\.[a-z0-9]+$/i)) {
    return next();
  }
  // 返回index.html
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