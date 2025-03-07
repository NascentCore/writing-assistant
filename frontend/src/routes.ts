export const routes = [
  {
    path: '/',
    redirect: '/PersonalKnowledge',
  },
  {
    name: '登录',
    path: '/Login',
    component: './Login',
    hideInMenu: true, // 隐藏菜单栏
    menuRender: false, //菜单栏存在，但是该路由不在菜单栏中显示
  },
  {
    name: '注册',
    path: '/Register',
    component: './Register',
    hideInMenu: true,
    menuRender: false,
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
  },
];
