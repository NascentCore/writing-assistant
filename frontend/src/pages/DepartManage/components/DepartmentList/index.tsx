import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons';
import {
  Button,
  Empty,
  Form,
  Input,
  message,
  Modal,
  Popconfirm,
  Spin,
} from 'antd';
import React, { useEffect, useState } from 'react';
import {
  createDepartment,
  deleteDepartment,
  editDepartment,
} from '../../service';
import styles from '../../style.less';
import { Department } from '../../type';

interface DepartmentListProps {
  departments: Department[];
  loading: boolean;
  currentDepartment: Department | null;
  onSelectDepartment: (department: Department) => void;
  onCreateSuccess: () => void;
}

const DepartmentList: React.FC<DepartmentListProps> = ({
  departments,
  loading,
  currentDepartment,
  onSelectDepartment,
  onCreateSuccess,
}) => {
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [form] = Form.useForm();
  const [searchValue, setSearchValue] = useState('');
  const [filteredDepartments, setFilteredDepartments] = useState<Department[]>(
    [],
  );
  const isAdmin =
    typeof window !== 'undefined' && localStorage.getItem('admin') === '2';
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editDepartmentData, setEditDepartmentData] =
    useState<Department | null>(null);

  useEffect(() => {
    if (departments.length > 0) {
      const filtered = searchValue
        ? departments.filter((dept) =>
            dept.name.toLowerCase().includes(searchValue.toLowerCase()),
          )
        : departments;
      setFilteredDepartments(filtered);
    } else {
      setFilteredDepartments([]);
    }
  }, [departments, searchValue]);

  const handleCreateDepartment = async () => {
    try {
      const values = await form.validateFields();
      const result = await createDepartment({
        name: values.name,
        description: values.description || '',
        parent_id: '',
      });

      if (result) {
        message.success('创建部门成功');
        setCreateModalVisible(false);
        form.resetFields();
        onCreateSuccess();
      }
    } catch (error) {
      console.error('创建部门失败:', error);
    }
  };

  const handleCancel = () => {
    setCreateModalVisible(false);
    form.resetFields();
  };

  const handleDeleteDepartment = async (departmentId: string) => {
    setDeletingId(departmentId);
    try {
      await deleteDepartment(departmentId);
      message.success('部门删除成功');
      if (currentDepartment?.department_id === departmentId) {
        const currentIndex = filteredDepartments.findIndex(
          (dept) => dept.department_id === departmentId,
        );
        let nextDepartment: Department | null = null;
        if (currentIndex !== -1) {
          if (currentIndex === 0 && filteredDepartments.length > 1) {
            nextDepartment = filteredDepartments[1];
          } else if (currentIndex > 0) {
            nextDepartment = filteredDepartments[currentIndex - 1];
          }
        }
        if (nextDepartment) {
          onSelectDepartment(nextDepartment);
        } else {
          onSelectDepartment({ department_id: '', name: '', description: '' });
        }
      }
      onCreateSuccess();
    } catch (error) {
      message.error('部门删除失败');
    } finally {
      setDeletingId(null);
    }
  };

  const handleEditDepartment = async () => {
    if (!editDepartmentData) return;
    try {
      await editDepartment({
        department_id: editDepartmentData.department_id,
        name: editDepartmentData.name,
        description: editDepartmentData.description,
      });
      message.success('部门编辑成功');
      setEditModalVisible(false);
      setEditDepartmentData(null);
      onCreateSuccess();
    } catch (error) {
      message.error('部门编辑失败');
    }
  };

  return (
    <div className={styles.siderContainer}>
      <div className={styles.departmentHeader}>
        <div className={styles.departmentTitle}>部门列表</div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateModalVisible(true)}
        >
          新建部门
        </Button>
      </div>

      <Input.Search
        placeholder="搜索部门"
        allowClear
        style={{ marginBottom: 16 }}
        onSearch={(value) => setSearchValue(value)}
        onChange={(e) => setSearchValue(e.target.value)}
      />

      <Spin spinning={loading}>
        <div className={styles.departmentList}>
          {filteredDepartments.length > 0 ? (
            filteredDepartments.map((dept) => {
              const isActive =
                currentDepartment?.department_id === dept.department_id;
              return (
                <div
                  key={dept.department_id}
                  className={`${styles.departmentItem} ${
                    isActive ? styles.active : ''
                  }`}
                  onClick={() => onSelectDepartment(dept)}
                >
                  <div className={styles.departmentName}>{dept.name}</div>
                  {isAdmin && (
                    <div
                      className={styles.departmentActions}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Button
                        type="text"
                        size="small"
                        icon={<EditOutlined style={{ color: '#1677ff' }} />}
                        onClick={() => {
                          setEditDepartmentData(dept);
                          setEditModalVisible(true);
                        }}
                      />
                      <Popconfirm
                        title="确定要删除该部门吗？"
                        onConfirm={() =>
                          handleDeleteDepartment(dept.department_id)
                        }
                        okText="删除"
                        cancelText="取消"
                      >
                        <Button
                          type="text"
                          size="small"
                          icon={<DeleteOutlined />}
                          danger
                          loading={deletingId === dept.department_id}
                        />
                      </Popconfirm>
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <Empty description="暂无部门" style={{ marginTop: 30 }} />
          )}
        </div>
      </Spin>

      <Modal
        title="新建部门"
        open={createModalVisible}
        onOk={handleCreateDepartment}
        onCancel={handleCancel}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="部门名称"
            rules={[{ required: true, message: '请输入部门名称' }]}
          >
            <Input placeholder="请输入部门名称" />
          </Form.Item>
          <Form.Item name="description" label="部门描述">
            <Input.TextArea placeholder="请输入部门描述" rows={4} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="编辑部门"
        open={editModalVisible}
        onOk={handleEditDepartment}
        onCancel={() => {
          setEditModalVisible(false);
          setEditDepartmentData(null);
        }}
        destroyOnClose
      >
        <Form
          layout="vertical"
          initialValues={editDepartmentData || { name: '', description: '' }}
          onValuesChange={(changed, all) => {
            setEditDepartmentData((prev) =>
              prev ? { ...prev, ...all } : null,
            );
          }}
        >
          <Form.Item
            name="name"
            label="部门名称"
            rules={[{ required: true, message: '请输入部门名称' }]}
          >
            <Input placeholder="请输入部门名称" />
          </Form.Item>
          <Form.Item name="description" label="部门描述">
            <Input.TextArea placeholder="请输入部门描述" rows={4} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default DepartmentList;
