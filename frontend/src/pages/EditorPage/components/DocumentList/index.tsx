import { API_BASE_URL } from '@/config';
import { fetchWithAuth } from '@/utils/fetch';
import { EllipsisOutlined, FileTextOutlined } from '@ant-design/icons';
import {
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
  onDocumentSelect: (docId: string) => void;
  onDocumentsChange: () => void;
}

const DocumentList: React.FC<DocumentListProps> = ({
  currentDocId,
  onDocumentSelect,
  onDocumentsChange,
}) => {
  const [documents, setDocuments] = useState<any[]>([]);
  const [renameModalVisible, setRenameModalVisible] = useState(false);
  const [deleteModalVisible, setDeleteModalVisible] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<{
    id: string;
    title: string;
  } | null>(null);
  const [newTitle, setNewTitle] = useState('');

  // 加载文档列表
  const loadDocuments = async () => {
    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/documents`);
      if (!response) return;
      if (response.ok) {
        const result = await response.json();
        setDocuments(result.data);

        // 如果没有当前选中的文档，但有文档列表，则选择最近的文档
        if (!currentDocId && result.data.length > 0) {
          const mostRecentDoc = result.data[0];
          onDocumentSelect(mostRecentDoc.id);
        } else if (currentDocId) {
          // 验证当前文档是否存在于列表中
          const docExists = result.data.some(
            (doc: { id: number }) => doc.id === parseInt(currentDocId, 10),
          );
          if (!docExists && result.data.length > 0) {
            // 如果当前文档不存在，选择最近的文档
            onDocumentSelect(result.data[0].id);
          }
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
        onDocumentsChange();
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
        if (currentDocId === selectedDoc.id) {
          onDocumentSelect('');
        }
        loadDocuments();
        onDocumentsChange();
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

  useEffect(() => {
    loadDocuments();
  }, []);

  const getDropdownItems = (doc: any): MenuProps['items'] => [
    {
      key: 'rename',
      label: '重命名',
      onClick: () => {
        handleRename(doc.id, doc.title);
      },
    },
    {
      key: 'delete',
      label: '删除',
      danger: true,
      onClick: () => {
        handleDelete(doc.id, doc.title);
      },
    },
  ];

  return (
    <>
      <List
        className="document-list"
        dataSource={documents}
        renderItem={(doc) => {
          const isActive = currentDocId && Number(currentDocId) === doc.id;
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
    </>
  );
};

export default DocumentList;
