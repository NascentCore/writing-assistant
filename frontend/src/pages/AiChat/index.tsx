import FilePreview from '@/components/FilePreview';
import PreviewableFileCard from '@/components/PreviewableFileCard';
import ReferenceContentRenderer from '@/components/ReferenceContentRenderer';
import useFilePreview from '@/hooks/useFilePreview';
import type { FileItem } from '@/types/common';
import { fetchWithAuthNew, fetchWithAuthStream } from '@/utils/fetch';
import {
  CloudUploadOutlined,
  CopyOutlined,
  PaperClipOutlined,
  QuestionCircleOutlined,
  SwapOutlined,
  UserOutlined,
} from '@ant-design/icons';
import type { AttachmentsProps } from '@ant-design/x';
import { Attachments, Bubble, Sender, XProvider, XStream } from '@ant-design/x';
import { history, useLocation } from '@umijs/max';
import {
  Badge,
  Button,
  Flex,
  GetRef,
  message,
  Select,
  Switch,
  Tooltip,
  Typography,
} from 'antd';
import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react';
import { CopyToClipboard } from 'react-copy-to-clipboard';
import { API_BASE_URL } from '../../config';
import ChatSessionList, {
  type ChatSessionListRef,
} from './components/ChatSessionList';
import styles from './index.module.less';
import {
  type AIChatProps,
  type AIChatRef,
  type ChatMessage,
  type Model,
} from './type';

// 扩展ChatMessage接口以添加reference_files属性
declare module './components/ChatSessionList' {
  interface ChatMessage {
    reference_files?: {
      file_id: string;
      file_name: string;
      file_path: string;
      file_ext: string;
      file_size: number;
      content: string;
    }[];
  }
}

const MODEL_STORAGE_KEY = 'ai_chat_model';
const SESSION_STORAGE_KEY = 'current_chat_session_id';
const ENHANCED_SEARCH_STORAGE_KEY = 'ai_chat_enhanced_search';

// 定义可用的模型类型
type ModelType = string;

// 添加一个消息计数器
let messageCounter = 0;

// 用于转换消息格式的辅助函数
const createMessage = (
  content: string,
  isUser: boolean,
  files?: FileItem[],
): ChatMessage => ({
  key: `${Date.now()}-${messageCounter++}`,
  placement: isUser ? 'end' : 'start',
  content,
  avatarType: isUser ? 'user' : 'assistant',
  files,
});

