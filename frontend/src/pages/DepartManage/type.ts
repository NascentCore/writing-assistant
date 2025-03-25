// 部门信息类型定义
export interface Department {
  department_id: string;
  name: string;
  description: string;
  parent_id?: string;
  children?: Department[];
}

// 部门成员信息类型定义
export interface DepartmentUser {
  user_id: string;
  username: string;
  email: string;
  admin: number; // 1 或 2 表示是管理员
  created_at: string;
}

// 部门详情接口返回类型
export interface DepartmentDetail {
  department_id: string;
  department_name: string;
  knowledge_base: string;
  users: DepartmentUser[];
  total?: number;
  page?: number;
  page_size?: number;
  total_pages?: number;
}

// 用户列表接口返回类型
export interface UserListResponse {
  list: DepartmentUser[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// 创建部门请求参数
export interface CreateDepartmentParams {
  name: string;
  description: string;
  parent_id?: string;
}

// 添加用户到部门请求参数
export interface AddUsersToDepartmentParams {
  user_ids: string[];
  department_id: string;
}

// 从部门移除用户请求参数
export interface RemoveUserFromDepartmentParams {
  user_id: string;
  department_id: string;
}

// 设置用户为部门管理员请求参数
export interface SetUserAdminParams {
  user_id: string;
  admin: number;
}
