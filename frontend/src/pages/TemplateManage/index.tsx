import { PlusOutlined } from '@ant-design/icons';
import type { ProColumns } from '@ant-design/pro-components';
import { DragSortTable, PageContainer } from '@ant-design/pro-components';
import { Button, Popconfirm, Space, Tag } from 'antd';
import TemplateForm from './components/TemplateForm';
import { useTemplateManage } from './hook';
import { getTemplateList } from './service';
import type { Template } from './type';

const TemplateManage = () => {
  const {
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
  } = useTemplateManage();

  const columns: ProColumns<Template>[] = [
    {
      title: '排序',
      dataIndex: 'sort',
      width: 60,
      className: 'drag-visible',
    },
    {
      title: 'ID',
      dataIndex: 'id',
      width: 180,
      ellipsis: true,
    },
    {
      title: '模板名称',
      ellipsis: true,
      dataIndex: 'show_name',
      width: 150,
    },
    {
      title: '提示词',
      dataIndex: 'value',
      ellipsis: true,
    },
    {
      title: '描述',
      dataIndex: 'description',
      ellipsis: true,
    },
    {
      title: '是否有步骤',
      dataIndex: 'has_steps',
      width: 100,
      render: (_, record) =>
        record.has_steps ? (
          <Tag color="green">是</Tag>
        ) : (
          <Tag color="default">否</Tag>
        ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 180,
      valueType: 'dateTime',
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      width: 180,
      valueType: 'dateTime',
    },
    {
      title: '操作',
      key: 'option',
      width: 120,
      valueType: 'option',
      render: (_, record) => (
        <Space>
          <a key="edit" onClick={() => handleEdit(record)}>
            编辑
          </a>
          <Popconfirm
            title="确定要删除这个模板吗？"
            onConfirm={() => handleDeleteTemplate(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <a key="delete" style={{ color: 'red' }}>
              删除
            </a>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageContainer>
      <DragSortTable<Template>
        headerTitle="模板列表"
        actionRef={actionRef}
        options={false}
        rowKey="id"
        search={false}
        dataSource={dataSource}
        toolBarRender={() => [
          <Button
            key="add"
            type="primary"
            onClick={handleAdd}
            icon={<PlusOutlined />}
          >
            新建模板
          </Button>,
        ]}
        request={async (params) => {
          const { current = 1 } = params;
          const result = await getTemplateList({
            page: current,
            page_size: 999999999,
          });

          if (!result) {
            return {
              data: [],
              success: false,
              total: 0,
            };
          }

          // 处理可能是TemplateListResponse或其他类型的返回值
          const templates = 'templates' in result ? result.templates : [];
          const total = 'total' in result ? result.total : 0;

          // 更新本地数据源状态
          setDataSource(templates);

          return {
            data: templates,
            success: true,
            total: total,
          };
        }}
        dragSortKey="sort"
        onDragSortEnd={handleDragSortEnd}
        columns={columns}
        pagination={{
          showQuickJumper: true,
        }}
      />

      {/* 创建模板表单 */}
      <TemplateForm
        open={createModalOpen}
        title="新建模板"
        onOk={handleCreateTemplate}
        onCancel={() => setCreateModalOpen(false)}
        confirmLoading={confirmLoading}
      />

      {/* 编辑模板表单 */}
      <TemplateForm
        open={updateModalOpen}
        title="编辑模板"
        values={{
          id: currentTemplate?.id,
          show_name: currentTemplate?.show_name || '',
          value: currentTemplate?.value || '',
          description: currentTemplate?.description || '',
          has_steps: currentTemplate?.has_steps || false,
          background_url: currentTemplate?.background_url || '',
          outline_ids: currentTemplate?.outlines?.map((item) => item.id) || [],
        }}
        onOk={handleUpdateTemplate}
        onCancel={() => setUpdateModalOpen(false)}
        confirmLoading={confirmLoading}
      />
    </PageContainer>
  );
};

export default TemplateManage;
