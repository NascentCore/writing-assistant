import Icon from '@/components/Icon';
import UserProfile from '@/layouts/components/UserProfile';
import { routes } from '@/routes';
import {
  EditOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UpOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { history, Outlet, useLocation } from '@umijs/max';
import { Avatar, Dropdown, MenuProps } from 'antd';
import React, { useEffect, useState } from 'react';
import styles from './index.less';

interface RouteItem {
  name?: string;
  path: string;
  component?: string;
  hideInMenu?: boolean;
  redirect?: string;
  icon?: React.ReactNode;
  menuRender?: boolean;
}

interface MenuItem {
  key: string;
  icon: React.ReactNode;
  title: string;
  path?: string;
  children?: { key: string; title: string }[];
}

// 图标映射
const iconMap: Record<string, React.ReactNode> = {
  '/PersonalKnowledge': <Icon type="PersonalKnowledge" />,
  '/SystemKnowledge': <Icon type="SystemKnowledge" />,
  '/WritingAssistant': <Icon type="WritingAssistant" />,
  '/RecentChat': <Icon type="RecentChat" />,
  '/AiChat': <Icon type="AIChat" />,
  '/DepartKnowledge': <Icon type="DepartKn" />,
  '/DepartManage': <Icon type="DepartMana" />,
  '/KnowledgeSearch': <Icon type="KnSearch" />,
  '/TemplateManage': <Icon type="TemplateManage" />,
  '/UserManual': <Icon type="UserManual" />,
  '/UserSessionList': <Icon type="UserSessionList" />,
};

// 将路由配置转换为菜单项
const convertRoutesToMenuItems = (routes: RouteItem[]): MenuItem[] => {
  const admin = localStorage.getItem('admin');

  const menuItems: MenuItem[] = routes
    .filter((route) => {
      // 如果不是管理员，过滤掉相关路由
      const adminOnlyRoutes = [
        '/SystemKnowledge',
        '/UserSessionList',
        '/TemplateManage',
      ];
      if (adminOnlyRoutes.includes(route.path) && admin !== '2') {
        return false;
      }

      // 如果是普通用户，过滤掉部门相关路由
      const departRoutes = ['/DepartKnowledge', '/DepartManage'];
      if (departRoutes.includes(route.path) && admin === '0') {
        return false;
      }

      return !route.hideInMenu && route.name && !route.redirect;
    })
    .map((route) => ({
      key: route.path,
      icon: iconMap[route.path] || <EditOutlined />,
      title: route.name || '',
      path: route.path,
    }));

  // 添加最近对话菜单项
  // menuItems.push({
  //   key: 'RecentChat',
  //   icon: <Icon type="RecentChat" />,
  //   title: '最近对话',
  //   children: Array.from({ length: 12 }, (_, i) => ({
  //     key: `chat-${String(i + 1).padStart(2, '0')}`,
  //     title: `最近对话${String(i + 1).padStart(2, '0')}`,
  //   })),
  // });
  // menuItems.push({
  //   key: 'EditorPage',
  //   icon: <Icon type="PersonalKnowledge" />,
  //   title: '编辑器',
  //   path: '/EditorPage',
  // });

  return menuItems;
};

const menuItems = convertRoutesToMenuItems(routes);

const Layout: React.FC = () => {
  const location = useLocation();
  const [selectedMenu, setSelectedMenu] = useState('writing-assistant');
  const [expandedMenu, setExpandedMenu] = useState<string[]>(['RecentChat']);
  const [collapsed, setCollapsed] = useState(false);
  const [username, setUsername] = useState('');
  const [showProfile, setShowProfile] = useState(false);

  useEffect(() => {
    const storedUsername = localStorage.getItem('username') || '';
    setUsername(storedUsername);
  }, []);

  // 退出登录处理函数
  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    // 退出登录后直接跳转到登录界面
    window.location.href = '/Login';
  };

  // 用户下拉菜单项
  const userMenuItems: MenuProps['items'] = [
    {
      key: 'profile',
      label: '个人信息',
      icon: <UserOutlined style={{ fontSize: 18 }} />,
      onClick: () => setShowProfile(true),
    },
    {
      key: 'logout',
      label: '退出登录',
      icon: <LogoutOutlined style={{ fontSize: 18 }} />,
      onClick: handleLogout,
    },
  ];

  // 根据当前路径设置选中的菜单
  useEffect(() => {
    // 如果路径中包含查询参数chatId，说明是从最近对话菜单点击进入的
    // 这种情况下不需要重新设置selectedMenu，保留子菜单的选中状态
    if (location.search.includes('chatId=')) {
      return;
    }

    const currentMenuItem = menuItems.find(
      (item) => item.path === location.pathname,
    );
    if (currentMenuItem) {
      setSelectedMenu(currentMenuItem.key);
    }
  }, [location.pathname, location.search]);

  // 检查当前路由是否需要隐藏菜单
  const currentRoute = routes.find(
    (route) =>
      route.path === '/*' ||
      route.path.toLowerCase() === location.pathname.toLowerCase(),
  );
  if (currentRoute?.menuRender === false) {
    return <Outlet />;
  }

  return (
    <div className={styles.layoutContainer}>
      {!(window as any).isIframe && (
        <div
          className={`${styles.sideMenu} ${collapsed ? styles.collapsed : ''}`}
        >
          <div className={styles.menuHeader}>
            <div className={styles.userAvatar}>
              <Dropdown
                menu={{ items: userMenuItems }}
                placement="bottomRight"
                trigger={['click']}
              >
                <div className={styles.avatarContainer}>
                  <Avatar icon={<UserOutlined />} size="large" />
                  <span className={styles.userName}>{username}</span>
                </div>
              </Dropdown>
            </div>
            <div
              className={styles.collapseButton}
              onClick={() => setCollapsed(!collapsed)}
            >
              {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            </div>
          </div>

          {menuItems.map((item) => (
            <div key={item.key} className={styles.menuItemContainer}>
              <div
                className={`${styles.menuItem} ${
                  selectedMenu === item.key && item.key !== 'RecentChat'
                    ? styles.selected
                    : ''
                }`}
                onClick={() => {
                  if (item.key !== 'RecentChat') {
                    setSelectedMenu(item.key);
                    if (item.path) {
                      history.push(item.path);
                    }
                  }
                  if (item.children) {
                    setExpandedMenu((prev) =>
                      prev.includes(item.key)
                        ? prev.filter((key) => key !== item.key)
                        : [...prev, item.key],
                    );
                  }
                }}
              >
                <div className={styles.menuItemContent}>
                  {item.icon}
                  {!collapsed && (
                    <span className={styles.menuItemTitle}>{item.title}</span>
                  )}
                </div>
                {item.children && !collapsed && (
                  <UpOutlined
                    className={`${styles.arrow} ${
                      expandedMenu.includes(item.key)
                        ? styles.expanded
                        : styles.unexpanded
                    }`}
                  />
                )}
              </div>
              {item.children && !collapsed && (
                <div
                  className={`${styles.subMenu} ${
                    expandedMenu.includes(item.key) ? 'expanded' : ''
                  }`}
                >
                  {item.children.map((child) => (
                    <div
                      key={child.key}
                      className={`${styles.subMenuItem} ${
                        selectedMenu === child.key ? styles.selected : ''
                      }`}
                      onClick={() => {
                        setSelectedMenu(child.key);
                        history.push(`/AiChat?chatId=${child.key}`);
                      }}
                    >
                      {child.title}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      <div
        className={styles.mainContent}
        style={{ marginLeft: !(window as any).isIframe ? '240px' : '0px' }}
      >
        <Outlet />
      </div>
      {showProfile && <UserProfile onClose={() => setShowProfile(false)} />}
    </div>
  );
};

export default Layout;
