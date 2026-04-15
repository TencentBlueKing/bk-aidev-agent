const {
  defineConfig,
} = require('@blueking/cli-service');

module.exports = defineConfig({
  host: process.env.BK_APP_HOST,
  port: process.env.BK_APP_PORT,
  publicPath: '/',
  cache: false,
  open: false,
  outputPreserveModuleDir: 'dist',
  replaceStatic: false,
  target: 'lib',
  libraryTarget: 'module',
  libraryName: undefined,
  preserveModules: true,
  preserveModulesOnly: true,
  splitChunk: false,
  splitCss: false,
  typescript: true,
  resource: {
    index: {
      entry: './src/index.ts',
    },
  },
  configureWebpack: {
    // optimization: {
    //   // 不压缩
    //   minimize: false,
    // },
    module: {
      parser: {
        javascript: {
          url: 'relative',
        },
      },
    },
    externals: {
      vue: 'vue',
      'bkui-vue': 'bkui-vue',
    },
  },
});
