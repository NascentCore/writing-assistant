import React, { useState, useEffect } from 'react';
import { fetchWithAuth } from '../utils/fetch';
import { API_BASE_URL } from '../config';
import '../styles/version-history.css';


const VersionHistory = ({ docId, onClose, onRollback }) => {
  const [versions, setVersions] = useState([]);
  const [selectedVersion, setSelectedVersion] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadVersions();
  }, [docId]);

  const loadVersions = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/documents/${docId}/versions`, {
        // ... 其他配置
      });
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

  const handleRollback = async (versionId) => {
    if (window.confirm(`确定要回滚到版本 ${versionId} 吗？`)) {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/documents/${docId}/rollback/${versionId}`, {
          // ... 其他配置
        });
        if (response && response.ok) {
          onRollback();
          onClose();
        }
      } catch (error) {
        console.error('Rollback error:', error);
        alert('回滚失败');
      }
    }
  };

  return (
    <div className="version-history-overlay">
      <div className="version-history-modal">
        <div className="version-history-header">
          <h2>版本历史</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        <div className="version-history-content">
          <div className="version-list">
            {loading ? (
              <div className="loading">加载中...</div>
            ) : versions.length === 0 ? (
              <div className="no-versions">暂无版本历史</div>
            ) : (
              versions.map(version => (
                <div
                  key={version.version}
                  className={`version-item ${selectedVersion?.version === version.version ? 'active' : ''}`}
                  onClick={() => setSelectedVersion(version)}
                >
                  <div className="version-info">
                    <span className="version-number">版本 {version.version}</span>
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
  );
};

export default VersionHistory; 