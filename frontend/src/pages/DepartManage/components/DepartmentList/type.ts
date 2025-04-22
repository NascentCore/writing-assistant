// 部门列表组件相关类型定义

export interface EditDepartmentParams {
  department_id: string;
  name: string;
  description: string;
}

export interface DeleteDepartmentParams {
  department_id: string;
}

export interface EditDepartmentModalState {
  visible: boolean;
  department: {
    department_id: string;
    name: string;
    description: string;
  } | null;
}
