import { fetchWithAuthNew } from '@/utils/fetch';
import {
  CreateTemplateParams,
  TemplateListResponse,
  UpdateTemplateParams,
} from './type';

// 获取模板列表
export async function getTemplateList(params: {
  page: number;
  page_size: number;
}) {
  return fetchWithAuthNew<TemplateListResponse>('/api/v1/writing/templates', {
    method: 'GET',
    params,
  });
}

// 创建模板
export async function createTemplate(data: CreateTemplateParams) {
  return fetchWithAuthNew<{ id: string }>('/api/v1/writing/templates', {
    method: 'POST',
    data,
  });
}

// 更新模板
export async function updateTemplate(id: string, data: UpdateTemplateParams) {
  return fetchWithAuthNew<null>(`/api/v1/writing/templates/${id}`, {
    method: 'PUT',
    data,
  });
}

// 删除模板
export async function deleteTemplate(id: string) {
  return fetchWithAuthNew<null>(`/api/v1/writing/templates/${id}`, {
    method: 'DELETE',
  });
}

// 排序模板
export async function sortTemplates(template_ids: string[]) {
  return fetchWithAuthNew<null>('/api/v1/writing/templates/sort', {
    method: 'POST',
    data: { template_ids },
  });
}
