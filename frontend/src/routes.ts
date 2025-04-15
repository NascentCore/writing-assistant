export const routes = [
  {
    path: '/',
    redirect: '/WritingAssistant',
  },
  {
    name: '登录',
    path: '/Login',
    component: './Login',
    hideInMenu: true, // 菜单栏存在，但是该路由不在菜单栏中显示
    menuRender: false, //隐藏菜单栏
  },
  {
    name: '树形',
    path: '/Products',
    component: './Products',
    hideInMenu: true,
  },
  {
    name: '注册',
    path: '/Register',
    component: './Register',
    hideInMenu: true,
    menuRender: false,
  },
  {
    name: 'AI对话',
    path: '/AiChat',
    component: './AiChat',
  },
  {
    name: '写作助手',
    path: '/WritingAssistant',
    component: './WritingAssistant',
  },
  {
    name: '系统知识库',
    path: '/SystemKnowledge',
    component: './SystemKnowledge',
  },
  {
    name: '部门知识库',
    path: '/DepartKnowledge',
    component: './DepartKnowledge',
  },
  {
    name: '个人知识库',
    path: '/PersonalKnowledge',
    component: './PersonalKnowledge',
  },
  {
    name: '部门管理',
    path: '/DepartManage',
    component: './DepartManage',
  },
  {
    name: '知识库检索',
    path: '/KnowledgeSearch',
    component: './KnowledgeSearch',
  },
  {
    name: '历史记录',
    path: '/WritingHistory',
    component: './WritingHistory',
    hideInMenu: true,
  },
  {
    name: '编辑器',
    path: '/EditorPage',
    component: './EditorPage',
    menuRender: false,
    hideInMenu: true,
  },
  {
    name: '模板管理',
    path: '/TemplateManage',
    component: './TemplateManage',
  },
  {
    name: '用户手册',
    path: '/UserManual',
    component: './UserManual',
  },
  {
    path: '/*',
    component: '@/pages/404',
    name: '404',
    hideInMenu: true,
    menuRender: false,
  },
];
