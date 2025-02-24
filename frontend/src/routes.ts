export const routes = [
  {
    path: '/',
    redirect: '/EditorPage',
  },
  {
    name: '登录',
    path: '/Login',
    component: './Login',
    hideInMenu: true,
  },
  {
    name: '注册',
    path: '/Register',
    component: './Register',
    hideInMenu: true,
  },
  {
    name: '编辑器',
    path: '/EditorPage',
    component: './EditorPage',
    hideInMenu: true,
  },
  {
    name: '写作助手',
    path: '/WritingAssistant',
    component: './WritingAssistant',
  },
  {
    name: '个人知识库',
    path: '/PersonalKnowledge',
    component: './PersonalKnowledge',
  },
  {
    name: '系统知识库',
    path: '/SystemKnowledge',
    component: './SystemKnowledge',
  },

  {
    name: 'AI对话',
    path: '/AiChat',
    component: './AiChat',
  },
];
