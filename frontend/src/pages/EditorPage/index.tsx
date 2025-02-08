import { API_BASE_URL } from '@/config';
import { fetchWithAuth } from '@/utils/fetch';
import { useDebounceFn } from 'ahooks';
import { AiEditor } from 'aieditor';
import 'aieditor/dist/style.css';
import { Button } from 'antd';
import type { DataNode } from 'antd/es/tree';
import { useCallback, useEffect, useRef, useState } from 'react';
import DocumentList from './components/DocumentList';
import ExportBtnGroup from './components/ExportBtn';
import NewDoc from './components/NewDoc';
import OutLine from './components/OutLine';
import UserProfile from './components/UserProfile';
import VersionHistory from './components/VersionHistory';
import { getEditorConfig } from './editorConfig';
import './index.less';

// 定义存储当前文档ID的key
const CURRENT_DOC_KEY = 'current_document_id';

interface OutlineNode extends DataNode {
  pos: number;
  size: number;
  level: number;
}

function App() {
  const divRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<AiEditor | null>(null);
  const [currentDocId, setCurrentDocId] = useState<string | null>(() => {
    return localStorage.getItem(CURRENT_DOC_KEY) || null;
  });

  const [showNewDocDialog, setShowNewDocDialog] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [outlineData, setOutlineData] = useState<OutlineNode[]>([]);

  // 保存文档内容的函数
  const saveDocument = async (content: string) => {
    if (!currentDocId) return;

    try {
      const response = await fetchWithAuth(
        `${API_BASE_URL}/api/v1/documents/` + currentDocId,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ content }),
        },
      );
      if (!response) return;
      if (response.ok) {
        // setLastSavedTime(new Date()); // 未使用的变量
      }
    } catch (error) {
      console.error('Save error:', error);
    }
  };
  const { run: saveDocumentDebounce } = useDebounceFn(saveDocument, {
    wait: 1000,
  });

  function updateOutLine(editor: AiEditor) {
    const outlines = editor.getOutline();
    const treeData: OutlineNode[] = outlines.map((outline) => ({
      key: outline.id,
      title: outline.text,
      pos: outline.pos,
      size: outline.size,
      level: outline.level,
    }));
    setOutlineData(treeData);
  }

  // 新增加载文档内容的函数
  const loadDocumentContent = useCallback(
    async (editor: AiEditor, docId: string) => {
      try {
        const response = await fetchWithAuth(
          `${API_BASE_URL}/api/v1/documents/${docId}`,
        );
        if (response && response.ok) {
          const result = await response.json();
          const content = result.data.content || '';

          // 创建临时 div 来解析内容
          const tempDiv = document.createElement('div');
          tempDiv.innerHTML = content;

          // 查找所有段落和标题元素并处理样式
          const elements = tempDiv.querySelectorAll(
            'p, h1, h2, h3, h4, h5, h6',
          ) as NodeListOf<HTMLElement>;
          elements.forEach((element) => {
            const textAlign =
              element.style.textAlign ||
              element.getAttribute('data-text-align') ||
              (element.classList.contains('is-style-text-align-center')
                ? 'center'
                : '');

            if (textAlign === 'center') {
              element.style.textAlign = 'center';
              element.setAttribute('data-text-align', 'center');
              element.classList.add('is-style-text-align-center');
            }
          });

          // 设置内容并立即定位光标到开头
          editor.setContent(tempDiv.innerHTML);
          requestAnimationFrame(() => {
            // 将所有可能的滚动容器都滚动到顶部
            const editorElement = editor.innerEditor.view.dom;
            const scrollContainers = [
              editorElement.parentElement,
              document.querySelector('.aie-container-panel'),
              document.querySelector('.aie-container-main'),
            ];

            scrollContainers.forEach((container) => {
              if (container) {
                container.scrollTop = 0;
              }
            });
            editor.focusStart();
          });
        }
      } catch (error) {
        console.error('Fetch document error:', error);
      }
    },
    [],
  );

  // 监听 currentDocId 变化，只更新内容
  useEffect(() => {
    if (editorRef.current && currentDocId) {
      loadDocumentContent(editorRef.current, currentDocId);
    }
  }, [currentDocId, loadDocumentContent]);

  // 修改编辑器初始化代码，只在组件挂载时执行一次
  useEffect(() => {
    if (divRef.current) {
      const aiEditor = new AiEditor({
        ...getEditorConfig(divRef.current),
        onCreated: async (editor) => {
          // 在编辑器创建完成后，如果有当前文档ID，就加载文档内容
          if (currentDocId) {
            await loadDocumentContent(editor, currentDocId);
          } else {
            updateOutLine(editor);
          }
        },
        onChange: async (editor) => {
          // 更新大纲
          updateOutLine(editor);
          const content = editor.getHtml();
          saveDocumentDebounce(content);
        },
      });

      editorRef.current = aiEditor;

      return () => {
        aiEditor.destroy();
      };
    }
  }, []); // 依赖项为空数组，只在组件挂载时执行一次

  // 添加登出处理函数
  const handleLogout = () => {
    localStorage.removeItem('token');
    setCurrentDocId(null);
    // 退出登录后直接跳转到登录界面
    window.location.href = '/login';
  };

  // 监听 currentDocId 变化，保存到 localStorage
  useEffect(() => {
    if (currentDocId) {
      localStorage.setItem(CURRENT_DOC_KEY, currentDocId);
    } else {
      localStorage.removeItem(CURRENT_DOC_KEY);
    }
  }, [currentDocId]);

  return (
    <div style={{ padding: 0, margin: 0, background: '#f3f4f6' }}>
      <>
        <div className="page-header">
          <h1>售前方案写作助手</h1>
          <div className="header-buttons">
            <Button onClick={() => setShowNewDocDialog(true)}>新建文档</Button>
            <ExportBtnGroup editorRef={editorRef} />
            {currentDocId && (
              <Button onClick={() => setShowVersionHistory(true)}>
                版本历史
              </Button>
            )}

            <div className="user-buttons">
              <Button onClick={() => setShowProfile(true)}>个人信息</Button>
              <Button onClick={handleLogout}>退出登录</Button>
            </div>
          </div>
        </div>

        {/* 添加个人信息对话框 */}
        {showProfile && <UserProfile onClose={() => setShowProfile(false)} />}

        {/* 新建文档对话框 */}
        <NewDoc
          visible={showNewDocDialog}
          onClose={() => setShowNewDocDialog(false)}
          onSuccess={() => {
            // 重新加载文档列表
          }}
        />

        {showVersionHistory && currentDocId && (
          <VersionHistory
            docId={currentDocId}
            onClose={() => setShowVersionHistory(false)}
            onRollback={async () => {
              if (editorRef.current) {
                try {
                  const response = await fetchWithAuth(
                    `${API_BASE_URL}/api/v1/documents/` + currentDocId,
                  );
                  if (response && response.ok) {
                    const result = await response.json();
                    editorRef.current.setContent(result.data.content || '');
                  }
                } catch (error) {
                  console.error('Load document content error:', error);
                }
              }
            }}
          />
        )}

        <div ref={divRef} style={{ padding: 0, margin: 0 }}>
          <div className="aie-container" style={{ backgroundColor: '#f3f4f6' }}>
            <div className="aie-header-panel">
              <div className="aie-container-header"></div>
            </div>
            <div className="aie-main">
              <div className="aie-directory-content">
                <div className="aie-directory">
                  <div
                    style={{ background: '#fff', padding: 20, marginTop: 18 }}
                  >
                    <h5>我的文档</h5>
                    <DocumentList
                      currentDocId={currentDocId}
                      onDocumentSelect={(docId) => {
                        saveDocument(editorRef.current?.getHtml() || '');
                        setCurrentDocId(docId);
                      }}
                      onDocumentsChange={() => {
                        // 重新加载文档列表
                      }}
                    />
                  </div>
                </div>
              </div>
              <div className="aie-container-panel">
                <div className="aie-container-main"></div>
              </div>
              <div className="aie-outline" style={{ width: 280 }}>
                <OutLine editorRef={editorRef} outlineData={outlineData} />
              </div>
            </div>
            <div className="aie-container-footer"></div>
          </div>
        </div>
      </>
    </div>
  );
}

export default App;
