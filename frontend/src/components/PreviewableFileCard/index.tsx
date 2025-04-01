import type { FileItem } from '@/types/common';
import { Attachments } from '@ant-design/x';
import { Tooltip } from 'antd';
import React, { useState } from 'react';

interface PreviewableFileCardProps {
  file: FileItem;
  onPreview: (fileName: string, fileId: string) => void;
}

const PreviewableFileCard: React.FC<PreviewableFileCardProps> = ({
  file,
  onPreview,
}) => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <Tooltip title="点击预览文件">
      <div
        style={{
          cursor: 'pointer',
          transition: 'all 0.3s ease',
          transform: isHovered ? 'translateY(-2px)' : 'none',
          boxShadow: isHovered ? '0 4px 12px rgba(0, 0, 0, 0.15)' : 'none',
          borderRadius: '6px',
        }}
        onClick={() => onPreview(file.name, file.file_id)}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        role="button"
        aria-label={`预览文件: ${file.name}`}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            onPreview(file.name, file.file_id);
          }
        }}
      >
        <Attachments.FileCard
          item={{
            uid: file.file_id,
            name: file.name,
            size: file.size,
            type: file.type,
            status: 'done',
          }}
        />
      </div>
    </Tooltip>
  );
};

export default PreviewableFileCard;
