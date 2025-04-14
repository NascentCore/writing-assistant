import type { FileItem } from '@/types/common';
import { Attachments } from '@ant-design/x';
import { Tooltip } from 'antd';
import React, { useState } from 'react';

// 添加对知识库文件类型的支持
interface KnowledgeFileItem {
  kb_id?: string;
  kb_type?: string;
  user_id?: string;
  file_id: string;
  file_name?: string;
  file_size?: number;
  file_words?: number;
  department_id?: string;
  department_name?: string;
  status?: string;
  error_message?: string;
  created_at: string;
}

interface PreviewableFileCardProps {
  file: FileItem | KnowledgeFileItem;
  onPreview: (fileName: string, fileId: string) => void;
}

// 文件类型映射函数
const getIconByExtension = (extension: string): string => {
  const map: Record<string, string> = {
    pdf: 'pdf',
    doc: 'word',
    docx: 'word',
    xls: 'excel',
    xlsx: 'excel',
    ppt: 'powerpoint',
    pptx: 'powerpoint',
    jpg: 'image',
    jpeg: 'image',
    png: 'image',
    gif: 'image',
    txt: 'text',
    // 可以根据需要添加更多映射
  };

  return map[extension] || 'unknown';
};

const PreviewableFileCard: React.FC<PreviewableFileCardProps> = ({
  file,
  onPreview,
}) => {
  const [isHovered, setIsHovered] = useState(false);

  // 兼容两种文件结构
  const fileName = 'name' in file ? file.name : file.file_name || '未知文件';
  const fileId = file.file_id;
  const fileSize = 'size' in file ? file.size : file.file_size || 0;

  // 提取文件类型
  const getFileType = () => {
    // 1. 尝试从文件对象的type属性获取
    if ('type' in file && file.type) {
      return file.type;
    }

    // 2. 从文件名中提取扩展名
    const name = 'name' in file ? file.name : file.file_name || '';
    const extension = name.split('.').pop()?.toLowerCase() || '';

    // 3. 将扩展名映射到Ant Design的文件类型
    return getIconByExtension(extension);
  };

  const fileType = getFileType();

  return (
    <Tooltip title={fileName}>
      <div
        style={{
          cursor: 'pointer',
          transition: 'all 0.3s ease',
          transform: isHovered ? 'translateY(-2px)' : 'none',
          boxShadow: isHovered ? '0 4px 12px rgba(0, 0, 0, 0.15)' : 'none',
          borderRadius: '6px',
        }}
        onClick={() => onPreview(fileName, fileId)}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        role="button"
        aria-label={`预览文件: ${fileName}`}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            onPreview(fileName, fileId);
          }
        }}
      >
        <Attachments.FileCard
          item={{
            uid: fileId,
            name: fileName,
            size: fileSize,
            type: fileType,
            status: 'done',
          }}
        />
      </div>
    </Tooltip>
  );
};

export default PreviewableFileCard;
