import { fetchWithAuthNew } from '@/utils/fetch';
import { ActionType, ProColumns, ProTable } from '@ant-design/pro-components';
import { useNavigate } from '@umijs/max';
import { useRef } from 'react';
import styles from './index.module.less';
import type { UserSessionItem } from './type';

const UserSessionList = () => {
  const actionRef = useRef<ActionType>();
  const navigate = useNavigate();

  const columns: ProColumns<UserSessionItem>[] = [
    {
      title: '写作会话ID',
      dataIndex: 'session_id',
      ellipsis: true,
      width: 180,
      search: false,
    },
    {
      title: '用户名',
      dataIndex: 'username',
      width: 120,
      search: true,
    },
    // {
    //   title: '首次消息',
    //   dataIndex: 'first_message',
    //   ellipsis: true,
    //   width: 200,
    // },
    {
      title: '写作会话发起时间',
      dataIndex: 'first_message_time',
      valueType: 'dateTime',
      width: 180,
      search: false,
    },
    // {
    //   title: '最后消息',
    //   dataIndex: 'last_message',
    //   ellipsis: true,
    //   width: 200,
    // },
    // {
    //   title: '最后时间',
    //   dataIndex: 'last_message_time',
    //   valueType: 'dateTime',
    //   width: 180,
    // },
    {
      title: '操作',
      valueType: 'option',
      width: 100,
      render: (_, record) => (
        <a
          onClick={() =>
            navigate(
              `/WritingHistory?id=${record.session_id}&user_id=${record.user_id}`,
            )
          }
        >
          查看
        </a>
      ),
    },
  ];

  return (
    <div className={styles.container}>
      <ProTable<UserSessionItem>
        rowKey="session_id"
        columns={columns}
        actionRef={actionRef}
        options={false}
        request={async (params) => {
          const { current = 1, pageSize = 10, username } = params;
          const res = await fetchWithAuthNew<{
            list: UserSessionItem[];
            total: number;
          }>(
            `/api/v1/writing/chat/sessions?page=${current}&page_size=${pageSize}&global_search=true${
              username ? `&username=${username}` : ''
            }`,
          );
          // 兼容 res 可能为 undefined 的情况
          const list = res && 'list' in res ? res.list : [];
          const total = res && 'total' in res ? res.total : 0;
          return {
            data: list,
            total,
            success: true,
          };
        }}
        pagination={{ showSizeChanger: true }}
        search={{ labelWidth: 80 }}
        scroll={{ x: 1200 }}
      />
    </div>
  );
};

export default UserSessionList;