const AIChat = forwardRef<AIChatRef, AIChatProps>((props, ref) => {
  // 获取当前路由信息
  const location = useLocation();

  const [value, setValue] = useState<string | undefined>(undefined);
  const [items, setItems] = useState<AttachmentsProps['items']>([]);
  const [open, setOpen] = useState(false);

  // 会话历史相关状态
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  // 根据 URL 参数初始化消息状态
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // 刷新会话列表的函数
  const [refreshSessionsList, setRefreshSessionsList] = useState<
    (() => void) | null
  >(null);

  const attachmentsRef = React.useRef<GetRef<typeof Attachments>>(null);
  const senderRef = React.useRef<GetRef<typeof Sender>>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const chatSessionListRef = useRef<ChatSessionListRef>(null);

  const [models, setModels] = useState<Model[]>([]);
  const [selectedModel, setSelectedModel] = useState<ModelType>(() => {
    const savedModel = localStorage.getItem(MODEL_STORAGE_KEY);
    return savedModel || '';
  });
  const [enhancedSearch, setEnhancedSearch] = useState<boolean>(() => {
    const savedEnhancedSearch = localStorage.getItem(
      ENHANCED_SEARCH_STORAGE_KEY,
    );
    return savedEnhancedSearch === 'true';
  });
  const [selectedFiles, setSelectedFiles] = useState<FileItem[]>([]);

  // 在组件内部添加文件预览相关的 hooks
  const { previewState, showPreview, hidePreview, fetchPreviewFile } =
    useFilePreview();

  // 获取模型列表
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const response = await fetchWithAuthNew('/api/v1/models');
        setModels(response.models);
        // 如果没有选中的模型，默认选择第一个
        if (!selectedModel && response.models.length > 0) {
          setSelectedModel(response.models[0].name);
          localStorage.setItem(MODEL_STORAGE_KEY, response.models[0].name);
        }
      } catch (error) {}
    };
    fetchModels();
  }, []);

  // 创建新会话
  const createNewSession = useCallback(() => {
    setActiveSessionId(null);
    setMessages([]);
    setSelectedFiles([]);
    setValue('');

    // 清除localStorage中保存的会话ID
    localStorage.removeItem(SESSION_STORAGE_KEY);

    // 清除 URL 中的会话 ID 参数
    history.push(location.pathname);
  }, []);

  const scrollToBottom = useCallback(() => {
    if (!scrollContainerRef.current) return;

    // 使用 setTimeout 确保在下一个宏任务中执行滚动，给予足够时间让内容渲染
    setTimeout(() => {
      if (scrollContainerRef.current) {
        scrollContainerRef.current.scrollTo({
          top: scrollContainerRef.current.scrollHeight,
          behavior: 'smooth',
        });
      }
    }, 100);
  }, []);

  // 页面首次加载时滚动到底部
  useEffect(() => {
    // 使用 requestAnimationFrame 确保在DOM完全渲染后再滚动
    const scrollToBottomImmediately = () => {
      if (scrollContainerRef.current) {
        scrollContainerRef.current.scrollTo({
          top: scrollContainerRef.current.scrollHeight,
          behavior: 'auto', // 使用 'auto' 而不是 'smooth' 以实现瞬间滚动
        });
      }
    };

    // 立即执行一次
    scrollToBottomImmediately();

    // 再次使用 requestAnimationFrame 确保在下一帧渲染后也执行滚动
    // 这有助于解决某些情况下内容高度计算不准确的问题
    requestAnimationFrame(() => {
      requestAnimationFrame(scrollToBottomImmediately);
    });

    // 添加 resize 事件监听器，在窗口大小变化时也滚动到底部
    const handleResize = () => {
      scrollToBottomImmediately();
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  // 监听消息变化
  useEffect(() => {
    // 使用 requestAnimationFrame 确保在DOM更新后再滚动
    requestAnimationFrame(() => {
      scrollToBottom();
    });
  }, [messages, scrollToBottom]);

  // 处理会话切换，确保切换会话后也滚动到底部
  const handleSessionChange = useCallback(
    (sessionId: string, sessionMessages: ChatMessage[]) => {
      setActiveSessionId(sessionId);
      setMessages(sessionMessages);

      // 保存当前会话ID到localStorage
      localStorage.setItem(SESSION_STORAGE_KEY, sessionId);

      // 使用 requestAnimationFrame 确保在DOM更新后再滚动
      // 延迟稍微长一点，确保内容已完全渲染
      setTimeout(() => {
        requestAnimationFrame(() => {
          if (scrollContainerRef.current) {
            scrollContainerRef.current.scrollTo({
              top: scrollContainerRef.current.scrollHeight,
              behavior: 'auto', // 使用 'auto' 实现瞬间滚动
            });
          }
        });
      }, 100);
    },
    [scrollToBottom],
  );

  // 计算要显示的消息
  const displayMessages = messages.map((msg) => {
    return {
      ...msg,
      files: msg.files, // 直接传递files属性给messageRender函数
      loading: msg.loading, // 确保 loading 属性被传递给 Bubble 组件
    };
  });

  // 处理模型变更
  const handleModelChange = (value: ModelType) => {
    setSelectedModel(value);
    localStorage.setItem(MODEL_STORAGE_KEY, value);
  };

  // 处理精确查找开关变更
  const handleEnhancedSearchChange = (checked: boolean) => {
    setEnhancedSearch(checked);
    localStorage.setItem(ENHANCED_SEARCH_STORAGE_KEY, String(checked));
  };

  // 处理会话列表刷新
  const handleRefreshSessions = useCallback((refreshFn: () => void) => {
    setRefreshSessionsList(() => refreshFn);
  }, []);

  // 暴露添加文件的方法
  useImperativeHandle(ref, () => ({
    addSelectedFile: (file: FileItem) => {
      setSelectedFiles((prev) => {
        const newFiles = [...prev, file];
        setOpen(true);
        return newFiles;
      });
    },
  }));

  // 处理 URL 参数变化
  useEffect(() => {
    const query = new URLSearchParams(location.search);
    const sessionIdFromUrl = query.get('id');

    // 如果 URL 中没有会话 ID，则创建新会话
    if (!sessionIdFromUrl && activeSessionId !== null) {
      createNewSession();
    }

    // 不在这里处理会话 ID 存在的情况，由 ChatSessionList 组件负责
  }, [location.search, activeSessionId, createNewSession]);

  // 初始化时检查localStorage中是否有保存的会话ID
  useEffect(() => {
    const query = new URLSearchParams(location.search);
    const sessionIdFromUrl = query.get('id');

    // 如果URL中没有会话ID，但localStorage中有保存的会话ID
    if (!sessionIdFromUrl && !activeSessionId) {
      const savedSessionId = localStorage.getItem(SESSION_STORAGE_KEY);
      if (savedSessionId) {
        // 更新URL，添加会话ID参数
        // history.push(`${location.pathname}?id=${savedSessionId}`);
        // 更新路由，添加会话ID参数
        const query = new URLSearchParams(location.search);
        query.set('id', savedSessionId);
        history.push(`${location.pathname}?${query.toString()}`);
      }
    }
  }, [location.search, activeSessionId, history]);

  const handleSubmit = async () => {
    if (!value || !value.trim()) return;

    const userMessage = createMessage(value, true, selectedFiles);
    setMessages((prev: ChatMessage[]) => [...prev, userMessage]);

    // 准备请求数据
    let currentSessionId = activeSessionId;

    // 创建一个带有loading状态的助手消息
    const assistantMessage = createMessage('', false);
    setMessages((prev: ChatMessage[]) => [
      ...prev,
      { ...assistantMessage, loading: true },
    ]);

    // 在插入loading消息后立即滚动到底部
    requestAnimationFrame(() => {
      if (scrollContainerRef.current) {
        scrollContainerRef.current.scrollTo({
          top: scrollContainerRef.current.scrollHeight,
          behavior: 'smooth',
        });
      }
    });

    // 如果是第一轮对话（没有活动会话ID），先创建会话
    if (!currentSessionId) {
      try {
        // 调用创建会话接口
        const sessionResponse = await fetchWithAuthNew(
          '/api/v1/rag/chat/session',
          {
            method: 'POST',
            data: {},
          },
        );

        if (sessionResponse && sessionResponse.session_id) {
          currentSessionId = sessionResponse.session_id;
          // 设置活动会话ID
          setActiveSessionId(currentSessionId);

          // 保存会话ID到localStorage
          if (currentSessionId) {
            localStorage.setItem(SESSION_STORAGE_KEY, currentSessionId);
          }

          // 更新路由，添加会话ID参数
          // history.push(`${location.pathname}?id=${currentSessionId}`);
          // 更新路由，添加会话ID参数
          const query = new URLSearchParams(location.search);
          query.set('id', currentSessionId!);
          history.push(`${location.pathname}?${query.toString()}`);
        }
      } catch (error) {
        console.error('创建会话失败:', error);
        message.error('创建会话失败');
      }
    }

    // 构建请求数据对象
    const requestData: {
      model_name: string;
      file_ids: string[];
      question: string;
      stream: boolean;
      enhanced_search: boolean;
      session_id?: string;
      files?: {
        file_id: string;
        name: string;
        size: number;
        type: string;
        status: number;
        created_at: string;
      }[];
    } = {
      model_name: localStorage.getItem(MODEL_STORAGE_KEY) || '',
      file_ids: selectedFiles
        .filter(
          (file) =>
            file.type === 'docx' || file.type === 'pdf' || file.type === 'doc',
        )
        .map((file) => file.file_id),
      question: value,
      stream: true,
      enhanced_search: enhancedSearch,
      // 添加 messages 字段，包含当前消息和关联的文件信息
      files: selectedFiles.length > 0 ? selectedFiles : undefined,
    };

    // 只有当 currentSessionId 不为 null 时才添加到请求数据中
    if (currentSessionId) {
      requestData.session_id = currentSessionId;
    }
    setValue('');
    setOpen(false);
    try {
      const response = await fetchWithAuthStream(
        '/api/v1/rag/chat',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestData),
        },
        true,
      );

      if (!response.ok || !response.body) {
        throw new Error('Stream response not available');
      }

      // 使用 XStream 处理流式响应
      for await (const chunk of XStream({
        readableStream: response.body,
      })) {
        try {
          // 如果 chunk.data 是字符串，需要解析它
          let data;
          if (typeof chunk.data === 'string') {
            data = JSON.parse(chunk.data);
          } else {
            data = chunk.data;
          }

          if (data.choices?.[0]?.delta?.content) {
            const content = data.choices[0].delta.content;
            // 更新最后一条消息的内容，不保留文件信息
            setMessages((prev: ChatMessage[]) => {
              const newMessages = [...prev];
              const lastMessage = newMessages[newMessages.length - 1];
              // 确保 lastMessage 存在
              if (!lastMessage) return newMessages;

              newMessages[newMessages.length - 1] = {
                ...lastMessage,
                content: lastMessage.content + content,
                loading: false, // 收到第一个有效内容时就移除 loading 状态
              };
              return newMessages;
            });

            // 使用 setTimeout 延迟滚动，确保内容已渲染
            setTimeout(() => {
              if (scrollContainerRef.current) {
                scrollContainerRef.current.scrollTo({
                  top: scrollContainerRef.current.scrollHeight,
                  behavior: 'smooth',
                });
              }
            }, 100);
          }
        } catch (error) {}
      }
      if (currentSessionId && chatSessionListRef.current) {
        await chatSessionListRef.current.loadSessionDetail(currentSessionId);
      }
      // 确保在流处理结束后，如果消息仍然处于 loading 状态，则移除该状态
      setMessages((prev: ChatMessage[]) => {
        const newMessages = [...prev];
        const lastMessage = newMessages[newMessages.length - 1];
        // 如果最后一条消息仍然处于 loading 状态，则移除该状态
        if (lastMessage && lastMessage.loading) {
          newMessages[newMessages.length - 1] = {
            ...lastMessage,
            loading: false,
            // 如果内容为空，添加一个提示信息
            content: lastMessage.content || '未收到有效回复',
          };
        }
        return newMessages;
      });

      // 消息发送完成后再清空选中的文件
      setSelectedFiles([]);
      setItems([]);

      // 刷新会话列表
      if (refreshSessionsList) {
        refreshSessionsList();
      }
    } catch (error) {
      // 在发生错误时添加错误消息，不包含文件信息
      const errorMessage = createMessage(
        '抱歉，处理您的请求时出现了错误。',
        false,
      );
      setMessages((prev: ChatMessage[]) => {
        // 先移除最后一条带有 loading 状态的消息（如果存在）
        const newMessages = [...prev];
        if (
          newMessages.length > 0 &&
          newMessages[newMessages.length - 1].loading
        ) {
          newMessages.pop();
        }
        // 添加错误消息
        return [...newMessages, errorMessage];
      });
      // 发生错误时也清空选中的文件
      setSelectedFiles([]);
      setItems([]);
    }
  };

  const handleSelectedModel = (selectedModel: string) => {
    if (models.length === 0) {
      return '';
    }

    // 判断下selectedModel是否在models中
    const model = models.find((model) => model.name === selectedModel);
    if (model) {
      return selectedModel;
    }
    return models[0].name;
  };

  return (
    <div className={styles.container}>
      <XProvider>
        <Flex gap={20} style={{ height: 'calc(100vh - 60px)' }}>
          {/* 使用 ChatSessionList 组件 */}
          <ChatSessionList
            ref={chatSessionListRef} // 传递 ref
            onSessionChange={handleSessionChange}
            onCreateNewSession={createNewSession}
            activeSessionId={activeSessionId}
            defaultMessage={createMessage('你好，我是你的AI助手', false)}
            refreshSessions={handleRefreshSessions}
          />

          {/* 右侧聊天区域 */}
          <Flex
            vertical
            justify="space-between"
            style={{
              flex: 1,
              height: '100%',
            }}
            gap={8}
          >
            <Flex
              justify="space-between"
              align="center"
              style={{
                padding: '12px 16px',
                backgroundColor: '#fff',
                borderBottom: '1px solid rgba(229, 231, 235, 0.8)',
                position: 'sticky',
                top: 0,
                zIndex: 10,
                backdropFilter: 'blur(8px)',
                WebkitBackdropFilter: 'blur(8px)',
                marginBottom: 12,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <div
                  style={{
                    fontSize: '16px',
                    fontWeight: 500,
                    marginTop: -7,
                  }}
                >
                  模型：
                </div>
                <Select
                  size="small"
                  value={handleSelectedModel(selectedModel)}
                  onChange={handleModelChange}
                  popupMatchSelectWidth={false}
                  prefix={<SwapOutlined />}
                  style={{ marginBottom: 8 }}
                >
                  {models.map((model) => (
                    <Select.Option
                      key={model.id}
                      value={model.name}
                      title={model.description}
                    >
                      {model.name}
                    </Select.Option>
                  ))}
                </Select>
                <div
                  style={{
                    fontSize: '16px',
                    fontWeight: 500,
                    marginTop: -7,
                    marginLeft: 16,
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  精确查找
                  <Tooltip title="如需借助 AI 对文件内容进行总结，可随时开启该功能。此举能够提升总结精度，不过相应地，会增加处理耗时">
                    <QuestionCircleOutlined style={{ marginLeft: 4 }} />
                  </Tooltip>
                  ：
                </div>
                <Switch
                  checked={enhancedSearch}
                  onChange={handleEnhancedSearchChange}
                  style={{ marginLeft: 8, marginTop: -7 }}
                />
              </div>
            </Flex>
            <div className={styles.scrollContainer} ref={scrollContainerRef}>
              <Bubble.List
                items={displayMessages.map((msg) => ({
                  ...msg,
                  role: msg.avatarType === 'user' ? 'user' : 'assistant',
                }))}
                roles={(bubble) => {
                  // 根据 bubble 的 role 返回不同的配置
                  const isUser = bubble.role === 'user';

                  return {
                    placement: isUser ? 'end' : 'start',
                    avatar: {
                      icon: <UserOutlined />,
                      style: { background: isUser ? '#87d068' : '#fde3cf' },
                    },
                    // 为 assistant 角色添加 footer，包含复制按钮
                    footer:
                      !isUser && bubble.content ? (
                        <Flex justify="flex-end">
                          <CopyToClipboard
                            text={String(bubble.content || '')}
                            onCopy={() => message.success('复制成功')}
                          >
                            <Button
                              type="text"
                              size="small"
                              icon={<CopyOutlined />}
                            >
                              复制
                            </Button>
                          </CopyToClipboard>
                        </Flex>
                      ) : undefined,
                    messageRender: () => {
                      // 找到对应的消息
                      const currentMessage = messages.find(
                        (msg) => msg.key === bubble.key,
                      );

                      return (
                        <Flex vertical gap="small">
                          {/* 渲染消息内容 */}
                          <Typography>
                            <ReferenceContentRenderer
                              content={String(bubble.content || '')}
                              referenceFiles={currentMessage?.reference_files}
                            />
                          </Typography>

                          {/* 只在用户消息中渲染关联文件 */}
                          {isUser &&
                            currentMessage?.files &&
                            currentMessage.files.length > 0 && (
                              <Flex
                                vertical
                                gap="small"
                                style={{
                                  marginTop: 8,
                                  background: '#f5f5f5',
                                  padding: 8,
                                  borderRadius: 4,
                                }}
                              >
                                <Typography.Text type="secondary">
                                  关联文件：
                                </Typography.Text>
                                <Flex wrap="wrap" gap="small">
                                  {currentMessage.files.map((file) => (
                                    <PreviewableFileCard
                                      key={file.file_id}
                                      file={file}
                                      onPreview={showPreview}
                                    />
                                  ))}
                                </Flex>
                              </Flex>
                            )}
                        </Flex>
                      );
                    },
                  };
                }}
              />
            </div>
            <div>
              <Sender
                ref={senderRef}
                placeholder="给AI助手发送消息"
                style={{
                  marginTop: 12,
                }}
                header={
                  <Sender.Header
                    title="附件"
                    open={open}
                    onOpenChange={setOpen}
                    styles={{
                      content: {
                        padding: 0,
                      },
                    }}
                    forceRender
                  >
                    <Attachments
                      accept=".doc,.docx,.pdf"
                      multiple
                      ref={attachmentsRef}
                      beforeUpload={() => true}
                      customRequest={({
                        file,
                        onSuccess,
                        onError,
                        onProgress,
                      }) => {
                        const formData = new FormData();
                        formData.append('files', file);
                        const xhr = new XMLHttpRequest();
                        xhr.open(
                          'POST',
                          `${API_BASE_URL}/api/v1/rag/attachments`,
                        );
                        xhr.setRequestHeader(
                          'authorization',
                          `Bearer ${localStorage.getItem('token')}`,
                        );

                        // 添加进度监听
                        xhr.upload.onprogress = (event) => {
                          if (event.lengthComputable) {
                            const percent = Math.round(
                              (event.loaded / event.total) * 100,
                            );
                            onProgress?.({ percent });
                          }
                        };

                        xhr.onload = () => {
                          if (xhr.status === 200) {
                            try {
                              const response = JSON.parse(xhr.responseText);
                              if (response.code !== 200) {
                                onError?.(new Error('上传失败'));
                                message.error(`${response.message}`);
                                return;
                              }
                              onSuccess?.(response);
                            } catch (e) {
                              onError?.(new Error('解析响应失败'));
                            }
                          } else {
                            onError?.(new Error('上传失败'));
                          }
                        };
                        xhr.onerror = () => {
                          onError?.(new Error('网络错误'));
                        };
                        xhr.send(formData);
                      }}
                      items={items}
                      onChange={({ fileList }) => {
                        setItems(fileList);

                        // 更新 selectedFiles，移除已经不在 fileList 中的文件
                        setSelectedFiles((prev) =>
                          prev.filter((file) =>
                            fileList.some(
                              (f) =>
                                f.response?.data?.[0]?.file_id === file.file_id,
                            ),
                          ),
                        );

                        // 当文件列表为空时，自动关闭 Header
                        if (fileList.length === 0) {
                          setOpen(false);
                        }

                        // 处理新完成上传的文件
                        const completedFiles = fileList
                          .filter((file) => {
                            return (
                              file.status === 'done' &&
                              file.response?.code === 200
                            );
                          })
                          .map((file) => {
                            const fileData = file.response.data?.[0];
                            return {
                              file_id: fileData.file_id,
                              name: fileData.name || file.name,
                              size: fileData.size || file.size || 0,
                              type: fileData.content_type || '',
                              status: 1,
                              created_at: new Date().toISOString(),
                              percent: 100,
                            };
                          });

                        if (completedFiles.length > 0) {
                          // 更新 selectedFiles，但要避免重复添加
                          setSelectedFiles((prev) => {
                            const existingIds = new Set(
                              prev.map((f) => f.file_id),
                            );
                            const newFiles = completedFiles.filter(
                              (f) => !existingIds.has(f.file_id),
                            );
                            // 如果有新文件上传完成，自动打开 Header
                            if (newFiles.length > 0) {
                              setOpen(true);
                            }
                            return [...prev, ...newFiles];
                          });
                        }
                      }}
                      placeholder={(type) =>
                        type === 'drop'
                          ? {
                              title: '拖拽文件到这里',
                            }
                          : {
                              icon: <CloudUploadOutlined />,
                              title: '上传文件',
                              description: (
                                <div>
                                  <div>
                                    点击或拖拽文件到此区域上传，此处仅上传背景资料，字数不宜超过2000字
                                  </div>
                                  <div>
                                    相关参考文件提前上传至个人知识库并自动解析
                                  </div>
                                </div>
                              ),
                            }
                      }
                      getDropContainer={() => senderRef.current?.nativeElement}
                    />
                  </Sender.Header>
                }
                value={value}
                prefix={
                  <Badge dot={!open && selectedFiles.length > 0}>
                    <Button
                      icon={<PaperClipOutlined style={{ fontSize: 18 }} />}
                      onClick={() => setOpen(!open)}
                    />
                  </Badge>
                }
                onChange={(nextVal: string) => {
                  setValue(nextVal);
                }}
                onPasteFile={(file) => {
                  attachmentsRef.current?.upload(file);
                  setOpen(true);
                }}
                onSubmit={handleSubmit}
              />
            </div>
          </Flex>
        </Flex>
        <FilePreview
          open={previewState.visible}
          onCancel={hidePreview}
          fileName={previewState.fileName}
          fetchFile={fetchPreviewFile}
        />
      </XProvider>
    </div>
  );
});

export default AIChat;
