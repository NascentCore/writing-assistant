import { defineConfig } from '@umijs/max';
import { routes } from './src/routes';

export default defineConfig({
  antd: {},
  access: {},
  model: {},
  initialState: {},
  request: {},
  layout: false,
  // layout: {
  //   title: '@umijs/max',
  // },
  // mako: {},
  mfsu: {},
  hash: true,
  locale: {
    default: 'zh-CN', // 默认语言
    antd: true, // 启用 antd 国际化
    baseNavigator: true, // 开启浏览器语言检测
  },
  favicons: ['/logo.png'],

  routes,
  npmClient: 'pnpm',
  esbuildMinifyIIFE: true,
});
