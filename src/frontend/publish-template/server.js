const Express = require('express');
const path = require('path');
const artTemplate = require('express-art-template');

const app = new Express();

const PORT = process.env.PORT || 5000;

const distDir = path.resolve(__dirname, './dist');

// 首页
app.get('/', (req, res) => {
  const GLOBAL_VAR = {};
  const scriptName = (req.headers['x-script-name'] || '').replace(/\//g, '');
  // 使用子路径
  if (scriptName) {
    GLOBAL_VAR.BK_STATIC_URL = `/${scriptName}`;
    GLOBAL_VAR.SITE_URL = `/${scriptName}`;
  } else {
    // 使用系统分配域名
    GLOBAL_VAR.BK_STATIC_URL = '';
    GLOBAL_VAR.SITE_URL = '';
  }
  // 注入全局变量
  res.render(path.join(distDir, 'index.html'), GLOBAL_VAR);
});
// static
app.use('/static', Express.static(path.join(distDir, '../dist/static')));
// 配置视图
app.set('views', path.join(__dirname, '../dist'));

app.engine('html', artTemplate);
app.set('view engine', 'html');

// 配置端口
app.listen(PORT, () => {
  console.log(`App is running in port ${PORT}`);
});
