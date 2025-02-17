import {
  DeleteOutlined,
  FileAddOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { Button, Input, Tree, TreeProps } from 'antd';
import type { DataNode } from 'antd/es/tree';
import React, { useCallback, useEffect, useState } from 'react';
import styles from './index.module.less';

interface TreeNode extends Omit<DataNode, 'title'> {
  title: string;
  description?: string;
  children?: TreeNode[];
  level: number;
}

interface InteractiveTreeProps {
  onNodeUpdate?: (node: TreeNode) => void;
  onNodeDelete?: (key: React.Key) => void;
  onNodeAdd?: (parentKey: React.Key | null, node: TreeNode) => void;
  onAddMaterial?: (nodeKey: React.Key) => void;
}

// 抽离节点编辑组件以优化性能
const NodeTitle: React.FC<{
  node: TreeNode;
  editingNode: { title: string; description: string };
  onTitleChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onTitleBlur: () => void;
  onDescriptionBlur: () => void;
  onAddMaterial?: () => void;
  onAddChild?: () => void;
  onDelete?: () => void;
}> = React.memo(
  ({
    node,
    editingNode,
    onTitleChange,
    onDescriptionChange,
    onTitleBlur,
    onDescriptionBlur,
    onAddMaterial,
    onAddChild,
    onDelete,
  }) => {
    const level = node.level;

    const handleInputMouseEnter = (e: React.MouseEvent) => {
      e.stopPropagation();
      // 找到最近的树节点元素并添加不可拖拽类
      const treeNode = (e.target as HTMLElement).closest('.ant-tree-treenode');
      if (treeNode) {
        treeNode.setAttribute('draggable', 'false');
      }
    };

    const handleInputMouseLeave = (e: React.MouseEvent) => {
      e.stopPropagation();
      // 找到最近的树节点元素并恢复可拖拽
      const treeNode = (e.target as HTMLElement).closest('.ant-tree-treenode');
      if (treeNode) {
        treeNode.setAttribute('draggable', 'true');
      }
    };

    return (
      <div className={styles.nodeContent}>
        <div
          className={styles.inputWrapper}
          onMouseEnter={handleInputMouseEnter}
          onMouseLeave={handleInputMouseLeave}
        >
          <Input.TextArea
            autoSize={{ minRows: 1, maxRows: 6 }}
            value={editingNode.title}
            onChange={(e) => onTitleChange(e.target.value)}
            onBlur={onTitleBlur}
            placeholder="请输入标题"
          />
          <Input.TextArea
            autoSize={{ minRows: 1, maxRows: 6 }}
            style={{ fontSize: 12 }}
            value={editingNode.description}
            onChange={(e) => onDescriptionChange(e.target.value)}
            onBlur={onDescriptionBlur}
            placeholder="请输入描述"
          />
        </div>
        <div className={styles.nodeActions}>
          {level < 3 && (
            <FileAddOutlined
              className={styles.actionIcon}
              onClick={(e) => {
                e.stopPropagation();
                onAddMaterial?.();
              }}
            />
          )}
          {level < 3 && (
            <PlusOutlined
              className={styles.actionIcon}
              onClick={(e) => {
                e.stopPropagation();
                onAddChild?.();
              }}
            />
          )}
          <DeleteOutlined
            className={styles.actionIcon}
            onClick={(e) => {
              e.stopPropagation();
              onDelete?.();
            }}
          />
        </div>
      </div>
    );
  },
);

const InteractiveTree: React.FC<InteractiveTreeProps> = ({
  onNodeDelete,
  onNodeAdd,
  onAddMaterial,
}) => {
  const [treeData, setTreeData] = useState<TreeNode[]>([
    {
      key: '1',
      title: '第一章',
      description: '章节描述',
      level: 1,
      children: [
        {
          key: '1-1',
          title: '1.1 节',
          description: '小节描述',
          level: 2,
          children: [
            {
              key: 'node-3',
              title: '新建节点 1',
              description: '',
              level: 3,
            },
            {
              key: 'node-2',
              title: '新建节点2',
              description: '',
              level: 3,
            },
            {
              key: 'node-4',
              title: '新建节点 3',
              description: '',
              level: 3,
            },
          ],
        },
      ],
    },
  ]);

  // 获取所有第一级和第二级节点的 key
  const getDefaultExpandedKeys = useCallback((nodes: TreeNode[]): string[] => {
    let keys: string[] = [];
    nodes.forEach((node) => {
      if (node.level <= 2) {
        keys.push(node.key as string);
        if (node.children) {
          keys = keys.concat(getDefaultExpandedKeys(node.children));
        }
      }
    });
    return keys;
  }, []);

  // 获取当前树中最大的数字 key
  const getMaxNodeNumber = useCallback((nodes: TreeNode[]): number => {
    let maxNum = 0;
    const extractNumber = (key: React.Key) => {
      const match = String(key).match(/\d+$/);
      return match ? parseInt(match[0], 10) : 0;
    };

    const traverse = (node: TreeNode) => {
      const num = extractNumber(node.key);
      maxNum = Math.max(maxNum, num);
      if (node.children) {
        node.children.forEach(traverse);
      }
    };

    nodes.forEach(traverse);
    return maxNum;
  }, []);

  const [nodeCounter, setNodeCounter] = useState(
    () => getMaxNodeNumber(treeData) + 1,
  );
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>(() =>
    getDefaultExpandedKeys(treeData),
  );
  const [editingNodes, setEditingNodes] = useState<
    Record<string, { title: string; description: string }>
  >({});

  useEffect(() => {
    const initialEditingNodes: Record<
      string,
      { title: string; description: string }
    > = {};
    const initNodes = (nodes: TreeNode[]) => {
      nodes.forEach((node) => {
        initialEditingNodes[node.key as string] = {
          title: node.title,
          description: node.description || '',
        };
        if (node.children) {
          initNodes(node.children);
        }
      });
    };
    initNodes(treeData);
    setEditingNodes(initialEditingNodes);
  }, [treeData]);

  // 使用 useCallback 优化函数
  const updateTreeData = useCallback((newData: TreeNode[]) => {
    console.log('树形数据更新:', JSON.stringify(newData, null, 2));
    setTreeData(newData);
  }, []);

  const deleteNode = useCallback(
    (list: TreeNode[], key: React.Key): TreeNode[] => {
      return list.filter((node) => {
        if (node.key === key) {
          return false;
        }
        if (node.children) {
          node.children = deleteNode(node.children, key);
        }
        return true;
      });
    },
    [],
  );

  const getNodeLevel = useCallback(
    (list: TreeNode[], key: React.Key): number => {
      for (const node of list) {
        if (node.key === key) {
          return node.level;
        }
        if (node.children) {
          const level = getNodeLevel(node.children, key);
          if (level > 0) {
            return level;
          }
        }
      }
      return 1;
    },
    [],
  );

  const addNode = useCallback(
    (list: TreeNode[], parentKey: React.Key, newNode: TreeNode): TreeNode[] => {
      return list.map((node) => {
        if (node.key === parentKey) {
          // 确保新节点的层级是父节点的层级 + 1
          const updatedNewNode = {
            ...newNode,
            level: node.level + 1,
          };
          return {
            ...node,
            children: [...(node.children || []), updatedNewNode],
          };
        }
        if (node.children) {
          const updatedChildren = addNode(node.children, parentKey, newNode);
          // 如果子节点数组发生变化，说明在子节点中找到了目标父节点
          if (updatedChildren !== node.children) {
            return {
              ...node,
              children: updatedChildren,
            };
          }
        }
        return node;
      });
    },
    [],
  );

  const addChildNode = useCallback(
    (parentKey: React.Key | null) => {
      const newKey = `node-${nodeCounter}`;
      setNodeCounter((prev) => prev + 1);

      const parentLevel = parentKey ? getNodeLevel(treeData, parentKey) : 0;
      const newNode: TreeNode = {
        key: newKey,
        title: '新建节点',
        description: '',
        level: parentKey ? parentLevel + 1 : 1,
      };

      let newData: TreeNode[];
      if (!parentKey) {
        newData = [...treeData, newNode];
      } else {
        newData = addNode(treeData, parentKey, newNode);
      }

      // 先更新树数据
      updateTreeData(newData);

      // 更新展开的节点
      setExpandedKeys((keys) =>
        Array.from(new Set([...keys, parentKey || newKey])),
      );

      onNodeAdd?.(parentKey, newNode);
    },
    [nodeCounter, treeData, onNodeAdd, addNode, getNodeLevel, updateTreeData],
  );

  const onDrop: TreeProps['onDrop'] = (info) => {
    const dropKey = info.node.key;
    const dragKey = info.dragNode.key;
    const dropPos = info.node.pos.split('-');
    const dropPosition =
      info.dropPosition - Number(dropPos[dropPos.length - 1]);

    const dragLevel = getNodeLevel(treeData, dragKey);
    const dropLevel = getNodeLevel(treeData, dropKey);

    // 如果是放到节点上，需要检查目标节点的层级
    if (dropPosition === 0) {
      const targetLevel = dropLevel + 1;
      if (dragLevel !== targetLevel) {
        return;
      }
    } else {
      // 如果是放到节点前后，需要检查是否同级
      if (dragLevel !== dropLevel) {
        return;
      }
    }

    const data = [...treeData];

    // Find dragObject
    let dragObj: TreeNode | undefined;
    const loop = (
      data: TreeNode[],
      key: React.Key,
      callback: (item: TreeNode, index: number, arr: TreeNode[]) => void,
    ) => {
      data.forEach((item, index, arr) => {
        if (item.key === key) {
          callback(item, index, arr);
          return;
        }
        if (item.children) {
          loop(item.children, key, callback);
        }
      });
    };

    // Find dragObject and delete it
    loop(data, dragKey, (item, index, arr) => {
      dragObj = item;
      arr.splice(index, 1);
    });

    if (!dragObj) return;

    if (dropPosition === 0) {
      // Drop on the node
      loop(data, dropKey, (item) => {
        item.children = item.children || [];
        item.children.unshift(dragObj!);
      });
    } else {
      let ar: TreeNode[] = data;
      let i: number;
      loop(data, dropKey, (_item, index, arr) => {
        ar = arr;
        i = index;
      });
      if (dropPosition === -1) {
        // Drop on the top
        ar.splice(i!, 0, dragObj!);
      } else {
        // Drop on the bottom
        ar.splice(i! + 1, 0, dragObj!);
      }
    }

    updateTreeData(data);
  };

  const updateNodeInTree = useCallback(
    (
      nodes: TreeNode[],
      key: React.Key,
      updater: (node: TreeNode) => TreeNode,
    ): TreeNode[] => {
      return nodes.map((node) => {
        if (node.key === key) {
          return updater(node);
        }
        if (node.children) {
          return {
            ...node,
            children: updateNodeInTree(node.children, key, updater),
          };
        }
        return node;
      });
    },
    [],
  );

  const titleRender = useCallback(
    (node: TreeNode) => {
      const editingNode = editingNodes[node.key as string] || {
        title: node.title,
        description: node.description || '',
      };

      const handleTitleChange = (value: string) => {
        setEditingNodes((prev) => ({
          ...prev,
          [node.key as string]: {
            ...prev[node.key as string],
            title: value,
          },
        }));
      };

      const handleDescriptionChange = (value: string) => {
        setEditingNodes((prev) => ({
          ...prev,
          [node.key as string]: {
            ...prev[node.key as string],
            description: value,
          },
        }));
      };

      const handleTitleBlur = () => {
        const currentNode = editingNodes[node.key as string];
        if (currentNode && currentNode.title !== node.title) {
          const newTreeData = updateNodeInTree(treeData, node.key, (n) => ({
            ...n,
            title: currentNode.title,
          }));
          updateTreeData(newTreeData);
        }
      };

      const handleDescriptionBlur = () => {
        const currentNode = editingNodes[node.key as string];
        if (currentNode && currentNode.description !== node.description) {
          const newTreeData = updateNodeInTree(treeData, node.key, (n) => ({
            ...n,
            description: currentNode.description,
          }));
          updateTreeData(newTreeData);
        }
      };

      return (
        <NodeTitle
          node={node}
          editingNode={editingNode}
          onTitleChange={handleTitleChange}
          onDescriptionChange={handleDescriptionChange}
          onTitleBlur={handleTitleBlur}
          onDescriptionBlur={handleDescriptionBlur}
          onAddMaterial={() => onAddMaterial?.(node.key)}
          onAddChild={() => addChildNode(node.key)}
          onDelete={() => {
            const newData = deleteNode(treeData, node.key);
            updateTreeData(newData);
            onNodeDelete?.(node.key);
          }}
        />
      );
    },
    [
      editingNodes,
      treeData,
      updateNodeInTree,
      updateTreeData,
      deleteNode,
      onNodeDelete,
      onAddMaterial,
      addChildNode,
    ],
  );

  const allowDrop: TreeProps['allowDrop'] = ({
    dragNode,
    dropNode,
    dropPosition,
  }) => {
    const dragLevel = getNodeLevel(treeData, dragNode.key);
    const dropLevel = getNodeLevel(treeData, dropNode.key);

    // 如果是放到节点上，检查是否符合层级要求
    if (dropPosition === 0) {
      const targetLevel = dropLevel + 1;
      return dragLevel === targetLevel;
    }

    // 如果是放到节点前后，检查是否同级
    return dragLevel === dropLevel;
  };

  return (
    <div className={styles.interactiveTree}>
      <Tree
        className={styles.tree}
        treeData={treeData}
        titleRender={titleRender}
        draggable
        blockNode
        allowDrop={allowDrop}
        onDrop={onDrop}
        expandedKeys={expandedKeys}
        onExpand={useCallback((keys: React.Key[]) => {
          console.log('展开/收起的节点:', keys);
          setExpandedKeys(keys);
        }, [])}
        autoExpandParent={false}
        selectable={false}
      />
      <Button
        type="dashed"
        icon={<PlusOutlined />}
        className={styles.addChapterButton}
        onClick={useCallback(() => addChildNode(null), [addChildNode])}
      >
        添加章节
      </Button>
    </div>
  );
};

export default InteractiveTree;
