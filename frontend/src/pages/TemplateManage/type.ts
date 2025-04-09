export interface Outline {
  id: string;
  title: string;
}

export interface Template {
  id: string;
  show_name: string;
  value: string;
  is_default: boolean;
  description: string;
  background_url: string;
  template_type: string;
  variables: any[];
  created_at: string;
  updated_at: string;
  outlines: Outline[];
  has_steps: boolean;
}

export interface TemplateListResponse {
  templates: Template[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateTemplateParams {
  show_name: string;
  value: string;
  description: string;
  has_steps: boolean;
  background_url: string;
  outline_ids: string[];
}

export interface UpdateTemplateParams extends CreateTemplateParams {
  id: string;
}

export interface TemplateFormValues {
  id?: string;
  show_name: string;
  value: string;
  description: string;
  has_steps: boolean;
  background_url: string;
  outline_ids: string[];
}
