import FilePreview from '@/components/FilePreview';
import PreviewableFileCard from '@/components/PreviewableFileCard';
import useFilePreview from '@/hooks/useFilePreview';
import type { FileItem } from '@/types/common';
import { fetchWithAuthNew, fetchWithAuthStream } from '@/utils/fetch';
import {
  CloudUploadOutlined,
  // PlusCircleOutlined,
  PaperClipOutlined,
  SwapOutlined,
  UserOutlined,
} from '@ant-design/icons';
import type { AttachmentsProps } from '@ant-design/x';
import { Attachments, Bubble, Sender, XProvider, XStream } from '@ant-design/x';
import { history, useLocation } from '@umijs/max';
import { Badge, Button, Flex, GetRef, Select, Typography, message } from 'antd';
import markdownit from 'markdown-it';
import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react';
import { API_BASE_URL } from '../../config';
import InteractiveTree from '../Products/components/InteractiveTree';
import ChatSessionList, { ChatMessage } from './components/ChatSessionList';
import styles from './index.module.less';

const md = markdownit({ html: true, breaks: true });

// 添加日志容器组件，优化滚动功能
const LogContainer = React.memo(({ log }: { log: string }) => {
  const logRef = useRef<HTMLDivElement>(null);

  // 当日志内容变化时滚动到底部
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [log]);

  return (
    <div
      ref={logRef}
      style={{
        marginTop: 10,
        padding: 8,
        background: '#f5f5f5',
        borderRadius: 4,
        maxHeight: 200,
        overflow: 'auto',
        fontSize: 12,
        whiteSpace: 'pre-line',
        fontFamily: 'monospace',
        color: '#333',
      }}
    >
      <div
        style={{
          fontWeight: 'bold',
          marginBottom: 5,
        }}
      >
        执行日志：
      </div>
      {log}
    </div>
  );
});

const MODEL_STORAGE_KEY = 'ai_chat_model';

// 定义模型接口类型
interface Model {
  id: string;
  name: string;
  description: string;
}

// 定义可用的模型类型
type ModelType = string;

// 用于转换消息格式的辅助函数
const createMessage = (
  content: string,
  isUser: boolean,
  files?: FileItem[],
): ChatMessage => ({
  key: Date.now().toString(),
  placement: isUser ? 'end' : 'start',
  content,
  avatarType: isUser ? 'user' : 'assistant',
  files,
});

const DEFAULT_MESSAGE = createMessage('你好，我是你的AI助手', false);

interface AIChatProps {
  setShowAIChat: (show: boolean) => void;
}

interface AIChatRef {
  addSelectedFile: (file: FileItem) => void;
}

// 创建一个包装组件来处理 InteractiveTree 的 ref
const TreeWrapper = forwardRef<
  {
    getTreeData: () => any[];
    getOutlineTitle: () => string;
    getInteractiveTreeData: () => {
      treeData: any[];
      outlineTitle: string;
    };
  },
  {
    outlineId?: string | number;
    readOnly?: boolean;
    onGenerateLongDocument: (currentMessage: ChatMessage) => void;
    currentMessage: ChatMessage;
  }
>(({ outlineId, readOnly, onGenerateLongDocument, currentMessage }, ref) => {
  const handleGenerateDocument = async () => {
    try {
      // 先获取大纲数据
      const outlineResponse = (ref as any)?.current?.getInteractiveTreeData();
      // 调用大纲更新接口
      await fetchWithAuthNew(`/api/v1/writing/outlines/${outlineId}`, {
        method: 'PUT',
        data: {
          outline_id: outlineId,
          title: outlineResponse?.outlineTitle || 'Untitled',
          sub_paragraphs: outlineResponse?.treeData || [],
        },
      });

      // 调用父组件的生成长文档方法
      onGenerateLongDocument(currentMessage);
    } catch (error) {
      console.error('更新大纲失败', error);
      message.error('更新大纲失败');
      // 即使更新失败，也尝试生成长文档
      // onGenerateLongDocument(currentMessage);
    }
  };

  return (
    <>
      <InteractiveTree ref={ref} readOnly={readOnly} outlineId={outlineId} />
      {!readOnly && (
        <Button type="link" size="small" onClick={handleGenerateDocument}>
          基于大纲生成长文档
        </Button>
      )}
    </>
  );
});

