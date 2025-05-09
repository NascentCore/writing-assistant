import { fetchWithAuthNew } from '@/utils/fetch';
import { DeleteOutlined } from '@ant-design/icons';
import { history } from '@umijs/max';
import { Button, Empty, Spin, Typography, message } from 'antd';
import React, { useCallback, useEffect, useState } from 'react';
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
    task_status: 'pending' | 'processing' | 'completed' | 'failed';
    content_type: 'outline' | 'document' | 'text';
    task_result: string | null;
    document_id: string;
    outline_id: string;
    process?: number;
    process_detail_info?: string;
    log?: string;
    task_id?: string;
    files?: {
      file_id: string;
      name: string;
      size: number;
      type: string;
      status: number;
      created_at: string;
    }[];
    atfiles?: {
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

// 任务详情接口返回类型
interface TaskDetailResponse {
  id: string;
  type: string;
  status: 'processing' | 'completed' | 'failed' | 'pending';
  created_at: string;
  updated_at: string;
  result: any;
  error: string | null;
  process?: number; // 任务进度百分比
  process_detail_info?: string; // 任务进度详细信息
  log?: string; // 任务日志
}

export interface ChatMessage {
  key: string;
  placement: 'start' | 'end';
  content: string;
  avatarType: 'user' | 'assistant';
  loading?: boolean;
  status?: 'pending' | 'processing' | 'completed' | 'failed';
  error?: string | null;
  document_id?: string;
  outline_id?: string;
  content_type?: 'outline' | 'document' | 'text';
  files?: {
    file_id: string;
    name: string;
    size: number;
    type: string;
    status: number;
    created_at: string;
  }[];
  atfiles?: {
    file_id: string;
    name: string;
    size: number;
    type: string;
    status: number;
    created_at: string;
  }[];
  process?: number; // 任务进度百分比
  process_detail_info?: string; // 任务进度详细信息
  log?: string; // 任务日志
}

interface ChatSessionListProps {
  onSessionChange: (
    sessionId: string,
    messages: ChatMessage[],
    update?: {
      isProgressUpdate: boolean;
      taskId: string;
      progress?: number;
      status: string;
      log?: string;
      process_detail_info?: string;
    },
  ) => void;
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
          onClick={() => onActiveChange(item.key)}
        >
          <div className={styles.sessionContent}>
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

  // 会话历史相关状态
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [showSidebar, setShowSidebar] = useState(true);
  // 添加一个状态来跟踪会话列表是否需要刷新
  const [needRefresh, setNeedRefresh] = useState(false);
  // 添加一个状态来跟踪任务轮询的定时器ID
  const [taskPollingInterval, setTaskPollingInterval] =
    useState<NodeJS.Timeout | null>(null);
  // 添加一个状态来跟踪当前正在轮询的任务ID
  const [pollingTaskId, setPollingTaskId] = useState<string | null>(null);

  // 获取会话历史
  const fetchSessions = useCallback(async (page = 1) => {
    setSessionsLoading(true);
    try {
      const response = await fetchWithAuthNew<SessionResponse>(
        `/api/v1/writing/chat/sessions?page=${page}&page_size=20`,
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
        history.push(`/WritingHistory?id=${sessionId}`);
      }

      // 不在这里请求会话详情，而是由 URL 监听函数来触发
    },
    [location.search],
  );

  // 加载会话详情
  const loadSessionDetail = useCallback(
    async (sessionId: string) => {
      try {
        // 使用单个会话详情接口
        const response = await fetchWithAuthNew<SessionDetailResponse>(
          `/api/v1/writing/chat/sessions/${sessionId}?page=1&page_size=50`,
        );

        if (response) {
          const sessionDetail = response as SessionDetailResponse;
          // 确保 sessionDetail.items 存在且是数组
          const messageList = Array.isArray(sessionDetail.items)
            ? sessionDetail.items
            : [];

          // 将会话消息转换为聊天消息格式
          console.log('messageList', messageList);

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
              atfiles: msg.atfiles, // 添加知识库文件
              status: msg.task_status,
              error: msg.task_result,
              document_id: msg.document_id,
              content_type: msg.content_type,
              outline_id: msg.outline_id,
              // 如果是助手角色，且含有任务进度信息，则加入进度信息
              process: msg.role === 'assistant' ? msg.process : undefined,
              process_detail_info:
                msg.role === 'assistant' ? msg.process_detail_info : undefined,
              log: msg.role === 'assistant' ? msg.log : undefined,
            }));

          // 检查最后一条消息是否有 task_id
          const lastMessage = messageList[messageList.length - 1];
          if (
            lastMessage &&
            lastMessage.task_id &&
            lastMessage.task_status !== 'completed' &&
            !new URLSearchParams(location.search).get('task_id') &&
            lastMessage.task_status !== 'failed'
          ) {
            // 更新 URL，添加 task_id 参数
            history.push(
              `/WritingHistory?id=${sessionId}&task_id=${lastMessage.task_id}`,
            );
          }

          // 如果没有消息，显示默认消息
          if (chatMessages.length === 0) {
            onSessionChange(sessionId, [defaultMessage]);
          } else {
            onSessionChange(sessionId, chatMessages);
          }
        } else {
          // 如果响应为空，显示默认消息
          onSessionChange(sessionId, [defaultMessage]);
        }
      } catch (error) {
        console.error('加载会话消息失败', error);
        message.error('加载会话消息失败');
        onSessionChange(sessionId, [defaultMessage]);
      }
    },
    [onSessionChange, defaultMessage],
  );

  // 轮询任务详情接口
  const pollTaskStatus = useCallback(
    async (taskId: string, sessionId: string) => {
      try {
        const response = await fetchWithAuthNew<TaskDetailResponse>(
          `/api/v1/writing/tasks/${taskId}`,
        );

        if (response) {
          console.log('任务状态:', response.status);

          // 如果存在进度信息，更新会话UI
          if (
            response.status === 'processing' ||
            response.status === 'pending'
          ) {
            // 处理中的任务，直接更新现有消息的进度信息，不重新获取会话详情
            // 查找当前会话中最后一条助手消息
            const updatedMessage: ChatMessage = {
              key: `task-${taskId}`,
              placement: 'start',
              content: response.process_detail_info || '正在处理中...',
              avatarType: 'assistant',
              loading: true,
              status: response.status,
              process: response.process,
              process_detail_info: response.process_detail_info,
              log: response.log,
            };

            // 通知父组件更新消息
            // 这里不再请求会话详情，而是直接传递更新的消息和任务ID
            // 父组件需要负责在现有消息列表中查找和更新相应的消息
            onSessionChange(sessionId, [updatedMessage], {
              isProgressUpdate: true,
              taskId: taskId,
              progress: response.process || 0,
              status: response.status,
              log: response.log || '',
              process_detail_info: response.process_detail_info || '',
            });
          }

          // 如果任务状态不是处理中，停止轮询并重新加载会话详情
          if (
            response.status !== 'processing' &&
            response.status !== 'pending'
          ) {
            // 清除轮询定时器
            if (taskPollingInterval) {
              clearInterval(taskPollingInterval);
              setTaskPollingInterval(null);
            }

            // 清除当前轮询的任务ID
            setPollingTaskId(null);

            // 更新URL，移除task_id参数，直接使用原始会话ID
            if (location.pathname === '/WritingHistory') {
              history.push(`/WritingHistory?id=${sessionId}`);
            }

            // 只有当任务状态变为completed或failed时，才重新加载会话详情
            // 这样可以获取最终的结果
            loadSessionDetail(sessionId);

            // 如果任务失败，显示错误消息
            if (response.status === 'failed') {
              // message.error('任务处理失败: ' + (response.error || '未知错误'));
            } else if (response.status === 'completed') {
              // message.success('任务处理完成');
            }
          }
        }
      } catch (error) {
        console.error('轮询任务状态失败', error);
        // 发生错误时也停止轮询
        if (taskPollingInterval) {
          clearInterval(taskPollingInterval);
          setTaskPollingInterval(null);
        }
        // 清除当前轮询的任务ID
        setPollingTaskId(null);
      }
    },
    [
      loadSessionDetail,
      taskPollingInterval,
      setTaskPollingInterval,
      history,
      setPollingTaskId,
      onSessionChange,
    ],
  );

  // 删除会话
  const handleDeleteSession = useCallback(
    async (sessionId: string) => {
      try {
        // 调用删除会话的接口
        await fetchWithAuthNew(`/api/v1/writing/chat/sessions/${sessionId}`, {
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
    loadSessionDetail,
    setNeedRefresh,
  ]);

  // 处理 URL 中的 task_id 参数，实现任务轮询
  useEffect(() => {
    // 从 URL 中获取任务 ID 和会话 ID
    const query = new URLSearchParams(location.search);
    const taskId = query.get('task_id');
    const sessionId = query.get('id');

    // 如果没有任务ID或会话ID，清除轮询
    if (!taskId || !sessionId) {
      if (taskPollingInterval) {
        clearInterval(taskPollingInterval);
        setTaskPollingInterval(null);
        setPollingTaskId(null);
      }
      return;
    }

    // 如果已经在轮询同一个任务，不要重新启动轮询
    if (taskId === pollingTaskId && taskPollingInterval) {
      return;
    }

    // 清除之前的轮询定时器
    if (taskPollingInterval) {
      clearInterval(taskPollingInterval);
      setTaskPollingInterval(null);
    }

    // 设置当前正在轮询的任务ID
    setPollingTaskId(taskId);

    // 立即执行一次轮询
    pollTaskStatus(taskId, sessionId);

    // 设置定时器，每 5 秒轮询一次任务状态
    const intervalId = setInterval(() => {
      pollTaskStatus(taskId, sessionId);
    }, 5000);

    // 保存定时器 ID
    setTaskPollingInterval(intervalId);

    // 组件卸载时清除定时器
    return () => {
      if (taskPollingInterval) {
        clearInterval(taskPollingInterval);
      }
    };
  }, [location.search, pollTaskStatus, taskPollingInterval, pollingTaskId]);

  // 监听路由变化，终止轮询任务
  useEffect(() => {
    // 清除轮询定时器的函数
    const clearPolling = () => {
      if (taskPollingInterval) {
        clearInterval(taskPollingInterval);
        setTaskPollingInterval(null);
        setPollingTaskId(null);
      }
    };

    // 监听路由变化
    const unlisten = history.listen(() => {
      clearPolling();
    });

    // 组件卸载时清除监听器和轮询
    return () => {
      unlisten();
      clearPolling();
    };
  }, [taskPollingInterval, history]);

  // 当会话列表加载完成后，如果URL没有id参数且会话列表不为空，自动选择第一个会话
  useEffect(() => {
    const query = new URLSearchParams(location.search);
    const sessionIdFromUrl = query.get('id');

    // 如果URL没有id参数，会话列表不为空，且没有活动会话，则选择第一个会话
    if (!sessionIdFromUrl && sessions.length > 0 && !activeSessionId) {
      const firstSession = sessions[0];
      // 更新URL，添加会话ID参数
      history.push(`/WritingHistory?id=${firstSession.session_id}`);
    }
  }, [sessions, activeSessionId, location.search, history, loadSessionDetail]);

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
    history.push('/WritingAssistant');

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
    !(window as any).isIframe && (
      <div className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <Typography.Title level={5} style={{ margin: 0 }}>
            写作历史
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
        <div className={styles.sidebarFooter} style={{ display: 'none' }}>
          <Button type="primary" block onClick={handleCreateNewSession}>
            新建会话
          </Button>
        </div>
      </div>
    )
  );
};

export default ChatSessionList;
