
module.exports = {
  port: process.env.BK_APP_PORT,
  host: process.env.BK_APP_HOST,
  typescript: true,
  replaceStatic: true,
  parseNodeModules: false,
  server: 'http'
};
