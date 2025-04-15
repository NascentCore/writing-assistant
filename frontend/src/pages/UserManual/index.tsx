import React, { useEffect } from 'react';
import styles from './index.module.less';

// 用户手册页面，嵌入飞书文档
const UserManual: React.FC = () => {
  useEffect(() => {
    // 进入页面时设置 body 样式
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    // 页面卸载时恢复 body 样式
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, []);

  return (
    <div className={styles.container}>
      {/* 这里通过 iframe 嵌入飞书文档，后续如需替换链接可直接修改 src */}
      <iframe
        src="https://www.yuque.com/xuanxuan-r7m8s/ag1pfw/sh6u6amunezlwy8u?singleDoc#%20%E3%80%8A%E4%BD%BF%E7%94%A8%E6%89%8B%E5%86%8C%E3%80%8B"
        title="用户手册"
        width="100%"
        height="100%"
        style={{ minHeight: '80vh', border: 'none' }}
        allowFullScreen
      />
    </div>
  );
};

export default UserManual;
