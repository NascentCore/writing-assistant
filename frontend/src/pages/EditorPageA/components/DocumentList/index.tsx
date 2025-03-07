import { API_BASE_URL } from '@/config';
import { fetchWithAuth } from '@/utils/fetch';
import {
  EllipsisOutlined,
  FileTextOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { useModel } from '@umijs/max';
import {
  Button,
  Dropdown,
  Input,
  List,
  MenuProps,
  Modal,
  Space,
  Typography,
} from 'antd';
import { useEffect, useState } from 'react';

interface DocumentListProps {
  currentDocId: string | null;
  onDocumentSelect: (docId: string | null) => void;
}

const DocumentList: React.FC<DocumentListProps> = ({
  currentDocId,
  onDocumentSelect,
}) => {
  const { documents, setDocuments } = useModel('EditorPage.model');
  const [renameModalVisible, setRenameModalVisible] = useState(false);
  const [deleteModalVisible, setDeleteModalVisible] = useState(false);
  const [newDocModalVisible, setNewDocModalVisible] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<{
    id: string;
    title: string;
  } | null>(null);
  const [newTitle, setNewTitle] = useState('');
  const [newDocTitle, setNewDocTitle] = useState('');
  const [loading, setLoading] = useState(false);

  // 加载文档列表
  const loadDocuments = async () => {
    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/documents`);
      if (!response) return;
      if (response.ok) {
        const result = await response.json();
        result.data.forEach((doc: any) => {
          doc.id = doc.doc_id;
        });
        setDocuments(result.data);

        // 只在没有当前选中文档时，才自动选择第一个文档
        if (!currentDocId && result.data.length > 0) {
          const mostRecentDoc = result.data[0];
          onDocumentSelect(mostRecentDoc.id);
        }
      }
    } catch (error) {
      console.error('Load documents error:', error);
    }
  };

  // 重命名按钮函数
  const handleRename = async (docId: string, currentTitle: string) => {
    setSelectedDoc({ id: docId, title: currentTitle });
    setNewTitle(currentTitle);
    setRenameModalVisible(true);
  };

  // 确认重命名函数
  const handleConfirmRename = async () => {
    if (!selectedDoc || !newTitle.trim() || newTitle === selectedDoc.title) {
      setRenameModalVisible(false);
      return;
    }

    try {
      const response = await fetchWithAuth(
        `${API_BASE_URL}/api/v1/documents/` + selectedDoc.id,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ title: newTitle.trim() }),
        },
      );

      if (response && response.ok) {
        loadDocuments();
        setRenameModalVisible(false);
      }
    } catch (error) {
      console.error('Rename document error:', error);
      Modal.error({
        title: '重命名失败',
        content: '请稍后重试',
      });
    }
  };

  // 删除按钮函数
  const handleDelete = async (docId: string, title: string) => {
    setSelectedDoc({ id: docId, title });
    setDeleteModalVisible(true);
  };

  // 确认删除函数
  const handleConfirmDelete = async () => {
    if (!selectedDoc) {
      setDeleteModalVisible(false);
      return;
    }

    try {
      const response = await fetchWithAuth(
        `${API_BASE_URL}/api/v1/documents/` + selectedDoc.id,
        {
          method: 'DELETE',
        },
      );

      if (response && response.ok) {
        // 如果删除的是当前选中的文档
        if (currentDocId === selectedDoc.id) {
          localStorage.removeItem('currentDocId');
          // 找到当前文档在列表中的索引
          const currentIndex = documents.findIndex(
            (doc) => doc.id === selectedDoc.id,
          );
          // 如果还有其他文档，选中上一个文档
          if (documents.length > 1) {
            // 如果删除的是第一个文档，选中新的第一个文档
            // 否则选中上一个文档
            const newIndex = currentIndex === 0 ? 1 : currentIndex - 1;
            onDocumentSelect(documents[newIndex].id);
          } else {
            onDocumentSelect(null);
          }
        }
        loadDocuments();
        setDeleteModalVisible(false);
      }
    } catch (error) {
      console.error('Delete document error:', error);
      Modal.error({
        title: '删除失败',
        content: '请稍后重试',
      });
    }
  };

  // 新建文档函数
  const handleNewDocument = async () => {
    if (!newDocTitle.trim() || loading) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/documents`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          title: newDocTitle,
          content: '',
        }),
      });

      if (response?.ok) {
        const result = await response.json();
        setNewDocTitle('');
        loadDocuments();
        setNewDocModalVisible(false);
        // 选中新创建的文档（创建成功的时候把 id 返回给父组件）
        onDocumentSelect(result.data.doc_id);
      } else {
        const result = await response?.json();
        throw new Error(result.message || '创建文档失败');
      }
    } catch (error) {
      console.error('Create document error:', error);
      Modal.error({
        title: '创建失败',
        content: (error as Error).message || '创建文档失败，请稍后重试',
      });
    } finally {
      setLoading(false);
    }
  };

  // 处理新建文档弹窗的关闭
  const handleNewDocModalClose = () => {
    setNewDocModalVisible(false);
    setNewDocTitle(''); // 清空输入框
    setLoading(false); // 重置loading状态
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const getDropdownItems = (doc: any): MenuProps['items'] => [
    {
      key: 'rename',
      label: '重命名',
      onClick: (e) => {
        e.domEvent.stopPropagation();
        handleRename(doc.id, doc.title);
      },
    },
    {
      key: 'delete',
      label: '删除',
      danger: true,
      onClick: (e) => {
        e.domEvent.stopPropagation();
        handleDelete(doc.id, doc.title);
      },
    },
  ];

  return (
    <>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '16px',
        }}
      >
        <Typography.Text strong style={{ fontSize: '16px' }}>
          我的文档
        </Typography.Text>
        <Button
          type="primary"
          size="small"
          icon={<PlusOutlined />}
          onClick={() => setNewDocModalVisible(true)}
        >
          新建文档
        </Button>
      </div>
      <List
        className="document-list"
        dataSource={documents}
        renderItem={(doc) => {
          const isActive = currentDocId && currentDocId === doc.id;
          return (
            <List.Item
              key={doc.id}
              className={isActive ? 'active-doc' : ''}
              onClick={() => onDocumentSelect(doc.id.toString())}
              style={{
                padding: '12px 16px',
                cursor: 'pointer',
                backgroundColor: isActive ? '#e6f4ff' : 'transparent',
                borderRadius: '8px',
                marginBottom: '8px',
                transition: 'all 0.3s',
              }}
            >
              <List.Item.Meta
                avatar={
                  <FileTextOutlined
                    style={{
                      fontSize: '20px',
                      color: isActive ? '#1890ff' : '#8c8c8c',
                    }}
                  />
                }
                title={
                  <Space
                    style={{ width: '100%', justifyContent: 'space-between' }}
                  >
                    <Typography.Text
                      style={{
                        maxWidth: '120px',
                        color: isActive ? '#1890ff' : 'inherit',
                      }}
                      ellipsis={{ tooltip: true }}
                    >
                      {doc.title}
                    </Typography.Text>
                    <Dropdown
                      menu={{ items: getDropdownItems(doc) }}
                      trigger={['click']}
                      placement="bottomRight"
                    >
                      <div onClick={(e) => e.stopPropagation()}>
                        <EllipsisOutlined
                          style={{ color: '#8c8c8c', padding: '4px' }}
                        />
                      </div>
                    </Dropdown>
                  </Space>
                }
                description={
                  <Typography.Text
                    type="secondary"
                    style={{ fontSize: '12px' }}
                  >
                    {doc.updated_at}
                  </Typography.Text>
                }
              />
            </List.Item>
          );
        }}
        style={{
          backgroundColor: 'transparent',
        }}
      />

      {/* 重命名对话框 */}
      <Modal
        title="重命名文档"
        open={renameModalVisible}
        onOk={handleConfirmRename}
        onCancel={() => setRenameModalVisible(false)}
        okText="确定"
        cancelText="取消"
      >
        <Input
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          placeholder="请输入新的文档名称"
          autoFocus
        />
      </Modal>

      {/* 删除确认对话框 */}
      <Modal
        title="删除确认"
        open={deleteModalVisible}
        onOk={handleConfirmDelete}
        onCancel={() => setDeleteModalVisible(false)}
        okText="确定"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        <p>
          确定要删除文档 &quot;{selectedDoc?.title}&quot; 吗？此操作不可恢复。
        </p>
      </Modal>

      {/* 新建文档对话框 */}
      <Modal
        title="新建文档"
        open={newDocModalVisible}
        onCancel={handleNewDocModalClose}
        footer={[
          <Button key="cancel" onClick={handleNewDocModalClose}>
            取消
          </Button>,
          <Button
            key="submit"
            type="primary"
            loading={loading}
            onClick={handleNewDocument}
          >
            确定
          </Button>,
        ]}
      >
        <Input
          value={newDocTitle}
          onChange={(e) => setNewDocTitle(e.target.value)}
          placeholder="请输入文档标题"
          onPressEnter={() => !loading && handleNewDocument()}
          disabled={loading}
        />
      </Modal>
    </>
  );
};

export default DocumentList;
