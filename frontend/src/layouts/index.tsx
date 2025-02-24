import Icon from '@/components/Icon';
import { routes } from '@/routes';
import { EditOutlined, UpOutlined } from '@ant-design/icons';
import { history, Outlet, useLocation } from '@umijs/max';
import React, { useEffect, useState } from 'react';
import styles from './index.less';

interface RouteItem {
  name?: string;
  path: string;
  component?: string;
  hideInMenu?: boolean;
  redirect?: string;
  icon?: React.ReactNode;
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
};

// 将路由配置转换为菜单项
const convertRoutesToMenuItems = (routes: RouteItem[]): MenuItem[] => {
  const menuItems: MenuItem[] = routes
    .filter((route) => !route.hideInMenu && route.name && !route.redirect)
    .map((route) => ({
      key: route.path,
      icon: iconMap[route.path] || <EditOutlined />,
      title: route.name || '',
      path: route.path,
    }));

  // 添加最近对话菜单项
  menuItems.push({
    key: 'RecentChat',
    icon: <Icon type="RecentChat" />,
    title: '最近对话',
    children: Array.from({ length: 12 }, (_, i) => ({
      key: `chat-${String(i + 1).padStart(2, '0')}`,
      title: `最近对话${String(i + 1).padStart(2, '0')}`,
    })),
  });

  return menuItems;
};

const menuItems = convertRoutesToMenuItems(routes);

const Layout: React.FC = () => {
  const location = useLocation();
  const [selectedMenu, setSelectedMenu] = useState('writing-assistant');
  const [expandedMenu, setExpandedMenu] = useState<string[]>(['RecentChat']);

  // 根据当前路径设置选中的菜单
  useEffect(() => {
    const currentMenuItem = menuItems.find(
      (item) => item.path === location.pathname,
    );
    if (currentMenuItem) {
      setSelectedMenu(currentMenuItem.key);
    }
  }, [location.pathname]);

  // 检查当前路由是否需要隐藏菜单
  const currentRoute = routes.find((route) => route.path === location.pathname);
  if (currentRoute?.hideInMenu) {
    return <Outlet />;
  }

  return (
    <div className={styles.layoutContainer}>
      <div className={styles.sideMenu}>
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
                <span>{item.title}</span>
              </div>
              {item.children && (
                <UpOutlined
                  className={`${styles.arrow} ${
                    expandedMenu.includes(item.key)
                      ? styles.expanded
                      : styles.unexpanded
                  }`}
                />
              )}
            </div>
            {item.children && (
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
                      // 从 chat-01 这样的格式中提取出数字部分作为 chatId
                      const chatId = child.key.split('-')[1];
                      history.push(`/AiChat?chatId=${chatId}`);
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
      <div className={styles.mainContent}>
        <Outlet />
      </div>
    </div>
  );
};

export default Layout;
