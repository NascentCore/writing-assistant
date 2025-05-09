import { Spin } from 'antd';
import React, { useEffect, useState } from 'react';
import DepartmentList from './components/DepartmentList';
import DepartmentUsers from './components/DepartmentUsers';
import { getDepartments } from './service';
import styles from './style.less';
import { Department } from './type';

const DepartManage: React.FC = () => {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [departmentLoading, setDepartmentLoading] = useState(false);
  const [currentDepartment, setCurrentDepartment] = useState<Department | null>(
    null,
  );

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
        } else if (currentDepartment) {
          // 如果当前有选中部门，刷新为新列表中的同 id 对象，保证名称等信息同步
          const updated = result.find(
            (dep) => dep.department_id === currentDepartment.department_id,
          );
          if (updated) {
            setCurrentDepartment(updated);
          }
        }
      }
    } catch (error) {
      console.error('获取部门列表失败:', error);
    } finally {
      setDepartmentLoading(false);
    }
  };

  // 选择部门
  const handleSelectDepartment = (department: Department) => {
    setCurrentDepartment(department);
  };

  useEffect(() => {
    fetchDepartments();
  }, []);

  return (
    <Spin spinning={departmentLoading}>
      <div className={styles.departmentContainer}>
        <DepartmentList
          departments={departments}
          loading={departmentLoading}
          currentDepartment={currentDepartment}
          onSelectDepartment={handleSelectDepartment}
          onCreateSuccess={fetchDepartments}
        />

        <DepartmentUsers currentDepartment={currentDepartment} />
      </div>
    </Spin>
  );
};

export default DepartManage;
