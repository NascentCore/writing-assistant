import { Card } from 'antd';
import React from 'react';
import InteractiveTree from './components/InteractiveTree';
import styles from './index.module.less';

const Products: React.FC = () => {
  const handleNodeUpdate = (node: any) => {
    console.log('节点更新:', node);
  };

  const handleNodeDelete = (key: React.Key) => {
    console.log('节点删除:', key);
  };

  const handleNodeAdd = (parentKey: React.Key | null, node: any) => {
    console.log('节点添加:', parentKey, node);
  };

  const handleAddMaterial = (nodeKey: React.Key) => {
    console.log('添加资料:', nodeKey);
  };

  return (
    <div className={styles.container}>
      <Card title="文档大纲" bordered={false}>
        <InteractiveTree
          onNodeUpdate={handleNodeUpdate}
          onNodeDelete={handleNodeDelete}
          onNodeAdd={handleNodeAdd}
          onAddMaterial={handleAddMaterial}
        />
      </Card>
    </div>
  );
};

export default Products;
