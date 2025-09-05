module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
    node: true,
  },
  globals: {
    // Vue 3 <script setup> 编译时宏
    defineProps: 'readonly',
    defineEmits: 'readonly',
    defineExpose: 'readonly',
    withDefaults: 'readonly',
    defineOptions: 'readonly',
    defineSlots: 'readonly',
    defineModel: 'readonly',
  },
  extends: [
    // 基础规则
    'eslint:recommended',
    // TypeScript规则
    'plugin:@typescript-eslint/recommended',
    // Vue3规则（包含script-setup-uses-vars）
    'plugin:vue/vue3-recommended',
    // Prettier（必须放在最后，覆盖前面所有格式化规则）
    'prettier',
  ],
  parser: 'vue-eslint-parser',
  parserOptions: {
    ecmaVersion: 'latest',
    parser: '@typescript-eslint/parser',
    sourceType: 'module',
    project: './src/frontend/ai-blueking/tsconfig.json',
    extraFileExtensions: ['.vue'],
  },
  plugins: ['vue', '@typescript-eslint', 'import', 'unused-imports', 'prettier'],
  settings: {
    'import/resolver': {
      typescript: {
        alwaysTryTypes: true,
        project: './src/frontend/ai-blueking/tsconfig.json',
      },
      node: {
        extensions: ['.js', '.jsx', '.ts', '.tsx', '.vue'],
      },
    },
    'import/extensions': ['.js', '.jsx', '.ts', '.tsx', '.vue'],
  },
  rules: {
    // === 基础规则 ===
    'no-console': process.env.NODE_ENV === 'production' ? 'warn' : 'off',
    'no-debugger': process.env.NODE_ENV === 'production' ? 'warn' : 'off',
    'prefer-rest-params': 'warn',

    // === TypeScript规则 ===
    '@typescript-eslint/no-unused-vars': [
      'warn',
      {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        caughtErrorsIgnorePattern: '^_',
      },
    ],
    '@typescript-eslint/no-explicit-any': 'warn',
    '@typescript-eslint/no-empty-function': 'warn',
    '@typescript-eslint/no-unsafe-function-type': 'warn',

    // === Vue规则 ===
    'vue/component-name-in-template-casing': ['error', 'kebab-case'],
    'vue/component-definition-name-casing': ['error', 'PascalCase'],
    'vue/prop-name-casing': ['error', 'camelCase'],
    'vue/attribute-hyphenation': ['error', 'always'],
    'vue/v-on-event-hyphenation': ['error', 'always'],
    'vue/custom-event-name-casing': ['error', 'kebab-case'],
    'vue/require-explicit-emits': 'error',
    'vue/no-unused-refs': 'error',
    'vue/no-unused-components': 'error',
    'vue/no-unused-vars': 'error',
    'vue/script-setup-uses-vars': 'error',
    'vue/multi-word-component-names': 'off',

    // === 关闭所有与Prettier冲突的格式化规则 ===
    'vue/html-indent': 'off',
    'vue/script-indent': 'off',
    'vue/html-self-closing': 'off',
    'vue/max-attributes-per-line': 'off',
    'vue/first-attribute-linebreak': 'off',
    'vue/html-closing-bracket-newline': 'off',
    'vue/singleline-html-element-content-newline': 'off',
    'vue/multiline-html-element-content-newline': 'off',
    'vue/max-len': 'off',
    'vue/html-closing-bracket-spacing': 'off',
    'vue/comma-dangle': 'off',
    'vue/quote-props': 'off',
    'vue/space-infix-ops': 'off',
    'vue/space-unary-ops': 'off',
    'vue/object-curly-spacing': 'off',
    'vue/array-bracket-spacing': 'off',
    'vue/arrow-spacing': 'off',
    'vue/block-spacing': 'off',
    'vue/brace-style': 'off',
    'vue/comma-spacing': 'off',
    'vue/dot-notation': 'off',
    'vue/func-call-spacing': 'off',
    'vue/key-spacing': 'off',
    'vue/keyword-spacing': 'off',
    'vue/no-extra-parens': 'off',
    'vue/no-multi-spaces': 'off',
    'vue/no-sparse-arrays': 'off',
    'vue/object-curly-newline': 'off',
    'vue/object-property-newline': 'off',
    'vue/operator-linebreak': 'off',
    'vue/rest-spread-spacing': 'off',
    'vue/semi': 'off',
    'vue/semi-spacing': 'off',
    'vue/space-before-blocks': 'off',
    'vue/space-before-function-paren': 'off',
    'vue/space-in-parens': 'off',
    'vue/template-curly-spacing': 'off',

    // === Import排序规则（简化版）===
    'import/order': [
      'error',
      {
        groups: ['builtin', 'external', 'internal', 'parent', 'sibling', 'index'],
        pathGroups: [
          {
            pattern: 'vue',
            group: 'external',
            position: 'before',
          },
          {
            pattern: '@/**',
            group: 'internal',
            position: 'after',
          },
        ],
        'newlines-between': 'always',
        alphabetize: {
          order: 'asc',
          caseInsensitive: true,
        },
      },
    ],

    // === Vue组件顺序（简化版）===
    'vue/order-in-components': [
      'error',
      {
        order: [
          'name',
          'components',
          'props',
          'emits',
          'setup',
          'data',
          'computed',
          'watch',
          'methods',
        ],
      },
    ],
    'vue/attributes-order': [
      'error',
      {
        order: [
          'DEFINITION',
          'LIST_RENDERING',
          'CONDITIONALS',
          'RENDER_MODIFIERS',
          'GLOBAL',
          'UNIQUE',
          'SLOT',
          'TWO_WAY_BINDING',
          'OTHER_DIRECTIVES',
          'OTHER_ATTR',
          'EVENTS',
          'CONTENT',
        ],
        alphabetical: false,
      },
    ],
    'vue/component-tags-order': [
      'error',
      {
        order: ['template', 'script', 'style'],
      },
    ],
    'vue/block-order': [
      'error',
      {
        order: ['template', 'script[setup]', 'style[scoped]'],
      },
    ],

    // 清理未使用的导入
    'unused-imports/no-unused-imports': 'warn',
    'unused-imports/no-unused-vars': [
      'warn',
      {
        vars: 'all',
        varsIgnorePattern: '^_',
        args: 'after-used',
        argsIgnorePattern: '^_',
      },
    ],
  },
  overrides: [
    // Vue文件特殊处理
    {
      files: ['*.vue'],
      rules: {
        // 所有格式化相关规则交给Prettier
        indent: 'off',
        '@typescript-eslint/indent': 'off',
        'vue/html-indent': 'off',
        'vue/script-indent': 'off',
        'vue/max-attributes-per-line': 'off',
        'vue/first-attribute-linebreak': 'off',
        'vue/html-closing-bracket-newline': 'off',
        'vue/html-self-closing': 'off',
      },
    },
    // JS文件特殊处理
    {
      files: ['*.js'],
      rules: {
        '@typescript-eslint/no-var-requires': 'off',
      },
    },
  ],
};
