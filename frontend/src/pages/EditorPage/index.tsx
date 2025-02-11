import { API_BASE_URL } from '@/config';
import { fetchWithAuth } from '@/utils/fetch';
import { useDebounceFn } from 'ahooks';
import { AiEditor } from 'aieditor';
import 'aieditor/dist/style.css';
import { Button } from 'antd';
import type { DataNode } from 'antd/es/tree';
import { useCallback, useEffect, useRef, useState } from 'react';
import AIChat from './components/AIChat';
import DocumentList from './components/DocumentList';
import ExportBtnGroup from './components/ExportBtn';
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

  const [showProfile, setShowProfile] = useState(false);
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [outlineData, setOutlineData] = useState<OutlineNode[]>([]);
  const [showAIChat, setShowAIChat] = useState(false);

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
        textSelectionBubbleMenu: {
          enable: true,
          items: [
            'ai',
            'Bold',
            'Italic',
            'Underline',
            {
              id: 'visit',
              title: '插入到对话',
              icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M10 6V8H5V19H16V14H18V20C18 20.5523 17.5523 21 17 21H4C3.44772 21 3 20.5523 3 20V7C3 6.44772 3.44772 6 4 6H10ZM21 3V11H19L18.9999 6.413L11.2071 14.2071L9.79289 12.7929L17.5849 5H13V3H21Z"></path></svg>',
              onClick: (editor) => {
                const content = editor.getSelectedText();
                console.log('🚀 ~ useEffect ~ content:', content);
                // window.open('https://aieditor.dev', '_blank');
              },
            },
          ],
        },
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

  // 添加键盘事件监听
  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      // 检查是否按下 Ctrl + K
      if (event.ctrlKey && event.key.toLowerCase() === 'k') {
        event.preventDefault(); // 阻止默认行为
        setShowAIChat((prev) => !prev);
      }
    };

    // 添加事件监听
    window.addEventListener('keydown', handleKeyPress);

    // 清理函数
    return () => {
      window.removeEventListener('keydown', handleKeyPress);
    };
  }, []);

  return (
    <div style={{ padding: 0, margin: 0, background: '#f3f4f6' }}>
      <>
        <div className="page-header">
          <h1>售前方案写作助手</h1>
          <div className="header-buttons">
            <Button onClick={() => setShowAIChat(!showAIChat)}>AI对话</Button>
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
          <div
            className={`aie-container ${showAIChat ? 'with-ai-chat' : ''}`}
            style={{ backgroundColor: '#f3f4f6' }}
          >
            <div className="aie-header-panel">
              <div className="aie-container-header"></div>
            </div>
            <div className="aie-main">
              <div className="aie-directory-content">
                <div className="aie-directory">
                  <div
                    style={{ background: '#fff', padding: 20, marginTop: 18 }}
                  >
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
          {showAIChat && (
            <div className="ai-chat-panel">
              <AIChat />
            </div>
          )}
        </div>
      </>
    </div>
  );
}

export default App;
