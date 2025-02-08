import { API_BASE_URL } from '@/config';
import { fetchWithAuth } from '@/utils/fetch';
import { Modal } from 'antd';
import React, { useEffect, useState } from 'react';
import './index.less';

interface Version {
  version: string;
  content: string;
  created_at: string;
  comment?: string;
}

interface VersionHistoryProps {
  docId: string;
  onClose: () => void;
  onRollback: () => void;
}

const VersionHistory: React.FC<VersionHistoryProps> = ({
  docId,
  onClose,
  onRollback,
}) => {
  const [versions, setVersions] = useState<Version[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<Version | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const loadVersions = async (): Promise<void> => {
    try {
      const response = await fetchWithAuth(
        `${API_BASE_URL}/api/v1/documents/${docId}/versions`,
        {
          method: 'GET',
        },
      );

      if (response && response.ok) {
        const result = await response.json();
        setVersions(result.data);
        if (result.data.length > 0) {
          setSelectedVersion(result.data[0]);
        }
      }
    } catch (error) {
      console.error('Load versions error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadVersions();
  }, [docId]);

  const handleRollback = async (versionId: string): Promise<void> => {
    Modal.confirm({
      title: '确认回滚',
      content: `确定要回滚到版本 ${versionId} 吗？`,
      onOk: async () => {
        try {
          const response = await fetchWithAuth(
            `${API_BASE_URL}/api/v1/documents/${docId}/rollback/${versionId}`,
            {
              method: 'PUT',
            },
          );

          if (response && response.ok) {
            onRollback();
            onClose();
          }
        } catch (error) {
          console.error('Rollback error:', error);
          Modal.error({
            title: '错误',
            content: '回滚失败',
          });
        }
      },
    });
  };

  return (
    <div className="version-history-container-forUni">
      <div className="version-history-overlay">
        <div className="version-history-modal">
          <div className="version-history-header">
            <h2>版本历史</h2>
            <button type="button" className="close-btn" onClick={onClose}>
              ×
            </button>
          </div>
          <div className="version-history-content">
            <div className="version-list">
              {loading ? (
                <div className="loading">加载中...</div>
              ) : versions.length === 0 ? (
                <div className="no-versions">暂无版本历史</div>
              ) : (
                versions.map((version) => (
                  <div
                    key={version.version}
                    className={`version-item ${
                      selectedVersion?.version === version.version
                        ? 'active'
                        : ''
                    }`}
                    onClick={() => setSelectedVersion(version)}
                  >
                    <div className="version-info">
                      <span className="version-number">
                        版本 {version.version}
                      </span>
                      <span className="version-time">{version.created_at}</span>
                    </div>
                    {version.comment && (
                      <div className="version-comment">{version.comment}</div>
                    )}
                  </div>
                ))
              )}
            </div>
            {selectedVersion && (
              <div className="version-preview">
                <div className="preview-header">
                  <h3>版本预览</h3>
                  <button
                    type="button"
                    className="rollback-btn"
                    onClick={() => handleRollback(selectedVersion.version)}
                  >
                    回滚到此版本
                  </button>
                </div>
                <div
                  className="preview-content"
                  dangerouslySetInnerHTML={{ __html: selectedVersion.content }}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default VersionHistory;
