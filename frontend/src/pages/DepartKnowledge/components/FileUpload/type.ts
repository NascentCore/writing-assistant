import type { UploadFile, UploadProps } from 'antd';

export interface Department {
  department_id: string;
  name: string;
  description: string;
}

export interface FileUploadProps
  extends Omit<UploadProps, 'value' | 'onChange'> {
  url?: string;
  category?: string;
  value?: UploadFile[];
  onChange?: (fileList: UploadFile[]) => void;
  selectedDepartment?: string;
  onDepartmentChange?: (departmentId: string) => void;
}
