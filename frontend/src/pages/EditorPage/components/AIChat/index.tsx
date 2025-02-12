import { fetchWithAuthNew } from '@/utils/fetch';
import {
  CloseCircleOutlined,
  DeleteOutlined,
  PlusCircleOutlined,
  SwapOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Bubble, Sender, XProvider } from '@ant-design/x';
import { Button, Dropdown, Flex, MenuProps, Select } from 'antd';
import React, { useEffect, useRef, useState } from 'react';
import styles from './index.module.less';

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

const AIChat: React.FC<AIChatProps> = ({ setShowAIChat }) => {
  const [value, setValue] = useState('');
  const [resetKey, setResetKey] = useState(0); // 添加重置键
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
          setSelectedModel(response.models[0].id);
          localStorage.setItem(MODEL_STORAGE_KEY, response.models[0].id);
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

  const handleSubmit = () => {
    if (!value.trim()) return;

    const userMessage = createMessage(value, true);
    setMessages((prev: ChatMessage[]) => [...prev, userMessage]);
    setValue('');

    // 模拟自动回复
    setTimeout(() => {
      const systemResponse = createMessage('收到消息', false);
      setMessages((prev: ChatMessage[]) => [...prev, systemResponse]);
    }, 500);
  };

  const handleClearChat = () => {
    localStorage.removeItem(STORAGE_KEY);
    setMessages([DEFAULT_MESSAGE]);
    setResetKey((prev) => prev + 1); // 强制重置组件状态
  };

  // 处理消息显示，添加avatar组件
  const displayMessages = messages.map((msg: ChatMessage) => ({
    ...msg,
    avatar: getAvatarIcon(),
  }));

  // 处理模型变更
  const handleModelChange = (value: ModelType) => {
    setSelectedModel(value);
    localStorage.setItem(MODEL_STORAGE_KEY, value);
  };

  // 可以用于滚动的懒加载
  // useEffect(() => {
  //   // 添加滚动事件处理
  //   const handleScroll = (e: WheelEvent) => {
  //     // 类型断言可能不安全，让我们添加类型检查
  //     const target = e.currentTarget;
  //     if (!(target instanceof HTMLElement)) return;

  //     const isAtTop = target.scrollTop === 0;
  //     const isAtBottom =
  //       Math.abs(target.scrollHeight - target.scrollTop - target.clientHeight) <
  //       1;

  //     // 只在到达边界且继续往对应方向滚动时阻止
  //     if ((isAtTop && e.deltaY < 0) || (isAtBottom && e.deltaY > 0)) {
  //       e.preventDefault();
  //       e.stopPropagation();
  //     }
  //   };

  //   // 找到滚动容器并添加事件监听
  //   const scrollContainer = document.querySelector<HTMLElement>(
  //     `.${styles.scrollContainer}`,
  //   );
  //   if (scrollContainer) {
  //     scrollContainer.addEventListener('wheel', handleScroll, {
  //       passive: false,
  //     });
  //   }

  //   // 清理函数
  //   return () => {
  //     if (scrollContainer) {
  //       scrollContainer.removeEventListener('wheel', handleScroll);
  //     }
  //   };
  // }, []);
  const headerNode = (
    <Sender.Header
      title="附件"
      open={open}
      onOpenChange={setOpen}
      closable={false}
    >
      <div>1111</div>
    </Sender.Header>
  );
  const items: MenuProps['items'] = [
    {
      key: '1',
      label: (
        <a
          target="_blank"
          rel="noopener noreferrer"
          href="https://www.antgroup.com"
        >
          1st menu item
        </a>
      ),
    },
    {
      key: '2',
      label: (
        <a
          target="_blank"
          rel="noopener noreferrer"
          href="https://www.aliyun.com"
        >
          2nd menu item
        </a>
      ),
    },
    {
      key: '3',
      label: (
        <a
          target="_blank"
          rel="noopener noreferrer"
          href="https://www.luohanacademy.com"
        >
          3rd menu item
        </a>
      ),
    },
  ];
  return (
    <div key={resetKey}>
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
                  marginTop: -7,
                }}
              >
                AI助手
              </div>
              <Select
                size="small"
                value={selectedModel}
                onChange={handleModelChange}
                prefix={<SwapOutlined />}
                style={{ width: 120, marginBottom: 8 }}
              >
                {models.map((model) => (
                  <Select.Option
                    key={model.id}
                    value={model.id}
                    title={model.description}
                  >
                    {model.name}
                  </Select.Option>
                ))}
              </Select>
            </div>
            <div>
              <Button
                icon={<DeleteOutlined />}
                type="text"
                onClick={handleClearChat}
              />
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
                <Dropdown menu={{ items }} trigger={['click']} placement="top">
                  <Button
                    type="text"
                    icon={<PlusCircleOutlined style={{ fontSize: 18 }} />}
                    // onClick={() => {
                    //   setOpen(!open);
                    // }}
                  />
                </Dropdown>
              }
              onChange={(nextVal: string) => {
                setValue(nextVal);
              }}
              onSubmit={handleSubmit}
            />
          </div>
        </Flex>
      </XProvider>
    </div>
  );
};

export default AIChat;