const AIChat = forwardRef<AIChatRef, AIChatProps>(({}, ref) => {
  // 获取当前路由信息
  const location = useLocation();

  const [value, setValue] = useState('');
  const [items, setItems] = useState<AttachmentsProps['items']>([]);
  const [open, setOpen] = useState(false);

  // 会话历史相关状态
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  // 会话消息状态，用于存储当前会话的所有消息
  const [messages, setMessages] = useState<ChatMessage[]>([DEFAULT_MESSAGE]);
  // 刷新会话列表的函数
  const [refreshSessionsList, setRefreshSessionsList] = useState<
    (() => void) | null
  >(null);

  const attachmentsRef = React.useRef<GetRef<typeof Attachments>>(null);
  const senderRef = React.useRef<GetRef<typeof Sender>>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const [models, setModels] = useState<Model[]>([]);
  const [selectedModel, setSelectedModel] = useState<ModelType>(() => {
    const savedModel = localStorage.getItem(MODEL_STORAGE_KEY);
    return savedModel || '';
  });
  const [selectedFiles, setSelectedFiles] = useState<FileItem[]>([]);
  const treeWrapperRef = useRef(null);

  // 添加文件预览相关的 hooks
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
    setMessages([DEFAULT_MESSAGE]);
    setSelectedFiles([]);
    setValue('');

    // 更新URL，移除会话ID参数
    history.push('/WritingHistory');
  }, [history]);

  // 添加一个函数来检查是否在底部附近
  const isNearBottom = useCallback(() => {
    if (!scrollContainerRef.current) return false;
    const { scrollTop, scrollHeight, clientHeight } =
      scrollContainerRef.current;
    return scrollHeight - scrollTop - clientHeight < 100;
  }, []);

  // 滚动到底部
  const scrollToBottom = useCallback(
    (isUserMessage: boolean) => {
      if (!scrollContainerRef.current) return;

      // 如果是用户消息，或者已经在底部附近，则滚动到底部
      if (isUserMessage || isNearBottom()) {
        scrollContainerRef.current.scrollTo({
          top: scrollContainerRef.current.scrollHeight,
          behavior: 'smooth',
        });
      }
    },
    [isNearBottom],
  );

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
    // 判断最后一条消息是否是用户发送的
    const isUserMessage =
      messages.length > 0 &&
      messages[messages.length - 1].avatarType === 'user';

    // 使用 requestAnimationFrame 确保在DOM更新后再滚动
    requestAnimationFrame(() => {
      scrollToBottom(isUserMessage);
    });
  }, [messages, scrollToBottom]);

  // 处理会话切换，确保切换会话后也滚动到底部
  const handleSessionChange = useCallback(
    (
      sessionId: string,
      sessionMessages: ChatMessage[],
      update?: {
        isProgressUpdate: boolean;
        taskId: string;
        progress?: number;
        status: string;
        log?: string;
        process_detail_info?: string;
      },
    ) => {
      // 如果收到的是进度更新信息
      if (update && update.isProgressUpdate) {
        // 更新现有消息列表中的任务状态，而不是替换整个消息列表
        setMessages((prevMessages) => {
          // 查找需要更新的任务消息
          const newMessages = [...prevMessages];
          let foundMessage = false;

          // 查找并更新处于processing或pending状态的助手消息
          for (let i = newMessages.length - 1; i >= 0; i--) {
            const msg = newMessages[i];
            if (
              msg.avatarType === 'assistant' &&
              (msg.status === 'processing' || msg.status === 'pending')
            ) {
              // 更新消息的进度信息
              newMessages[i] = {
                ...msg,
                process: update.progress,
                process_detail_info:
                  update.process_detail_info || msg.process_detail_info,
                log: update.log || msg.log,
                status: update.status as any,
              };
              foundMessage = true;
              break;
            }
          }

          // 如果没有找到相应的消息，则添加一个新消息
          if (!foundMessage && sessionMessages.length > 0) {
            newMessages.push(sessionMessages[0]);
          }

          return newMessages;
        });

        // 任务状态更新后滚动到底部
        setTimeout(() => {
          if (scrollContainerRef.current) {
            scrollContainerRef.current.scrollTo({
              top: scrollContainerRef.current.scrollHeight,
              behavior: 'smooth',
            });
          }
        }, 100);
      } else {
        // 正常的会话切换，完全替换消息列表
        setActiveSessionId(sessionId);
        setMessages(sessionMessages);

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
        }, 300);
      }
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

  // 初始化时检查URL中是否有会话ID
  useEffect(() => {
    const query = new URLSearchParams(location.search);
    const sessionIdFromUrl = query.get('id');

    // 如果URL中没有会话ID，且当前有活动会话，则创建新会话
    // 注意：如果URL中没有会话ID，但没有活动会话，则由ChatSessionList组件负责选择第一个会话
    if (!sessionIdFromUrl && activeSessionId !== null) {
      createNewSession();
    }
  }, [location.search, activeSessionId, createNewSession]);

  // 处理生成长文档
  const handleGenerateLongDocument = async (currentMessage: ChatMessage) => {
    try {
      // 添加一条用户消息"请基于大纲生成全文"
      const userMessage = createMessage('请基于大纲生成全文', true);
      setMessages((prev: ChatMessage[]) => [...prev, userMessage]);

      // 发送生成长文档请求
      const response = await fetchWithAuthNew<{
        task_id: string;
        session_id: string;
      }>('/api/v1/writing/content/generate', {
        method: 'POST',
        data: {
          outline_id: currentMessage.outline_id,
          session_id: activeSessionId,
          model_name: localStorage.getItem('ai_chat_model') || '',
          web_search: Boolean(localStorage.getItem('ai_web_search')) || false,
        },
      });

      if (response && 'task_id' in response) {
        // 添加一条新消息表示任务已创建
        const newMessage = createMessage(
          '长文档生成任务已创建，正在处理中...',
          false,
        );

        // 设置任务状态为处理中
        newMessage.status = 'processing';

        setMessages((prev: ChatMessage[]) => [...prev, newMessage]);

        // 更新URL，添加task_id参数，触发轮询
        history.push(
          `/WritingHistory?id=${activeSessionId || ''}&task_id=${
            response.task_id
          }`,
        );
      }
    } catch (error) {
      console.error('生成长文档失败', error);
      message.error('生成长文档失败');
    }
  };

  const handleSubmit = async () => {
    if (!value.trim()) return;

    const userMessage = createMessage(value, true, selectedFiles);
    setMessages((prev: ChatMessage[]) => [...prev, userMessage]);

    // 准备请求数据
    let currentSessionId = activeSessionId;

    // 如果是第一轮对话（没有活动会话ID），先创建会话
    if (!currentSessionId) {
      try {
        // 调用创建会话接口
        const sessionResponse = await fetchWithAuthNew(
          '/api/v1/rag/chat/session',
          {
            method: 'POST',
          },
        );

        if (sessionResponse && sessionResponse.session_id) {
          currentSessionId = sessionResponse.session_id;
          // 设置活动会话ID
          setActiveSessionId(currentSessionId);

          // 更新路由，添加会话ID参数
          history.push(`/WritingHistory?id=${currentSessionId}`);
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

      // 创建一个新的消息对象用于累积内容，不传递文件信息
      const assistantMessage = createMessage('', false); // 不再传递用户消息中的文件信息
      setMessages((prev: ChatMessage[]) => [
        ...prev,
        {
          ...assistantMessage,
          loading: true, // 添加 loading 状态
        },
      ]);

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
              newMessages[newMessages.length - 1] = {
                ...lastMessage,
                content: lastMessage.content + content,
                loading: false, // 收到第一个有效内容时就移除 loading 状态
              };
              return newMessages;
            });
          }
        } catch (error) {}
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
            onSessionChange={handleSessionChange}
            onCreateNewSession={createNewSession}
            activeSessionId={activeSessionId}
            defaultMessage={DEFAULT_MESSAGE}
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
                    messageRender: () => {
                      // 使用 bubble.key 查找对应的消息
                      const currentMessage = messages.find(
                        (msg) => msg.key === bubble.key,
                      );

                      return (
                        <Flex vertical gap="small">
                          {/* 渲染消息内容 */}
                          <Typography
                            style={{
                              display: 'block',
                            }}
                          >
                            <div
                              dangerouslySetInnerHTML={{
                                __html: md.render(String(bubble.content || '')),
                              }}
                            />
                            {/* <div>{currentMessage?.status}</div> */}
                          </Typography>

                          {/* 显示任务状态提示 */}
                          {!isUser && currentMessage?.status && (
                            <div style={{ marginTop: 8 }}>
                              {currentMessage.status === 'pending' ||
                              currentMessage.status === 'processing' ? (
                                <Typography.Text type="secondary">
                                  <span
                                    style={{
                                      color: '#1677ff',
                                      display: 'block',
                                    }}
                                  >
                                    处理中...
                                    {currentMessage.process !== undefined && (
                                      <div style={{ margin: '10px 0' }}>
                                        <div style={{ marginTop: 5 }}>
                                          <div
                                            style={{
                                              width: '100%',
                                              background: '#f0f0f0',
                                              borderRadius: 4,
                                              height: 8,
                                              overflow: 'hidden',
                                            }}
                                          >
                                            <div
                                              style={{
                                                width: `${currentMessage.process}%`,
                                                background: '#1677ff',
                                                height: '100%',
                                                transition: 'width 0.3s',
                                              }}
                                            />
                                          </div>
                                          <div
                                            style={{
                                              marginTop: 5,
                                              fontSize: 12,
                                              color: '#333',
                                              fontWeight: 'bold',
                                            }}
                                          >
                                            {currentMessage.process}% -{' '}
                                            {currentMessage.process_detail_info}
                                          </div>
                                        </div>
                                        {currentMessage.log && (
                                          <LogContainer
                                            log={currentMessage.log}
                                          />
                                        )}
                                      </div>
                                    )}
                                  </span>
                                </Typography.Text>
                              ) : currentMessage.status === 'completed' ? (
                                <Typography.Text type="success">
                                  {currentMessage.content_type === 'outline'
                                    ? '大纲生成完成'
                                    : '全文生成完成'}
                                  {currentMessage.content_type !==
                                    'outline' && (
                                    <Button
                                      type="link"
                                      size="small"
                                      onClick={() => {
                                        //查看结果时 通知外部更新doc
                                        if ((window as any).isIframe) {
                                          window.parent.postMessage(
                                            {
                                              type: 'onUpdateDoc',
                                              value: currentMessage.document_id,
                                            },
                                            '*',
                                          );
                                        }
                                        history.push(
                                          `/EditorPage?document_id=${
                                            currentMessage.document_id
                                          }&pre-id=${new URLSearchParams(
                                            location.search,
                                          ).get('id')}`,
                                        );
                                      }}
                                    >
                                      查看结果
                                    </Button>
                                  )}
                                  {currentMessage.content_type ===
                                    'outline' && (
                                    <TreeWrapper
                                      ref={treeWrapperRef}
                                      outlineId={currentMessage.outline_id}
                                      readOnly={messages.length > 3}
                                      onGenerateLongDocument={
                                        handleGenerateLongDocument
                                      }
                                      currentMessage={currentMessage}
                                    />
                                  )}
                                  {currentMessage.log && (
                                    <LogContainer log={currentMessage.log} />
                                  )}
                                </Typography.Text>
                              ) : currentMessage.status === 'failed' ? (
                                <Typography.Text type="danger">
                                  处理失败: {currentMessage.error || '未知错误'}
                                  {currentMessage.process !== undefined && (
                                    <div style={{ marginTop: 5 }}>
                                      <div>进度: {currentMessage.process}%</div>
                                      {currentMessage.process_detail_info && (
                                        <div>
                                          详情:{' '}
                                          {currentMessage.process_detail_info}
                                        </div>
                                      )}
                                    </div>
                                  )}
                                  {currentMessage.log && (
                                    <LogContainer log={currentMessage.log} />
                                  )}
                                </Typography.Text>
                              ) : null}
                            </div>
                          )}

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
            <div style={{ display: 'none' }}>
              <Sender
                ref={senderRef}
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
                            const fileData = file.response.data[0];
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
                              description: '点击或拖拽文件到此区域上传',
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

        {/* 添加文件预览组件 */}
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
