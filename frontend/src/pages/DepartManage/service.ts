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
  let my_own = localStorage.getItem('admin') !== '2';
  return fetchWithAuthNew<Department[]>(
    `${BASE_API}/departments?my_own=${my_own}`,
  ) as Promise<Department[] | undefined | null>;
}

// 创建部门
export async function createDepartment(
  params: CreateDepartmentParams,
): Promise<Department | undefined | null> {
  return fetchWithAuthNew<Department>(`${BASE_API}/departments`, {
    method: 'POST',
    data: params,
  }) as Promise<Department | undefined | null>;
}

// 获取部门成员
export async function getDepartmentUsers(
  departmentId: string,
  params?: {
    page?: number;
    page_size?: number;
    username?: string;
    [key: string]: any;
  },
): Promise<DepartmentDetail | undefined | null> {
  let url = `${BASE_API}/departments/${departmentId}`;

  // 如果有分页和搜索参数，添加到URL
  if (params) {
    const queryParams: string[] = [];
    Object.keys(params).forEach((key) => {
      if (params[key] !== undefined && params[key] !== null) {
        queryParams.push(`${key}=${encodeURIComponent(params[key])}`);
      }
    });

    if (queryParams.length > 0) {
      url += `?${queryParams.join('&')}`;
    }
  }

  return fetchWithAuthNew<DepartmentDetail>(url) as Promise<
    DepartmentDetail | undefined | null
  >;
}

// 查询用户列表（添加部门用户时使用）
export async function getUserList(params: {
  filter?: string;
  page: number;
  page_size: number;
  username?: string;
  [key: string]: any;
}): Promise<UserListResponse | undefined | null> {
  const {
    filter = 'no_departments',
    page,
    page_size,
    username,
    ...restParams
  } = params;
  let url = `${BASE_API}/users?filter=${filter}&page=${page}&page_size=${page_size}`;

  // 添加搜索参数
  if (username) {
    url += `&username=${encodeURIComponent(username)}`;
  }

  // 添加其他可能的查询参数
  Object.keys(restParams).forEach((key) => {
    if (restParams[key] !== undefined && restParams[key] !== null) {
      url += `&${key}=${encodeURIComponent(restParams[key])}`;
    }
  });

  return fetchWithAuthNew<UserListResponse>(url) as Promise<
    UserListResponse | undefined | null
  >;
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
