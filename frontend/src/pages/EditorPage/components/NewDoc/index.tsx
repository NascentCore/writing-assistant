import { API_BASE_URL } from '@/config';
import { fetchWithAuth } from '@/utils/fetch';
import { Button, Input, Modal } from 'antd';
import { useState } from 'react';

interface NewDocProps {
  onSuccess: () => void;
  onClose: () => void;
  visible: boolean;
}

const NewDoc: React.FC<NewDocProps> = ({ onSuccess, onClose, visible }) => {
  const [newDocTitle, setNewDocTitle] = useState('');
  const [loading, setLoading] = useState(false);

  const handleNewDocument = async () => {
    if (!newDocTitle.trim()) {
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
        setNewDocTitle('');
        onSuccess();
        onClose();
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

  return (
    <Modal
      title="新建文档"
      open={visible}
      onCancel={onClose}
      footer={[
        <Button key="cancel" onClick={onClose}>
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
        onPressEnter={handleNewDocument}
      />
    </Modal>
  );
};

export default NewDoc;
