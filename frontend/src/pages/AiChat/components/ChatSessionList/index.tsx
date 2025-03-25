import { fetchWithAuthNew } from '@/utils/fetch';
import { DeleteOutlined } from '@ant-design/icons';
import { history, useLocation } from '@umijs/max';
import { Button, Empty, Spin, Typography, message } from 'antd';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import styles from './index.module.less';

// 会话历史接口返回类型
interface SessionItem {
  session_id: string;
  session_type: number;
  first_message: string;
  first_message_time: string;
  created_at: string;
  updated_at: string;
}

interface SessionResponse {
  list: SessionItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// 单个会话详情接口返回类型
interface SessionDetailResponse {
  total: number;
  items: {
    message_id: string;
    role: 'user' | 'assistant';
    content: string;
    created_at: string;
    files?: {
      file_id: string;
      name: string;
      size: number;
      type: string;
      status: number;
      created_at: string;
    }[];
  }[];
  page: number;
  page_size: number;
  pages: number;
}

export interface ChatMessage {
  key: string;
  placement: 'start' | 'end';
  content: string;
  avatarType: 'user' | 'assistant';
  loading?: boolean;
  files?: {
    file_id: string;
    name: string;
    size: number;
    type: string;
    status: number;
    created_at: string;
  }[];
}

interface ChatSessionListProps {
  onSessionChange: (sessionId: string, messages: ChatMessage[]) => void;
  onCreateNewSession: () => void;
  activeSessionId: string | null;
  defaultMessage: ChatMessage;
  refreshSessions?: (refreshSessionsList: () => void) => void; // 可选的刷新会话列表函数
}

// 使用 React.memo 包装加载更多按钮组件，避免不必要的重新渲染
const LoadMoreButton = React.memo(
  ({
    hasMore,
    loading,
    onClick,
  }: {
    hasMore: boolean;
    loading: boolean;
    onClick: () => void;
  }) => {
    if (!hasMore) return null;

    return (
      <div className={styles.loadMore}>
        <Button type="link" size="small" loading={loading} onClick={onClick}>
          加载更多
        </Button>
      </div>
    );
  },
);

// 使用 React.memo 包装会话列表组件，避免不必要的重新渲染
const ConversationsList = React.memo(
  ({
    items,
    activeKey,
    onActiveChange,
    onDeleteSession,
  }: {
    items: any[];
    activeKey?: string;
    onActiveChange: (key: string) => void;
    onDeleteSession: (sessionId: string) => void;
  }) => {
    // 自定义渲染会话项，添加删除按钮
    const renderItem = (item: any, isActive: boolean) => {
      const handleDelete = (e: React.MouseEvent) => {
        e.stopPropagation(); // 阻止事件冒泡
        onDeleteSession(item.key);
      };

      return (
        <div
          className={`${styles.sessionItem} ${
            isActive ? styles.activeSession : ''
          }`}
        >
          <div
            className={styles.sessionContent}
            onClick={() => onActiveChange(item.key)}
          >
            <div className={styles.sessionLabel}>{item.label}</div>
            <div className={styles.sessionDescription}>{item.description}</div>
          </div>
          <Button
            type="text"
            size="small"
            icon={<DeleteOutlined />}
            danger
            className={styles.deleteButton}
            onClick={handleDelete}
          />
        </div>
      );
    };

    return (
      <div className={styles.customSessionList}>
        {items.map((item) => (
          <div key={item.key} className={styles.sessionItemWrapper}>
            {renderItem(item, item.key === activeKey)}
          </div>
        ))}
      </div>
    );
  },
);

const ChatSessionList: React.FC<ChatSessionListProps> = ({
  onSessionChange,
  onCreateNewSession,
  activeSessionId,
  defaultMessage,
  refreshSessions,
}) => {
  // 获取当前路由信息
  const location = useLocation();

  // 会话历史相关状态
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [showSidebar, setShowSidebar] = useState(true);
  // 添加一个状态来跟踪会话列表是否需要刷新
  const [needRefresh, setNeedRefresh] = useState(false);

  // 添加一个ref来跟踪已加载的会话ID
  const loadedSessionsRef = useRef<Set<string>>(new Set());

  // 获取会话历史
  const fetchSessions = useCallback(async (page = 1) => {
    setSessionsLoading(true);
    try {
      const response = await fetchWithAuthNew<SessionResponse>(
        `/api/v1/rag/chat/sessions?page=${page}&page_size=20`,
      );

      if (response) {
        // 确保 response 是 SessionResponse 类型
        const sessionData = response as SessionResponse;
        if (page === 1) {
          setSessions(sessionData.list);
        } else {
          setSessions((prev) => [...prev, ...sessionData.list]);
        }

        setHasMore(page < sessionData.total_pages);
        setCurrentPage(page);
      }
    } catch (error) {
      console.error('获取会话历史失败', error);
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  // 加载更多会话
  const loadMoreSessions = useCallback(() => {
    if (!sessionsLoading && hasMore) {
      fetchSessions(currentPage + 1);
    }
  }, [sessionsLoading, hasMore, currentPage, fetchSessions]);

  // 切换会话
  const handleSessionChange = useCallback(
    async (sessionId: string) => {
      // 获取当前 URL 中的会话 ID
      const query = new URLSearchParams(location.search);
      const currentSessionIdFromUrl = query.get('id');

      // 只有当 URL 中的会话 ID 与要切换的会话 ID 不同时，才更新 URL
      if (currentSessionIdFromUrl !== sessionId) {
        // 只更新路由，不请求会话详情
        // history.push(`/AiChat?id=${sessionId}`);
        // 更新路由，添加会话ID参数
        const query = new URLSearchParams(location.search);
        query.set('id', sessionId); // Use sessionId here instead of sessionId!
        history.push(`${location.pathname}?${query.toString()}`);
        // 从已加载集合中移除，以便可以重新加载
        loadedSessionsRef.current.delete(sessionId);
      }
    },
    [location.search],
  );

  // 加载会话详情
  const loadSessionDetail = useCallback(
    async (sessionId: string) => {
      try {
        // 使用单个会话详情接口
        const response = await fetchWithAuthNew<SessionDetailResponse>(
          `/api/v1/rag/chat/sessions/${sessionId}?page=1&page_size=50`,
        );

        if (response) {
          const sessionDetail = response as SessionDetailResponse;
          // 确保 sessionDetail.items 存在且是数组
          const messageList = Array.isArray(sessionDetail.items)
            ? sessionDetail.items
            : [];

          // 将会话消息转换为聊天消息格式
          const chatMessages = messageList
            .filter(
              (msg) => msg && (msg.role === 'user' || msg.role === 'assistant'),
            ) // 过滤有效消息
            .map((msg) => ({
              key: msg.message_id || `msg-${Date.now()}-${Math.random()}`,
              placement:
                msg.role === 'user' ? ('end' as const) : ('start' as const),
              content: msg.content || '',
              avatarType:
                msg.role === 'user'
                  ? ('user' as const)
                  : ('assistant' as const),
              files: msg.files,
            }));

          // 如果没有消息，显示默认消息
          if (chatMessages.length === 0) {
            onSessionChange(sessionId, [defaultMessage]);
          } else {
            onSessionChange(sessionId, chatMessages);
          }
        } else {
          // 如果响应为空，显示默认消息
          // onSessionChange(sessionId, [defaultMessage]);
        }
      } catch (error) {
        console.error('加载会话消息失败', error);
        message.error('加载会话消息失败');
        onSessionChange(sessionId, [defaultMessage]);
      }
    },
    [onSessionChange, defaultMessage],
  );

  // 删除会话
  const handleDeleteSession = useCallback(
    async (sessionId: string) => {
      try {
        // 调用删除会话的接口
        await fetchWithAuthNew(`/api/v1/rag/chat/sessions/${sessionId}`, {
          method: 'DELETE',
        });

        message.success('会话删除成功');

        // 判断是否删除的是当前选中的会话
        if (sessionId === activeSessionId) {
          // 找到当前会话在列表中的索引
          const currentIndex = sessions.findIndex(
            (session) => session.session_id === sessionId,
          );

          if (currentIndex !== -1) {
            // 确定要选择的下一个会话
            let nextSessionIndex;

            // 如果当前会话是第一个，选择下一个会话
            if (currentIndex === 0) {
              nextSessionIndex = sessions.length > 1 ? 1 : -1;
            } else {
              // 否则选择上一个会话
              nextSessionIndex = currentIndex - 1;
            }

            // 如果有可选择的会话
            if (nextSessionIndex >= 0 && nextSessionIndex < sessions.length) {
              const nextSession = sessions[nextSessionIndex];
              // 切换到下一个会话
              handleSessionChange(nextSession.session_id);
            } else {
              // 如果没有其他会话了，创建新会话
              onCreateNewSession();
            }
          }
        }

        // 标记需要刷新会话列表
        setNeedRefresh(true);
      } catch (error) {
        console.error('删除会话失败', error);
        message.error('删除会话失败');
      }
    },
    [
      activeSessionId,
      sessions,
      handleSessionChange,
      onCreateNewSession,
      setNeedRefresh,
    ],
  );

  // 初始化加载会话历史
  useEffect(() => {
    // 只在组件首次加载时请求会话列表接口
    fetchSessions();
  }, [fetchSessions]);

  // 当需要刷新会话列表时，重新加载会话列表
  useEffect(() => {
    if (needRefresh) {
      fetchSessions(1);
      setNeedRefresh(false);
    }
  }, [needRefresh, fetchSessions]);

  // 处理 URL 变化，加载对应会话
  useEffect(() => {
    // 从 URL 中获取会话 ID 并加载对应会话
    const query = new URLSearchParams(location.search);
    const sessionIdFromUrl = query.get('id');

    // 如果没有会话 ID 参数，不做任何处理
    if (!sessionIdFromUrl) return;

    const sessionId = sessionIdFromUrl;

    // 如果 URL 中的会话 ID 与当前活动会话相同，不做任何处理
    if (sessionId === activeSessionId) return;

    // 检查这个会话是否已经加载过
    if (loadedSessionsRef.current.has(sessionId)) return;

    // 将当前会话ID添加到已加载集合中
    loadedSessionsRef.current.add(sessionId);

    // 检查这个会话 ID 是否在当前会话列表中
    const sessionExists = sessions.some(
      (session) => session.session_id === sessionId,
    );

    // 如果会话不在列表中，可能需要刷新会话列表
    if (!sessionExists && sessions.length > 0) {
      // 标记需要刷新会话列表
      setNeedRefresh(true);
      // 等待会话列表刷新后再加载会话
      setTimeout(() => {
        // 加载会话详情
        loadSessionDetail(sessionId);
      }, 500); // 给会话列表刷新一些时间
      return;
    }

    // 加载会话详情
    loadSessionDetail(sessionId);
  }, [
    location.search,
    activeSessionId,
    sessions,
    setNeedRefresh,
    loadSessionDetail,
  ]);

  // 格式化日期时间
  const formatDateTime = useCallback(
    (dateTimeStr: string | null | undefined) => {
      if (!dateTimeStr) {
        return '';
      }

      try {
        const date = new Date(dateTimeStr);
        // 检查日期是否有效
        if (isNaN(date.getTime())) {
          return '';
        }

        const now = new Date();
        const isToday = date.toDateString() === now.toDateString();

        if (isToday) {
          return date.toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          });
        } else {
          return date.toLocaleDateString('zh-CN', {
            month: 'numeric',
            day: 'numeric',
          });
        }
      } catch (error) {
        console.error('日期格式化错误:', error);
        return '';
      }
    },
    [],
  );

  // 格式化消息内容，去除 markdown 和过长的内容
  const formatMessageContent = useCallback(
    (content: string | null | undefined) => {
      // 如果内容为空，返回默认文本
      if (!content) {
        return '新对话';
      }

      // 去除 markdown 标记
      let plainText = content
        .replace(/\*\*(.*?)\*\*/g, '$1') // 去除粗体
        .replace(/\*(.*?)\*/g, '$1') // 去除斜体
        .replace(/\[(.*?)\]\(.*?\)/g, '$1') // 去除链接，只保留文本
        .replace(/```[\s\S]*?```/g, '[代码]') // 替换代码块
        .replace(/`(.*?)`/g, '$1') // 去除行内代码
        .replace(/#+\s(.*)/g, '$1') // 去除标题
        .replace(/\n/g, ' '); // 替换换行为空格
      return plainText;
    },
    [],
  );

  // 将会话数据转换为组件需要的格式
  const conversationItems = React.useMemo(
    () =>
      sessions
        .filter((session) => session && session.session_id) // 过滤掉无效的会话
        .map((session) => {
          // 确保时间戳有效
          const messageTime = session.first_message_time
            ? new Date(session.first_message_time)
            : new Date();
          const isToday =
            messageTime.toLocaleDateString() ===
            new Date().toLocaleDateString();

          return {
            key: session.session_id,
            label: formatMessageContent(session.first_message),
            timestamp: messageTime.getTime(),
            // group: isToday ? '今天' : messageTime.toLocaleDateString(),
            group: isToday ? '今天' : '过去',
            description: formatDateTime(session.first_message_time || ''),
          };
        }),
    [sessions, formatMessageContent, formatDateTime],
  );

  // 创建新会话按钮点击处理
  const handleCreateNewSession = useCallback(() => {
    // 更新路由，移除 id 参数
    history.push(location.pathname);

    // 调用父组件的创建新会话函数
    onCreateNewSession();

    // 如果有新会话创建，可能需要刷新会话列表
    // 但这里不直接刷新，而是等待用户发送第一条消息后再刷新
  }, [onCreateNewSession]);

  // 实现刷新会话列表的函数
  const refreshSessionsList = useCallback(() => {
    setNeedRefresh(true);
  }, [setNeedRefresh]);

  // 暴露刷新会话列表的方法
  useEffect(() => {
    if (refreshSessions) {
      // 调用外部传入的函数，传递内部的刷新函数
      refreshSessions(refreshSessionsList);
    }
  }, [refreshSessions, refreshSessionsList]);

  if (!showSidebar) {
    return (
      <Button
        type="text"
        onClick={() => setShowSidebar(true)}
        className={styles.toggleButton}
      >
        &gt;
      </Button>
    );
  }

  return (
    <div className={styles.sidebar}>
      <div className={styles.sidebarHeader}>
        <Typography.Title level={5} style={{ margin: 0 }}>
          会话历史
        </Typography.Title>
        {/* <Button
          type="text"
          size="small"
          onClick={() => setShowSidebar(false)}
          style={{ marginLeft: 'auto' }}
        >
          &lt;
        </Button> */}
      </div>
      <div className={styles.conversationsContainer} id="scrollableDiv">
        {sessionsLoading && sessions.length === 0 ? (
          <div className={styles.loading}>
            <Spin size="small" />
            <div>加载中...</div>
          </div>
        ) : sessions.length === 0 ? (
          <Empty description="暂无会话记录" />
        ) : (
          <div style={{ height: '100%', overflow: 'auto' }}>
            <ConversationsList
              items={conversationItems}
              activeKey={activeSessionId || undefined}
              onActiveChange={handleSessionChange}
              onDeleteSession={handleDeleteSession}
            />
            <LoadMoreButton
              hasMore={hasMore}
              loading={sessionsLoading}
              onClick={loadMoreSessions}
            />
          </div>
        )}
      </div>
      <div className={styles.sidebarFooter}>
        <Button type="primary" block onClick={handleCreateNewSession}>
          新建会话
        </Button>
      </div>
    </div>
  );
};

export default ChatSessionList;
