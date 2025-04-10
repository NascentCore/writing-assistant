import type { ActionType } from '@ant-design/pro-components';
import { message } from 'antd';
import { useRef, useState } from 'react';
import {
  createTemplate,
  deleteTemplate,
  sortTemplates,
  updateTemplate,
} from './service';
import type { Template, TemplateFormValues } from './type';

export const useTemplateManage = () => {
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [updateModalOpen, setUpdateModalOpen] = useState(false);
  const [currentTemplate, setCurrentTemplate] = useState<Template>();
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [dataSource, setDataSource] = useState<Template[]>([]);
  const actionRef = useRef<ActionType>();

  // 打开创建模板弹窗
  const handleAdd = () => {
    setCreateModalOpen(true);
  };

  // 打开编辑模板弹窗
  const handleEdit = (record: Template) => {
    setCurrentTemplate(record);
    setUpdateModalOpen(true);
  };

  // 创建模板
  const handleCreateTemplate = async (values: TemplateFormValues) => {
    setConfirmLoading(true);
    try {
      const result = await createTemplate({
        show_name: values.show_name,
        value: values.value,
        description: values.description,
        has_steps: values.has_steps,
        background_url: values.background_url,
        outline_ids: values.outline_ids || [],
      });

      if (result) {
        setCreateModalOpen(false);
        message.success('创建成功');
        actionRef.current?.reload();
      }
    } catch (error) {
      console.error('创建模板失败：', error);
      message.error('创建失败');
    } finally {
      setConfirmLoading(false);
    }
  };

  // 更新模板
  const handleUpdateTemplate = async (values: TemplateFormValues) => {
    if (!currentTemplate) return;
    setConfirmLoading(true);
    try {
      await updateTemplate(currentTemplate.id, {
        id: currentTemplate.id,
        show_name: values.show_name,
        value: values.value,
        description: values.description,
        has_steps: values.has_steps,
        background_url: values.background_url,
        outline_ids: values.outline_ids || [],
      });

      // fetchWithAuthNew在失败时已经显示错误消息，这里只需处理成功的情况
      setUpdateModalOpen(false);
      message.success('更新成功');
      actionRef.current?.reload();
    } catch (error) {
      console.error('更新模板失败：', error);
      message.error('更新失败');
    } finally {
      setConfirmLoading(false);
    }
  };

  // 删除模板
  const handleDeleteTemplate = async (id: string) => {
    try {
      await deleteTemplate(id);
      // fetchWithAuthNew在失败时已经显示错误消息，这里只需处理成功的情况
      message.success('删除成功');
      actionRef.current?.reload();
    } catch (error) {
      console.error('删除模板失败：', error);
      message.error('删除失败');
    }
  };

  // 拖拽排序结束后处理
  const handleDragSortEnd = async (
    beforeIndex: number,
    afterIndex: number,
    newDataSource: Template[],
  ) => {
    // 立即更新本地数据源，使排序效果可见
    setDataSource([...newDataSource]);

    try {
      // 获取排序后的所有模板ID
      const template_ids = newDataSource.map((item) => item.id);
      // 调用排序接口
      await sortTemplates(template_ids);
      message.success('排序成功');
    } catch (error) {
      console.error('排序失败：', error);
      message.error('排序失败');
      // 如果排序失败，刷新表格恢复原有顺序
      actionRef.current?.reload();
    }
  };

  return {
    createModalOpen,
    updateModalOpen,
    currentTemplate,
    confirmLoading,
    actionRef,
    dataSource,
    setDataSource,
    handleAdd,
    handleEdit,
    handleCreateTemplate,
    handleUpdateTemplate,
    handleDeleteTemplate,
    handleDragSortEnd,
    setCreateModalOpen,
    setUpdateModalOpen,
  };
};
