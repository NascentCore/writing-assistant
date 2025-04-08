import FilePreview from '@/components/FilePreview';
import { fetchWithAuthStream } from '@/utils/fetch';
import { FileTextOutlined } from '@ant-design/icons';
import { Popover } from 'antd';
import React, { useState } from 'react';
import { ReferenceMarkerProps } from './type';

/**
 * 自定义引用标识组件
 */
const ReferenceMarker: React.FC<ReferenceMarkerProps> = ({
  index,
  referenceFile,
}) => {
  const [hovered, setHovered] = useState(false);
  // FilePreview 相关状态
  const [filePreviewVisible, setFilePreviewVisible] = useState(false);

  // 点击标题时使用 FilePreview 组件预览文件
  const handleTitleClick = () => {
    console.log('打开文件预览:', {
      file_id: referenceFile.file_id,
      file_name: referenceFile.file_name,
      content_length: referenceFile.content?.length,
      content:
        referenceFile.content?.substring(0, 100) +
        (referenceFile.content?.length > 100 ? '...' : ''),
    });
    setFilePreviewVisible(true);
  };

  // 获取文件数据的函数，提供给 FilePreview 组件
  const fetchFile = async (): Promise<string> => {
    if (!referenceFile.file_id) {
      throw new Error('文件ID不存在');
    }

    try {
      console.log('开始获取文件:', referenceFile.file_id);
      const response = await fetchWithAuthStream(
        `/api/v1/rag/files/${referenceFile.file_id}/download`,
        { method: 'GET' },
        true,
      );

      if (!response) {
        console.error('获取文件失败: 响应为空');
        throw new Error('获取文件失败');
      }

      console.log('成功获取文件, 准备创建Blob');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      console.log('创建Blob URL成功:', url.substring(0, 100));
      return url;
    } catch (error) {
      console.error('获取文件内容失败:', error);
      throw error;
    }
  };

  // 自定义标题组件
  const customTitle = (
    <div
      style={{
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        color: '#1677ff',
      }}
      onClick={handleTitleClick}
    >
      <FileTextOutlined style={{ marginRight: 4 }} />
      {referenceFile.file_name || '引用文件'}
    </div>
  );

  return (
    <>
      <Popover
        title={customTitle}
        content={
          <div
            style={{ maxWidth: '300px', maxHeight: '200px', overflow: 'auto' }}
          >
            <div style={{ whiteSpace: 'pre-wrap' }}>
              {referenceFile.content || '无内容'}
            </div>
          </div>
        }
        trigger="hover"
      >
        <span
          style={{
            display: 'inline-block',
            backgroundColor: hovered ? '#1677ff' : 'rgba(0, 0, 0, 0.15)',
            color: 'white',
            width: '16px',
            height: '16px',
            borderRadius: '50%',
            textAlign: 'center',
            lineHeight: '16px',
            fontSize: '10px',
            cursor: 'pointer',
            margin: '0 2px',
            userSelect: 'none',
            transition: 'background-color 0.2s',
            verticalAlign: 'text-bottom',
          }}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
        >
          {index + 1}
        </span>
      </Popover>

      {/* 使用 FilePreview 组件预览文件 */}
      <FilePreview
        open={filePreviewVisible}
        onCancel={() => setFilePreviewVisible(false)}
        fetchFile={fetchFile}
        fileName={referenceFile.file_name || '未知文件'}
      />

      {/* 检查 referenceFile.content 的内容 */}
      <div style={{ display: 'none' }}>
        {JSON.stringify({
          hasContent: !!referenceFile.content,
          contentLength: referenceFile.content?.length,
          contentSample: referenceFile.content?.substring(0, 30),
        })}
      </div>
    </>
  );
};

export default ReferenceMarker;
