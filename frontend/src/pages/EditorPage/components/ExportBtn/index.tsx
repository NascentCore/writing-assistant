import { AiEditor } from 'aieditor';
import { Button, Dropdown, Menu } from 'antd';
import React from 'react';
import { API_BASE_URL } from '../../../../config';
import { downloadFile } from '../../../../utils/fetch';

interface ExportBtnGroupProps {
  editorRef: React.MutableRefObject<AiEditor | null>; // 添加 editorRef
}

const ExportBtnGroup: React.FC<ExportBtnGroupProps> = ({ editorRef }) => {
  // 处理导出逻辑
  const handleExport = async (format: string) => {
    if (!editorRef.current) return;

    const currentDocId = new URLSearchParams(window.location.search).get(
      'document_id',
    );
    if (!currentDocId) return;

    try {
      if (format === 'pdf') {
        downloadFile(
          `${API_BASE_URL}/api/v1/documents/${currentDocId}/export/pdf`,
          'pdf',
        );
      } else if (format === 'docx') {
        downloadFile(
          `${API_BASE_URL}/api/v1/documents/${currentDocId}/export/docx`,
          'docx',
        );
      }
    } catch (error) {
      console.error('Export error:', error);
      alert('导出失败，请稍后重试');
    }
  };

  // 定义下拉菜单内容，保留按钮原先的处理函数调用
  const menu = (
    <Menu>
      <Menu.Item
        key="pdf"
        onClick={() => {
          handleExport('pdf');
        }}
      >
        导出为 PDF
      </Menu.Item>
      <Menu.Item
        key="docx"
        onClick={() => {
          handleExport('docx');
        }}
      >
        导出为 Word
      </Menu.Item>
    </Menu>
  );

  return (
    <div>
      <Dropdown overlay={menu} trigger={['click']}>
        <Button>导出</Button>
      </Dropdown>
    </div>
  );
};

export default ExportBtnGroup;
