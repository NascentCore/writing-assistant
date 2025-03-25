import { PlusOutlined } from '@ant-design/icons';
import { Button, Empty, Form, Input, message, Modal, Spin } from 'antd';
import React, { useEffect, useState } from 'react';
import { createDepartment } from '../../service';
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
            filteredDepartments.map((dept) => (
              <div
                key={dept.department_id}
                className={`${styles.departmentItem} ${
                  currentDepartment?.department_id === dept.department_id
                    ? styles.active
                    : ''
                }`}
                onClick={() => onSelectDepartment(dept)}
              >
                <div className={styles.departmentName}>{dept.name}</div>
              </div>
            ))
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
    </div>
  );
};

export default DepartmentList;
