import { defineConfig } from '@umijs/max';

export default defineConfig({
  antd: {},
  access: {},
  model: {},
  initialState: {},
  request: {},
  routes: [
    { path: '/', component: '@/pages/EditorPage/index' },
    { path: '/login', component: '@/pages/Login/index' },
    { path: '/register', component: '@/pages/Register/index' },
  ],
  mako: {},
  npmClient: 'pnpm',
});
