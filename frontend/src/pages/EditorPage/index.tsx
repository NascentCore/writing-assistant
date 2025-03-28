import { API_BASE_URL } from '@/config';
import { fetchWithAuth } from '@/utils/fetch';
import { history, useLocation, useModel } from '@umijs/max';
import { useDebounceFn } from 'ahooks';
import { AiEditor } from 'aieditor';
import 'aieditor/dist/style.css';
import { Button, Empty, Modal } from 'antd';
import type { DataNode } from 'antd/es/tree';
import { useCallback, useEffect, useRef, useState } from 'react';
import AIChat from './components/AIChat';
import ExportBtnGroup from './components/ExportBtn';
import FileUpload from './components/FileUpload';
import OutLine from './components/OutLine';
import VersionHistory from './components/VersionHistory';
import { getEditorConfig } from './editorConfig';
import './index.less';

interface OutlineNode extends DataNode {
  pos: number;
  size: number;
  level: number;
}

function App() {
  const divRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<AiEditor | null>(null);
  const location = useLocation();

  // 从 URL 查询参数中获取 document_id
  const getDocumentIdFromQuery = () => {
    const query = new URLSearchParams(location.search);
    const documentId = query.get('document_id');
    return documentId;
  };

  const [currentDocId, setCurrentDocId] = useState<string | null>(() => {
    // 优先从 URL 查询参数中获取 document_id
    const docIdFromQuery = getDocumentIdFromQuery();
    if (docIdFromQuery) {
      return docIdFromQuery;
    }
    // 如果 URL 查询参数中没有 document_id，则返回null
    return null;
  });

  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [outlineData, setOutlineData] = useState<OutlineNode[]>([]);
  const [showAIChat, setShowAIChat] = useState(false);
  const { setDocument } = useModel('EditorPage.model');
  const [showFileModal, setShowFileModal] = useState(false);
  // 是否是编辑器内容发生变化, 防止重复保存
  const [changeAction, setChangeAction] = useState(false);
  const aiChatRef = useRef<any>(null);

  // 保存文档内容的函数
  const saveDocument = async (content: string) => {
    if (!currentDocId) return;
    if (changeAction) {
      setChangeAction(false);
      return;
    }
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
    wait: 500,
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
  const loadDocumentContent = useCallback(async (docId: string) => {
    try {
      const response = await fetchWithAuth(
        `${API_BASE_URL}/api/v1/documents/${docId}`,
      );
      if (response && response.ok) {
        const result = await response.json();
        const content = result.data.content || '';
        setDocument(result.data);
        if (result.data.session_ids.length) {
          // 更新路由，添加会话ID参数
          const query = new URLSearchParams(location.search);
          query.set('id', result.data.session_ids[0]);
          history.push(`${location.pathname}?${query.toString()}`);
        }

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

        // 返回处理后的内容
        return tempDiv.innerHTML;
      }
    } catch (error) {
      console.error('Fetch document error:', error);
    }
    return ''; // 如果出错或没有内容，返回空字符串
  }, []);

  // 修改编辑器初始化逻辑
  useEffect(() => {
    const initEditor = async () => {
      if (divRef.current && currentDocId) {
        // 先获取文档内容
        const content = await loadDocumentContent(currentDocId);

        if (!editorRef.current) {
          // 初始化编辑器，将内容通过content属性注入
          const aiEditor = new AiEditor({
            ...getEditorConfig(divRef.current),
            content, // 直接注入内容
            textSelectionBubbleMenu: {
              enable: true,
              items: [
                'ai',
                'Bold',
                'Italic',
                'Underline',
                // {
                //   id: 'visit',
                //   title: '插入到对话',
                //   icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M10 6V8H5V19H16V14H18V20C18 20.5523 17.5523 21 17 21H4C3.44772 21 3 20.5523 3 20V7C3 6.44772 3.44772 6 4 6H10ZM21 3V11H19L18.9999 6.413L11.2071 14.2071L9.79289 12.7929L17.5849 5H13V3H21Z"></path></svg>',
                //   onClick: (editor) => {
                //     const content = editor.getSelectedText();
                //     if (!showAIChat) {
                //       setShowAIChat(true);
                //       setTimeout(() => {
                //         if (content && aiChatRef.current) {
                //           const newFile = {
                //             file_id: generateFileId(),
                //             name:
                //               content.slice(0, 20) +
                //               (content.length > 20 ? '...' : ''),
                //             size: new Blob([content]).size,
                //             type: 'text',
                //             status: 1,
                //             created_at: new Date().toISOString(),
                //           };
                //           aiChatRef.current.addSelectedFile(newFile);
                //         }
                //       }, 0);
                //     } else if (content && aiChatRef.current) {
                //       const newFile = {
                //         file_id: generateFileId(),
                //         name:
                //           content.slice(0, 20) +
                //           (content.length > 20 ? '...' : ''),
                //         size: new Blob([content]).size,
                //         type: 'text',
                //         status: 1,
                //         created_at: new Date().toISOString(),
                //       };
                //       aiChatRef.current.addSelectedFile(newFile);
                //     }
                //   },
                // },
              ],
            },
            onCreated: (editor) => {
              // 初始化后执行滚动到顶部和聚焦
              updateOutLine(editor);
            },
            onChange: async (editor) => {
              updateOutLine(editor);
              const content = editor.getHtml();
              saveDocumentDebounce(content);
            },
          });

          editorRef.current = aiEditor;
        } else {
          // 如果编辑器已存在，使用setContent方法更新内容
          editorRef.current.setContent(content);
        }
      }
    };

    if (currentDocId) {
      initEditor();
    }

    return () => {
      if (!currentDocId && editorRef.current) {
        editorRef.current.destroy();
        editorRef.current = null;
      }
    };
  }, [currentDocId]);

  // 监听 URL 查询参数变化，更新 currentDocId
  useEffect(() => {
    const docIdFromQuery = getDocumentIdFromQuery();
    if (docIdFromQuery && docIdFromQuery !== currentDocId) {
      setCurrentDocId(docIdFromQuery);
    }
  }, [location.search]);

  // 添加键盘事件监听
  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      // 检查是否按下 Ctrl + K
      if (event.metaKey && event.key.toLowerCase() === 'l') {
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
    <div
      className="editor-page"
      style={{ padding: 0, margin: 0, background: '#f3f4f6' }}
    >
      <>
        <div
          className="page-header"
          style={{
            ...(showAIChat
              ? {
                  right: 500,
                }
              : {}),
          }}
        >
          {!(window as any).isIframe && (
            <Button
              style={{ marginLeft: 10 }}
              onClick={() => {
                // 更新路由，添加会话ID参数
                const query = new URLSearchParams(location.search);
                history.push(`/WritingHistory?id=${query.get('pre-id') || ''}`);
              }}
            >
              返回
            </Button>
          )}
          <div className="header-buttons">
            {/* <Button onClick={() => setShowFileModal(true)}> 文件上传</Button> */}
            <Button onClick={() => setShowAIChat(!showAIChat)}>AI对话</Button>
            <ExportBtnGroup editorRef={editorRef} />
            {(window as any).isIframe && (
              <>
                <Button
                  onClick={() => {
                    window.parent.postMessage({ type: 'onCancel' }, '*'); // 发送消息到父页面
                  }}
                  ghost
                  type="primary"
                >
                  取消
                </Button>
                <Button
                  onClick={() => {
                    if (editorRef?.current) {
                      window.parent.postMessage(
                        {
                          type: 'onUpdate',
                          value: editorRef.current.getHtml(),
                        },
                        '*',
                      );
                    }
                  }}
                  type="primary"
                >
                  更新
                </Button>
              </>
            )}
            {currentDocId && !(window as any).isIframe && (
              <Button onClick={() => setShowVersionHistory(true)}>
                版本历史
              </Button>
            )}
          </div>
        </div>

        {/* 文件上传对话框 */}
        <Modal
          title="文件上传"
          open={showFileModal}
          onCancel={() => setShowFileModal(false)}
          footer={null}
          width={800}
        >
          <FileUpload />
        </Modal>

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

        <div
          ref={divRef}
          style={{
            padding: 0,
            margin: 0,
            ...(showAIChat
              ? {
                  width: 'calc(100% - 500px)',
                }
              : {}),
          }}
        >
          <div
            className={`aie-container`}
            style={{ backgroundColor: '#f3f4f6' }}
          >
            <div
              className="aie-header-panel"
              style={{
                ...(showAIChat
                  ? {
                      right: 500,
                    }
                  : {}),
              }}
            >
              <div className="aie-container-header"></div>
            </div>
            <div className="aie-main">
              <div className="aie-directory-content">
                {/* <div className="aie-directory">
                  <div
                    style={{ background: '#fff', padding: 20, marginTop: 18 }}
                  >
                    <DocumentList
                      currentDocId={currentDocId}
                      onDocumentSelect={(docId) => {
                        // 切换文档的时候先保存;
                        saveDocument(editorRef.current?.getHtml() || '');
                        setCurrentDocId(docId);
                        setChangeAction(true);
                      }}
                    />
                  </div>
                </div> */}
              </div>
              <div className="aie-container-panel">
                {currentDocId ? (
                  <div className="aie-container-main"></div>
                ) : (
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'center',
                      alignItems: 'center',
                      height: '100%',
                    }}
                  >
                    <Empty
                      description="暂无文档，请先新建文档"
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                    />
                  </div>
                )}
              </div>
              {currentDocId && (
                <div className="aie-outline" style={{ width: 280 }}>
                  <OutLine editorRef={editorRef} outlineData={outlineData} />
                </div>
              )}
            </div>
            <div className="aie-container-footer"></div>
          </div>
          {showAIChat && (
            <div className="ai-chat-panel">
              <AIChat setShowAIChat={setShowAIChat} ref={aiChatRef} />
            </div>
          )}
        </div>
      </>
    </div>
  );
}

export default App;
