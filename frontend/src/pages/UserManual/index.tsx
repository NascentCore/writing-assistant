import React from 'react';
import styles from './index.module.less';

// 用户手册页面，嵌入飞书文档
const UserManual: React.FC = () => {
  return (
    <div className={styles.container}>
      {/* 这里通过 iframe 嵌入飞书文档，后续如需替换链接可直接修改 src */}
      <iframe
        src="https://ycnlxgpsu8qv.feishu.cn/wiki/ByAQw0E9EiEbYckBvrccgZClnNg"
        title="用户手册"
        width="100%"
        height="100%"
        frameBorder="0"
        style={{ minHeight: '80vh', border: 'none' }}
        allowFullScreen
      />
    </div>
  );
};

export default UserManual;
