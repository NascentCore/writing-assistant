import { Spin } from 'antd';
import React, { useEffect, useState } from 'react';
import DepartmentList from './components/DepartmentList';
import DepartmentUsers from './components/DepartmentUsers';
import { getDepartments, getDepartmentUsers } from './service';
import styles from './style.less';
import { Department, DepartmentUser } from './type';

const DepartManage: React.FC = () => {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [departmentLoading, setDepartmentLoading] = useState(false);
  const [currentDepartment, setCurrentDepartment] = useState<Department | null>(
    null,
  );
  const [departmentUsers, setDepartmentUsers] = useState<DepartmentUser[]>([]);
  const [userLoading, setUserLoading] = useState(false);

  // 获取部门列表
  const fetchDepartments = async () => {
    setDepartmentLoading(true);
    try {
      const result = await getDepartments();
      if (result) {
        setDepartments(result);
        // 默认选中第一个部门
        if (result.length > 0 && !currentDepartment) {
          setCurrentDepartment(result[0]);
        }
      }
    } catch (error) {
      console.error('获取部门列表失败:', error);
    } finally {
      setDepartmentLoading(false);
    }
  };

  // 获取部门成员
  const fetchDepartmentUsers = async (departmentId: string) => {
    setUserLoading(true);
    try {
      const result = await getDepartmentUsers(departmentId);
      if (result) {
        setDepartmentUsers(result.users || []);
      }
    } catch (error) {
      console.error('获取部门成员失败:', error);
    } finally {
      setUserLoading(false);
    }
  };

  // 选择部门
  const handleSelectDepartment = (department: Department) => {
    setCurrentDepartment(department);
  };

  useEffect(() => {
    fetchDepartments();
  }, []);

  useEffect(() => {
    if (currentDepartment) {
      fetchDepartmentUsers(currentDepartment.department_id);
    }
  }, [currentDepartment]);

  return (
    <Spin spinning={departmentLoading && userLoading}>
      <div className={styles.departmentContainer}>
        <DepartmentList
          departments={departments}
          loading={departmentLoading}
          currentDepartment={currentDepartment}
          onSelectDepartment={handleSelectDepartment}
          onCreateSuccess={fetchDepartments}
        />

        <DepartmentUsers
          currentDepartment={currentDepartment}
          departmentUsers={departmentUsers}
          loading={userLoading}
          onRefreshUsers={() => {
            if (currentDepartment) {
              fetchDepartmentUsers(currentDepartment.department_id);
            }
          }}
        />
      </div>
    </Spin>
  );
};

export default DepartManage;
