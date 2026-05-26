import vue from 'eslint-plugin-vue'
import vueTsConfig from '@vue/eslint-config-typescript'
import prettierSkip from '@vue/eslint-config-prettier/skip-formatting'

export default [
  {
    ignores: ['dist/**', 'node_modules/**', 'public/lsf/**', 'coverage/**', 'playwright-report/**', 'test-results/**'],
  },
  ...vue.configs['flat/recommended'],
  ...vueTsConfig(),
  prettierSkip,
  {
    rules: {
      'vue/multi-word-component-names': 'off',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },
]
