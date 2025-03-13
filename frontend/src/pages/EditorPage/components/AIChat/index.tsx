import { fetchWithAuthNew, fetchWithAuthStream } from '@/utils/fetch';
import {
  CloseCircleOutlined,
  MinusCircleOutlined,
  PlusCircleOutlined,
  SwapOutlined,
  UserOutlined,
} from '@ant-design/icons';
import type { BubbleProps } from '@ant-design/x';
import { Bubble, Sender, XProvider, XStream } from '@ant-design/x';
import { Button, Flex, Modal, Select, Typography } from 'antd';
import markdownit from 'markdown-it';
import React, {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react';
import KnowledgeBaseList from './components/PersonalKnowledge';
import styles from './index.module.less';

const md = markdownit({ html: true, breaks: true });

// 定义 markdown 渲染函数
const renderMarkdown: BubbleProps['messageRender'] = (content) => (
  <Typography>
    {/* biome-ignore lint/security/noDangerouslySetInnerHtml: used for markdown rendering */}
    <div dangerouslySetInnerHTML={{ __html: md.render(content) }} />
  </Typography>
);

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

interface ChatMessage {
  key: string;
  placement: 'start' | 'end';
  content: string;
  avatarType: 'user' | 'assistant';
}

// 文件列表相关接口定义
interface FileItem {
  file_id: string;
  name: string;
  size: number;
  type: string;
  status: number;
  created_at: string;
}

// 用于转换消息格式的辅助函数
const createMessage = (content: string, isUser: boolean): ChatMessage => ({
  key: Date.now().toString(),
  placement: isUser ? 'end' : 'start',
  content,
  avatarType: isUser ? 'user' : 'assistant',
});

const getAvatarIcon = () => {
  return { icon: <UserOutlined /> };
};

const DEFAULT_MESSAGE = createMessage('你好，我是你的AI助手', false);

interface AIChatProps {
  setShowAIChat: (show: boolean) => void;
}

interface AIChatRef {
  addSelectedFile: (file: FileItem) => void;
}

// 创建一个包装组件来处理 KnowledgeBaseList 的选择变更
const KnowledgeBaseListWrapper: React.FC<{
  onSelectChange: (selectedRowKeys: React.Key[]) => void;
  onSelectFiles: (selectedFiles: any[]) => void;
}> = ({ onSelectChange, onSelectFiles }) => {
  return (
    <KnowledgeBaseList
      onSelectChange={onSelectChange}
      onSelectFiles={onSelectFiles}
    />
  );
};

const AIChat = forwardRef<AIChatRef, AIChatProps>(({ setShowAIChat }, ref) => {
  const [value, setValue] = useState('');
  const [models, setModels] = useState<Model[]>([]);
  const [open, setOpen] = React.useState(false);
  const [selectedModel, setSelectedModel] = useState<ModelType>(() => {
    const savedModel = localStorage.getItem(MODEL_STORAGE_KEY);
    return savedModel || '';
  });
  const [messages, setMessages] = useState(() => {
    const savedMessages = localStorage.getItem(STORAGE_KEY);
    if (savedMessages) {
      return JSON.parse(savedMessages);
    }
    return [DEFAULT_MESSAGE];
  });
  const [loading] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<FileItem[]>([]);
  const [selectedKnowledgeFileIds, setSelectedKnowledgeFileIds] = useState<
    React.Key[]
  >([]);
  const [knowledgeModalVisible, setKnowledgeModalVisible] = useState(false);
  const [selectedKnowledgeFiles, setSelectedKnowledgeFiles] = useState<any[]>(
    [],
  );

  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // 当消息更新时，保存到 localStorage
  useEffect(() => {
    if (
      messages.length === 1 &&
      messages[0].content === DEFAULT_MESSAGE.content
    ) {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
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
          setSelectedModel(response.models[0].name);
          localStorage.setItem(MODEL_STORAGE_KEY, response.models[0].name);
        }
      } catch (error) {
        console.error('获取模型列表失败:', error);
      }
    };
    fetchModels();
  }, []);

  // 添加一个函数来检查是否在底部附近
  const isNearBottom = () => {
    if (!scrollContainerRef.current) return true;
    const { scrollHeight, scrollTop, clientHeight } =
      scrollContainerRef.current;
    return scrollHeight - scrollTop - clientHeight < 100;
  };

  // 智能滚动函数
  const scrollToBottom = (isUserMessage: boolean) => {
    if (!scrollContainerRef.current) return;

    // 如果是用户消息，总是滚动到底部，且立即滚动
    // 如果是系统消息，只在用户本来就在底部时才滚动
    if (isUserMessage || isNearBottom()) {
      scrollContainerRef.current.scrollTo({
        top: scrollContainerRef.current.scrollHeight,
        behavior: isUserMessage ? 'auto' : 'smooth',
      });
    }
  };

  // 监听消息变化
  useEffect(() => {
    // 判断最后一条消息是否是用户发送的
    const isUserMessage =
      messages.length > 0 &&
      messages[messages.length - 1].avatarType === 'user';
    scrollToBottom(isUserMessage);
  }, [messages]);

  const handleSubmit = async () => {
    if (!value.trim()) return;

    const userMessage = createMessage(value, true);
    setMessages((prev: ChatMessage[]) => [...prev, userMessage]);
    // 准备请求数据
    const requestData = {
      model_name: localStorage.getItem(MODEL_STORAGE_KEY) || '',
      doc_id:
        new URLSearchParams(window.location.search).get('document_id') || '',
      file_ids: selectedFiles
        .filter((file) => file.type === 'docx' || file.type === 'pdf')
        .map((file) => file.file_id),
      max_tokens: 2000,
      messages: [
        {
          content: value,
          role: 'user',
        },
      ],
      selected_contents: selectedFiles
        .filter((file) => file.type === 'text')
        .map((file) => file.name),
      stream: true,
      action: 'chat',
      temperature: 0.7,
    };
    setValue('');
    setSelectedFiles([]);
    setOpen(false);
    try {
      const response = await fetchWithAuthStream(
        '/api/v1/completions',
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
      const assistantMessage = createMessage('', false);
      setMessages((prev: ChatMessage[]) => [...prev, assistantMessage]);

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
            // 更新最后一条消息的内容
            setMessages((prev: ChatMessage[]) => {
              const newMessages = [...prev];
              const lastMessage = newMessages[newMessages.length - 1];
              newMessages[newMessages.length - 1] = {
                ...lastMessage,
                content: lastMessage.content + content,
              };
              return newMessages;
            });
          }
        } catch (error) {
          console.error('Error parsing chunk:', error, chunk);
        }
      }
    } catch (error) {
      console.error('Error in stream processing:', error);
      // 在发生错误时添加错误消息
      const errorMessage = createMessage(
        '抱歉，处理您的请求时出现了错误。',
        false,
      );
      setMessages((prev: ChatMessage[]) => [...prev, errorMessage]);
    }
  };

  // 处理消息显示，添加avatar组件和markdown渲染
  const displayMessages = messages.map((msg: ChatMessage) => ({
    ...msg,
    avatar: getAvatarIcon(),
    messageRender: renderMarkdown,
  }));

  // 处理模型变更
  const handleModelChange = (value: ModelType) => {
    setSelectedModel(value);
    localStorage.setItem(MODEL_STORAGE_KEY, value);
  };

  // 处理删除单个文件
  const handleDeleteFile = (fileId: string) => {
    setSelectedFiles((prev) => {
      const newFiles = prev.filter((f) => f.file_id !== fileId);
      if (newFiles.length === 0) {
        setOpen(false);
      }
      return newFiles;
    });
  };

  // 处理知识库文件选择回调
  const handleKnowledgeFileSelect = (selectedRowKeys: React.Key[]) => {
    setSelectedKnowledgeFileIds(selectedRowKeys);
  };

  // 处理知识库文件数据选择回调
  const handleKnowledgeFilesSelect = (selectedFiles: any[]) => {
    setSelectedKnowledgeFiles(selectedFiles);
  };

  // 处理知识库文件选择
  const handleKnowledgeModalOk = () => {
    if (selectedKnowledgeFileIds.length > 0) {
      // 直接使用已选中的文件数据
      const selectedKnowledgeFilesFormatted = selectedKnowledgeFiles.map(
        (file) => ({
          file_id: file.file_id,
          name: file.file_name,
          size: file.file_size,
          type: file.file_name.split('.').pop() || 'unknown',
          status: file.status,
          created_at: file.created_at,
        }),
      );

      setSelectedFiles((prev) => [...prev, ...selectedKnowledgeFilesFormatted]);
      setOpen(true);
    }
    setKnowledgeModalVisible(false);
  };

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

  const headerNode = (
    <Sender.Header
      title="附件"
      open={open}
      onOpenChange={setOpen}
      closable={false}
    >
      <div className={styles.fileList}>
        {loading ? (
          <div className={styles.loading}>加载中...</div>
        ) : selectedFiles.length > 0 ? (
          selectedFiles.map((file) => (
            <div key={file.file_id} className={styles.fileItem}>
              <span className={styles.fileName}>{file.name}</span>
              <span className={styles.fileInfo}>
                <span className={styles.fileSize}>
                  {(file.size / 1024).toFixed(2)}KB
                </span>
                <MinusCircleOutlined
                  className={styles.deleteIcon}
                  onClick={() => handleDeleteFile(file.file_id)}
                />
              </span>
            </div>
          ))
        ) : (
          <div className={styles.emptyText}>请选择文件</div>
        )}
      </div>
    </Sender.Header>
  );

  return (
    <div>
      <XProvider>
        <Flex
          vertical
          justify="space-between"
          style={{
            height: '100vh',
            padding: 20,
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
                  marginRight: 20,
                }}
              >
                AI助手
              </div>
              <Select
                size="small"
                value={handleSelectedModel(selectedModel)}
                onChange={handleModelChange}
                prefix={<SwapOutlined />}
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
            <div>
              <Button
                icon={<CloseCircleOutlined />}
                type="text"
                onClick={() => setShowAIChat(false)}
              />
            </div>
          </Flex>
          <div className={styles.scrollContainer} ref={scrollContainerRef}>
            <Bubble.List items={displayMessages} />
          </div>
          <div>
            <Sender
              header={headerNode}
              value={value}
              prefix={
                <Button
                  type="text"
                  icon={<PlusCircleOutlined style={{ fontSize: 18 }} />}
                  onClick={() => setKnowledgeModalVisible(true)}
                />
              }
              onChange={(nextVal: string) => {
                setValue(nextVal);
              }}
              onSubmit={handleSubmit}
            />

            {/* 添加知识库选择Modal */}
            <Modal
              title="选择个人知识库文件"
              open={knowledgeModalVisible}
              onOk={handleKnowledgeModalOk}
              onCancel={() => setKnowledgeModalVisible(false)}
              width={800}
              destroyOnClose
            >
              <KnowledgeBaseListWrapper
                onSelectChange={handleKnowledgeFileSelect}
                onSelectFiles={handleKnowledgeFilesSelect}
              />
            </Modal>
          </div>
        </Flex>
      </XProvider>
    </div>
  );
});

export default AIChat;
