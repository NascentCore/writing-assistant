import { fetchWithAuthNew } from '@/utils/fetch';
import { BarsOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import {
  Button,
  Dropdown,
  Input,
  MenuProps,
  Spin,
  Tree,
  TreeProps,
} from 'antd';
import type { DataNode } from 'antd/es/tree';
import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useState,
} from 'react';
import styles from './index.module.less';

interface TreeNode extends Omit<DataNode, 'title'> {
  title: string;
  description?: string;
  count_style?: string;
  children?: TreeNode[];
  level: number;
}

interface InteractiveTreeProps {
  onNodeUpdate?: (node: TreeNode) => void;
  onNodeDelete?: (key: React.Key) => void;
  onNodeAdd?: (parentKey: React.Key | null, node: TreeNode) => void;
  onAddMaterial?: (nodeKey: React.Key) => void;
  outlineId?: string | number;
  readOnly?: boolean;
}

const items: MenuProps['items'] = [
  {
    key: 'short',
    label: '短篇',
  },
  {
    key: 'medium',
    label: '中篇',
  },
  {
    key: 'long',
    label: '长篇',
  },
];
// 抽离节点编辑组件以优化性能
const NodeTitle: React.FC<{
  node: TreeNode;
  editingNode: { title: string; description: string; count_style?: string };
  onTitleChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onTitleBlur: () => void;
  onDescriptionBlur: () => void;
  onAddMaterial?: () => void;
  onAddChild?: () => void;
  onDelete?: () => void;
  onMenuSelect?: (key: string) => void;
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
    onMenuSelect,
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
      <div
        className={styles.nodeContent}
        onMouseEnter={handleInputMouseEnter}
        onMouseLeave={handleInputMouseLeave}
      >
        <div className={styles.inputWrapper}>
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
            <Dropdown
              trigger={['click']}
              menu={{
                items,
                selectable: true,
                selectedKeys: editingNode.count_style
                  ? [editingNode.count_style]
                  : undefined,
                onClick: ({ key }) => onMenuSelect?.(key as string),
              }}
              placement="bottomLeft"
            >
              <BarsOutlined
                className={styles.actionIcon}
                onClick={(e) => {
                  e.stopPropagation();
                  onAddMaterial?.();
                }}
              />
            </Dropdown>
          )}
          {level < 11 && (
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

const InteractiveTree = forwardRef<
  {
    getTreeData: () => TreeNode[];
    getOutlineTitle: () => string;
    getInteractiveTreeData: () => {
      treeData: TreeNode[];
      outlineTitle: string;
    };
  },
  InteractiveTreeProps
>(({ onNodeDelete, onNodeAdd, onAddMaterial, outlineId, readOnly }, ref) => {
  const [treeData, setTreeData] = useState<TreeNode[]>([]);
  const [outlineTitle, setOutlineTitle] = useState<string>('');
  const [loading, setLoading] = useState(false);
  useImperativeHandle(ref, () => ({
    getTreeData: () => {
      return treeData;
    },
    getOutlineTitle: () => {
      return outlineTitle;
    },
    getInteractiveTreeData: () => {
      return {
        treeData,
        outlineTitle,
      };
    },
  }));

  // 从props获取outline_id
  useEffect(() => {
    const fetchOutlineData = async () => {
      if (outlineId) {
        setLoading(true);
        try {
          const response = await fetchWithAuthNew<any>(
            `/api/v1/writing/outlines/${outlineId}`,
          );
          if (response && response.sub_paragraphs) {
            // 直接使用接口返回的sub_paragraphs作为树节点数据
            setTreeData(response.sub_paragraphs);
            setOutlineTitle(response.title);
          }
        } catch (error) {
          console.error('获取大纲数据失败:', error);
        } finally {
          setLoading(false);
        }
      } else {
        // 如果没有提供outline_id，使用默认数据
        setTreeData([
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
                    key: '1-1-1',
                    title: '1.1.1 节',
                    description: '',
                    level: 3,
                    children: [
                      {
                        key: '1-1-1-1',
                        title: '1.1.1.1 节',
                        description: '',
                        level: 4,
                      },
                      {
                        key: '1-1-1-2',
                        title: '1.1.1.2 节',
                        description: '',
                        level: 4,
                      },
                    ],
                  },
                  {
                    key: '1-1-2',
                    title: '1.1.2 节',
                    description: '',
                    level: 3,
                  },
                  {
                    key: '1-1-3',
                    title: '1.1.3 节',
                    description: '',
                    level: 3,
                  },
                ],
              },
            ],
          },
        ]);
      }
    };

    fetchOutlineData();
  }, [outlineId]);

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

  // 获取父节点下的最大子节点索引
  const getMaxChildIndex = useCallback(
    (nodes: TreeNode[], parentKey: React.Key | null): number => {
      if (!parentKey) {
        // 如果是顶级节点，找出所有顶级节点中的最大索引
        return nodes.reduce((max, node) => {
          const index = parseInt(String(node.key), 10);
          return isNaN(index) ? max : Math.max(max, index);
        }, 0);
      }

      // 递归查找父节点及其子节点
      const findMaxChildIndex = (
        nodeList: TreeNode[],
        targetKey: React.Key,
      ): number => {
        for (const node of nodeList) {
          if (node.key === targetKey) {
            // 找到目标节点，计算其子节点的最大索引
            if (!node.children || node.children.length === 0) {
              return 0;
            }

            return node.children.reduce((max, child) => {
              const parts = String(child.key).split('-');
              const lastIndex = parseInt(parts[parts.length - 1], 10);
              return isNaN(lastIndex) ? max : Math.max(max, lastIndex);
            }, 0);
          }

          // 如果当前节点有子节点，递归查找
          if (node.children && node.children.length > 0) {
            const result = findMaxChildIndex(node.children, targetKey);
            if (result > 0) {
              return result;
            }
          }
        }

        return 0; // 如果没有找到目标节点或没有子节点
      };

      return findMaxChildIndex(nodes, parentKey);
    },
    [],
  );

  // 生成新节点的键
  const generateNodeKey = useCallback(
    (parentKey: React.Key | null): string => {
      if (!parentKey) {
        // 顶级节点，格式为数字
        const maxIndex = getMaxChildIndex(treeData, null);
        return String(maxIndex + 1);
      }

      // 子节点，格式为 parentKey-index
      const maxIndex = getMaxChildIndex(treeData, parentKey);
      return `${parentKey}-${maxIndex + 1}`;
    },
    [treeData, getMaxChildIndex],
  );

  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>(() =>
    getDefaultExpandedKeys(treeData),
  );
  const [editingNodes, setEditingNodes] = useState<
    Record<string, { title: string; description: string; count_style?: string }>
  >({});

  useEffect(() => {
    const initialEditingNodes: Record<
      string,
      { title: string; description: string; count_style?: string }
    > = {};
    const initNodes = (nodes: TreeNode[]) => {
      nodes.forEach((node) => {
        initialEditingNodes[node.key as string] = {
          title: node.title,
          description: node.description || '',
          count_style: node.count_style,
        };
        if (node.children) {
          initNodes(node.children);
        }
      });
    };

    if (treeData && treeData.length > 0) {
      initNodes(treeData);
      setEditingNodes(initialEditingNodes);

      // 只在初始加载时设置默认展开的节点，而不是每次treeData更新时
      if (expandedKeys.length === 0) {
        setExpandedKeys(getDefaultExpandedKeys(treeData));
      }
    }
  }, [treeData, getDefaultExpandedKeys, expandedKeys.length]);

  // 使用 useCallback 优化函数
  const updateTreeData = useCallback((newData: TreeNode[]) => {
    console.log('树形数据更新:', newData);
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
      const newKey = generateNodeKey(parentKey);

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
    [
      treeData,
      onNodeAdd,
      addNode,
      getNodeLevel,
      updateTreeData,
      generateNodeKey,
    ],
  );

  const onDrop: TreeProps['onDrop'] = (info) => {
    // 在拖拽前保存当前的展开状态
    const currentExpandedKeys = [...expandedKeys];

    const dropKey = info.node.key;
    const dragKey = info.dragNode.key;
    const dropPos = info.node.pos.split('-');
    const dropPosition =
      info.dropPosition - Number(dropPos[dropPos.length - 1]);

    // 获取节点的层级
    const dragLevel = getNodeLevel(treeData, dragKey);
    const dropLevel = getNodeLevel(treeData, dropKey);

    // 完全禁止跨层级移动
    // 如果是放到节点上（作为子节点），不允许
    if (dropPosition === 0) {
      console.log('不允许将节点作为子节点添加');
      return;
    }

    // 如果是放到节点前后，必须是同级节点
    if (dragLevel !== dropLevel) {
      console.log('只能在同级节点之间拖拽');
      return;
    }

    // 获取父节点键
    const getParentKey = (key: string): string | null => {
      const parts = key.split('-');
      return parts.length > 1 ? parts.slice(0, -1).join('-') : null;
    };

    const dragKeyStr = String(dragKey);
    const dropKeyStr = String(dropKey);
    const dragParent = getParentKey(dragKeyStr);
    const dropParent = getParentKey(dropKeyStr);

    // 必须有相同的父节点
    if (dragParent !== dropParent) {
      console.log('只能在同一父节点下的节点之间拖拽');
      return;
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

    // 在数据更新后恢复原来的展开状态
    setTimeout(() => {
      setExpandedKeys(currentExpandedKeys);
    }, 0);
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

      const handleMenuSelect = (selectedKey: string) => {
        setEditingNodes((prev) => ({
          ...prev,
          [node.key as string]: {
            ...prev[node.key as string],
            count_style: selectedKey,
          },
        }));

        const newTreeData = updateNodeInTree(treeData, node.key, (n) => ({
          ...n,
          count_style: selectedKey,
        }));
        updateTreeData(newTreeData);
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
          onMenuSelect={handleMenuSelect}
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
    // 获取节点的层级
    const dragLevel = getNodeLevel(treeData, dragNode.key);
    const dropLevel = getNodeLevel(treeData, dropNode.key);

    // 完全禁止跨层级移动
    // 如果是放到节点上（作为子节点），不允许
    if (dropPosition === 0) {
      return false;
    }

    // 如果是放到节点前后，必须是同级节点
    if (dragLevel !== dropLevel) {
      return false;
    }

    // 获取父节点键
    const getParentKey = (key: string): string | null => {
      const parts = key.split('-');
      return parts.length > 1 ? parts.slice(0, -1).join('-') : null;
    };

    const dragKey = String(dragNode.key);
    const dropKey = String(dropNode.key);
    const dragParent = getParentKey(dragKey);
    const dropParent = getParentKey(dropKey);

    // 必须有相同的父节点
    return dragParent === dropParent;
  };
  const addChapter = useCallback(() => addChildNode(null), [addChildNode]);
  return (
    <div className={styles.interactiveTree}>
      {readOnly && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            left: 0,
            right: 0,
            backgroundColor: 'transparent',
            zIndex: 2,
          }}
        ></div>
      )}
      <Spin spinning={loading}>
        <div style={{ display: loading ? 'none' : 'block' }}>
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <Input
              style={{ width: '80%', marginBottom: 20 }}
              prefix="文章标题："
              value={outlineTitle}
              onChange={(e) => setOutlineTitle(e.target.value)}
              placeholder="请输入文章标题"
            />
          </div>

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
              setExpandedKeys(keys);
            }, [])}
            autoExpandParent={false}
            selectable={false}
          />
          {!readOnly && (
            <Button
              type="dashed"
              icon={<PlusOutlined />}
              className={styles.addChapterButton}
              onClick={addChapter}
            >
              添加章节
            </Button>
          )}
        </div>
      </Spin>
    </div>
  );
});

export default InteractiveTree;
