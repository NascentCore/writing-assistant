import { CrownOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import type { ActionType, ProColumns } from '@ant-design/pro-components';
import { ProTable } from '@ant-design/pro-components';
import { Button, Empty, message, Modal, Space, Tooltip } from 'antd';
import React, { useEffect, useRef, useState } from 'react';
import {
  addUsersToDepartment,
  getDepartmentUsers,
  getUserList,
  removeUserFromDepartment,
  setUserAdmin,
} from '../../service';
import styles from '../../style.less';
import { Department, DepartmentUser } from '../../type';

interface DepartmentUsersProps {
  currentDepartment: Department | null;
}

const DepartmentUsers: React.FC<DepartmentUsersProps> = ({
  currentDepartment,
}) => {
  const [addUserModalVisible, setAddUserModalVisible] = useState(false);
  const [selectedUserIds, setSelectedUserIds] = useState<string[]>([]);
  const [addUserLoading, setAddUserLoading] = useState(false);
  const actionRef = useRef<ActionType>();

  // 当选择的部门变化时刷新表格
  useEffect(() => {
    if (currentDepartment && actionRef.current) {
      actionRef.current.reload();
    }
  }, [currentDepartment]);

  // 删除用户确认
  const confirmRemoveUser = (user: DepartmentUser) => {
    Modal.confirm({
      title: '确认移除',
      content: `确定将用户 "${user.username}" 移出当前部门吗？`,
      onOk: async () => {
        if (!currentDepartment) return;

        try {
          const result = await removeUserFromDepartment({
            user_id: user.user_id,
            department_id: currentDepartment.department_id,
          });
          if (result !== undefined) {
            // 刷新表格数据
            actionRef.current?.reload();
            message.success('移除成功');
          }
        } catch (error) {
          console.error('移除用户失败:', error);
        }
      },
    });
  };

  // 设置用户为管理员
  const handleSetUserAdmin = async (user: DepartmentUser) => {
    try {
      const result = await setUserAdmin({
        user_id: user.user_id,
        admin: user.admin === 1 ? 0 : 1, // 切换管理员状态
      });
      if (result !== undefined) {
        message.success('设置成功');
        // 刷新表格数据
        actionRef.current?.reload();
      }
    } catch (error) {
      console.error('设置管理员失败:', error);
    }
  };

  // 添加用户到部门
  const handleAddUsers = async () => {
    if (!currentDepartment || selectedUserIds.length === 0) return;

    setAddUserLoading(true);
    try {
      const result = await addUsersToDepartment({
        user_ids: selectedUserIds,
        department_id: currentDepartment.department_id,
      });
      if (result !== undefined) {
        message.success('添加用户成功');
        setAddUserModalVisible(false);
        setSelectedUserIds([]);
        // 刷新表格数据
        actionRef.current?.reload();
      }
    } catch (error) {
      console.error('添加用户失败:', error);
    } finally {
      setAddUserLoading(false);
    }
  };

  // 部门用户表格列定义
  const columns: ProColumns<DepartmentUser>[] = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
      search: false,
    },
    {
      title: '加入时间',
      dataIndex: 'created_at',
      key: 'created_at',
      valueType: 'dateTime',
      search: false,
    },
    {
      title: '角色',
      dataIndex: 'admin',
      key: 'admin',
      search: false,
      render: (_, record) => (
        <span>
          {record.admin === 2 ? (
            <span style={{ color: '#1677ff' }}>
              <CrownOutlined style={{ marginRight: 4 }} />
              系统管理员
            </span>
          ) : record.admin === 1 ? (
            <span style={{ color: '#1677ff' }}>
              <CrownOutlined style={{ marginRight: 4 }} />
              管理员
            </span>
          ) : (
            '普通成员'
          )}
        </span>
      ),
    },
    {
      title: '操作',
      key: 'action',
      valueType: 'option',
      render: (_, record) => (
        <Space size="middle">
          {record.admin !== 2 && localStorage.getItem('admin') === '2' && (
            <Tooltip title={record.admin === 1 ? '取消管理员' : '设为管理员'}>
              <Button
                type="link"
                icon={<CrownOutlined />}
                onClick={() => handleSetUserAdmin(record)}
              />
            </Tooltip>
          )}

          <Tooltip title="移出部门">
            <Button
              type="link"
              danger
              icon={<DeleteOutlined />}
              onClick={() => confirmRemoveUser(record)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  // 外部用户列表表格列定义
  const userColumns: ProColumns<DepartmentUser>[] = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
      search: false,
    },
  ];

  return (
    <div className={styles.contentContainer}>
      {currentDepartment ? (
        <div className={styles.tableContainer}>
          <ProTable<DepartmentUser>
            actionRef={actionRef}
            rowKey="user_id"
            columns={columns}
            headerTitle={`${currentDepartment.name} - 成员管理`}
            search={{
              labelWidth: 'auto',
            }}
            request={async (params) => {
              const { current = 1, pageSize = 10, username, ...rest } = params;
              // 使用当前部门ID进行搜索，并传入分页参数
              const result = await getDepartmentUsers(
                currentDepartment.department_id,
                {
                  page: current,
                  page_size: pageSize,
                  username,
                  ...rest,
                },
              );

              return {
                data: result?.users || [],
                success: true,
                total: result?.total || result?.users?.length || 0,
              };
            }}
            cardBordered
            pagination={{ showSizeChanger: true }}
            options={false}
            toolBarRender={() => [
              <Button
                key="add"
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => setAddUserModalVisible(true)}
              >
                添加成员
              </Button>,
            ]}
            dateFormatter="string"
          />
        </div>
      ) : (
        <div className={styles.emptyTip}>
          <Empty description="请先选择左侧部门" />
        </div>
      )}

      <Modal
        title="添加部门成员"
        destroyOnClose
        open={addUserModalVisible}
        onOk={handleAddUsers}
        onCancel={() => {
          setAddUserModalVisible(false);
          setSelectedUserIds([]);
        }}
        width={800}
        confirmLoading={addUserLoading}
      >
        <ProTable<DepartmentUser>
          rowKey="user_id"
          columns={userColumns}
          search={{
            labelWidth: 'auto',
          }}
          cardBordered
          request={async (params) => {
            const { current = 1, pageSize = 10, ...rest } = params;
            const result = await getUserList({
              filter: 'no_departments',
              page: current,
              page_size: pageSize,
              ...rest,
            });

            return {
              data: result?.list || [],
              success: true,
              total: result?.total || 0,
            };
          }}
          rowSelection={{
            preserveSelectedRowKeys: true,
            selectedRowKeys: selectedUserIds,
            onChange: (selectedRowKeys) => {
              setSelectedUserIds(selectedRowKeys as string[]);
            },
          }}
          pagination={{
            showSizeChanger: true,
          }}
          tableAlertRender={({ selectedRowKeys, onCleanSelected }) => (
            <div>
              已选择 <a style={{ fontWeight: 600 }}>{selectedRowKeys.length}</a>{' '}
              项
              <a style={{ marginLeft: 8 }} onClick={onCleanSelected}>
                清空
              </a>
            </div>
          )}
          options={false}
        />
      </Modal>
    </div>
  );
};

export default DepartmentUsers;
