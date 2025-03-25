import { fetchWithAuthNew } from '@/utils/fetch';
import type {
  AddUsersToDepartmentParams,
  CreateDepartmentParams,
  Department,
  DepartmentDetail,
  RemoveUserFromDepartmentParams,
  SetUserAdminParams,
  UserListResponse,
} from './type';

const BASE_API = '/api/v1/users';

// 获取部门列表
export async function getDepartments(): Promise<
  Department[] | undefined | null
> {
  return fetchWithAuthNew<Department[]>(`${BASE_API}/departments`);
}

// 创建部门
export async function createDepartment(
  params: CreateDepartmentParams,
): Promise<Department | undefined | null> {
  return fetchWithAuthNew<Department>(`${BASE_API}/departments`, {
    method: 'POST',
    data: params,
  });
}

// 获取部门成员
export async function getDepartmentUsers(
  departmentId: string,
): Promise<DepartmentDetail | undefined | null> {
  return fetchWithAuthNew<DepartmentDetail>(
    `${BASE_API}/departments/${departmentId}`,
  );
}

// 查询用户列表（添加部门用户时使用）
export async function getUserList(params: {
  filter?: string;
  page: number;
  page_size: number;
}): Promise<UserListResponse | undefined | null> {
  const { filter = 'no_departments', page, page_size } = params;
  return fetchWithAuthNew<UserListResponse>(
    `${BASE_API}/users?filter=${filter}&page=${page}&page_size=${page_size}`,
  );
}

// 添加用户到部门
export async function addUsersToDepartment(
  params: AddUsersToDepartmentParams,
): Promise<any> {
  return fetchWithAuthNew<null>(`${BASE_API}/users/department`, {
    method: 'POST',
    data: params,
  });
}

// 从部门移除用户
export async function removeUserFromDepartment(
  params: RemoveUserFromDepartmentParams,
): Promise<any> {
  return fetchWithAuthNew<null>(`${BASE_API}/user/department`, {
    method: 'DELETE',
    data: params,
  });
}

// 设置用户为部门管理员
export async function setUserAdmin(params: SetUserAdminParams): Promise<any> {
  return fetchWithAuthNew<null>(`${BASE_API}/user/admin`, {
    method: 'POST',
    data: params,
  });
}
