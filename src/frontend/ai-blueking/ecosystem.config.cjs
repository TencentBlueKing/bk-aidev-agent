module.exports = {
  apps: [
    {
      name: 'ai-blueking-dev',
      script: 'pnpm',
      args: 'dev:ai',
      cwd: __dirname,
      interpreter: 'none',
      watch: false,
      max_memory_restart: '2G',
      env: {
        NODE_ENV: 'development',
      },
    },
  ],
};
