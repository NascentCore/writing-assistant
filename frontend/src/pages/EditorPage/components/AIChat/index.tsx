import { DeleteOutlined, UserOutlined } from '@ant-design/icons';
import { Bubble, Sender, XProvider } from '@ant-design/x';
import { Button, Flex } from 'antd';
import React, { useEffect, useRef, useState } from 'react';
import styles from './index.module.less';

const STORAGE_KEY = 'ai_chat_messages';

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

const AIChat: React.FC = () => {
  const [value, setValue] = useState('');
  const [resetKey, setResetKey] = useState(0); // 添加重置键
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
            <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 500 }}>
              AI助手
            </h3>
            <Button
              icon={<DeleteOutlined />}
              type="text"
              onClick={handleClearChat}
              title="清除聊天记录"
            />
          </Flex>
          <div className={styles.scrollContainer} ref={scrollContainerRef}>
            <Bubble.List items={displayMessages} />
          </div>
          <Sender
            value={value}
            onChange={(nextVal: string) => {
              setValue(nextVal);
            }}
            onSubmit={handleSubmit}
          />
        </Flex>
      </XProvider>
    </div>
  );
};

export default AIChat;
