import { fetchWithAuthNew, fetchWithAuthStream } from '@/utils/fetch';
import {
  CloudUploadOutlined,
  // PlusCircleOutlined,
  PaperClipOutlined,
  SwapOutlined,
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
import ChatSessionList, { ChatMessage } from './components/ChatSessionList';
import styles from './index.module.less';

const md = markdownit({ html: true, breaks: true });

// 定义消息渲染函数
const messageRender = (
  content: string,
  props?: Record<string, unknown>,
): React.ReactNode => {
  const message = props?.['data-message'] as ChatMessage;
  return (
    <Flex vertical gap="small">
      {/* 渲染消息内容 */}
      <Typography>
        <div dangerouslySetInnerHTML={{ __html: md.render(content) }} />
      </Typography>

      {/* 渲染关联文件 */}
      {message?.files && message.files.length > 0 && (
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
          <Typography.Text type="secondary">关联文件：</Typography.Text>
          <Flex wrap="wrap" gap="small">
            {message.files.map((file) => (
              <Attachments.FileCard
                key={file.file_id}
                item={{
                  uid: file.file_id,
                  name: file.name,
                  size: file.size,
                  type: file.type,
                  status: 'done',
                }}
              />
            ))}
          </Flex>
        </Flex>
      )}
    </Flex>
  );
};

const STORAGE_KEY = 'ai_chat_messages';
const MODEL_STORAGE_KEY = 'ai_chat_model';

// 定义模型接口类型
interface Model {
  id: string;
  name: string;
  description: string;
}

// 定义可用的模型类型
type ModelType = string;

interface FileItem {
  file_id: string;
  name: string;
  size: number;
  type: string;
  status: number;
  created_at: string;
}

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

  // 当消息更新时，保存到 localStorage
  useEffect(() => {
    if (
      messages.length === 1 &&
      messages[0].content === DEFAULT_MESSAGE.content
    ) {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      // 确保消息中的文件信息也被保存
      const messagesToSave = messages.map((msg: ChatMessage) => ({
        ...msg,
        files: msg.files || [], // 确保 files 字段存在
      }));
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messagesToSave));
    }
  }, [messages]);

  // 获取模型列表
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const response = await fetchWithAuthNew('/api/v1/models');
        setModels(response.models);
        // 如果没有选中的模型，默认选择第一个
        if (!selectedModel && response.models.length > 0) {
          setSelectedModel(response.models[0].id);
          localStorage.setItem(MODEL_STORAGE_KEY, response.models[0].id);
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

    // 清除 URL 中的会话 ID 参数
    history.push('/AiChat');
  }, []);

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

  // 处理会话切换
  const handleSessionChange = useCallback(
    (sessionId: string, sessionMessages: ChatMessage[]) => {
      setActiveSessionId(sessionId);
      setMessages(sessionMessages);

      // 滚动到底部
      setTimeout(() => {
        scrollToBottom(false);
      }, 100);
    },
    [scrollToBottom],
  );

  // 计算要显示的消息
  const displayMessages = messages.map((msg) => ({
    ...msg,
    render: messageRender,
    'data-message': msg, // 传递消息对象给渲染函数
    loading: msg.loading, // 确保 loading 属性被传递给 Bubble 组件
  }));

  // 处理模型变更
  const handleModelChange = (value: ModelType) => {
    setSelectedModel(value);
    localStorage.setItem(MODEL_STORAGE_KEY, value);
  };

  // 处理会话列表刷新
  const handleRefreshSessions = useCallback((refreshFn: () => void) => {
    setRefreshSessionsList(() => refreshFn);
  }, []);

  const headerNode = (
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
        customRequest={({ file, onSuccess, onError, onProgress }) => {
          const formData = new FormData();
          formData.append('files', file);
          const xhr = new XMLHttpRequest();
          xhr.open('POST', `${API_BASE_URL}/api/v1/rag/files?category=user`);
          xhr.setRequestHeader(
            'authorization',
            `Bearer ${localStorage.getItem('token')}`,
          );

          // 添加进度监听
          xhr.upload.onprogress = (event) => {
            if (event.lengthComputable) {
              const percent = Math.round((event.loaded / event.total) * 100);
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
                (f) => f.response?.data?.[0]?.file_id === file.file_id,
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
                file.response?.code === 200 &&
                file.response?.data?.[0]
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
              const existingIds = new Set(prev.map((f) => f.file_id));
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
  );

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

  // 页面首次加载时滚动到底部
  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTo({
        top: scrollContainerRef.current.scrollHeight,
        behavior: 'auto',
      });
    }
  }, []);

  // 监听消息变化
  useEffect(() => {
    // 判断最后一条消息是否是用户发送的
    const isUserMessage =
      messages.length > 0 &&
      messages[messages.length - 1].avatarType === 'user';
    scrollToBottom(isUserMessage);
  }, [messages]);

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
          // 使用非空断言，因为我们已经检查了 sessionResponse.session_id 存在
          const sessionIdWithoutPrefix = currentSessionId!.replace('chat-', '');
          history.push(`/AiChat?id=${sessionIdWithoutPrefix}`);
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

      // 创建一个新的消息对象用于累积内容
      const assistantMessage = createMessage('', false, []); // 明确指定空文件数组
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
            // 更新最后一条消息的内容，保持文件信息不变
            setMessages((prev: ChatMessage[]) => {
              const newMessages = [...prev];
              const lastMessage = newMessages[newMessages.length - 1];
              newMessages[newMessages.length - 1] = {
                ...lastMessage,
                content: lastMessage.content + content,
                files: lastMessage.files || [], // 保持文件信息
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
      // 在发生错误时添加错误消息
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
                  value={selectedModel}
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
              <Bubble.List items={displayMessages} />
            </div>
            <div>
              <Sender
                ref={senderRef}
                style={{
                  marginTop: 12,
                }}
                header={headerNode}
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
      </XProvider>
    </div>
  );
});

export default AIChat;
