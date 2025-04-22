import FilePreview from '@/components/FilePreview';
import FileUpload from '@/components/FileUpload';
import { fetchWithAuthNew, fetchWithAuthStream } from '@/utils/fetch';
import { UploadOutlined } from '@ant-design/icons';
import type { ActionType, ProColumns } from '@ant-design/pro-components';
import { ProTable } from '@ant-design/pro-components';
import { Button, message, Modal, Popconfirm, Switch, Tag, Tooltip } from 'antd';
import { useRef, useState } from 'react';

type KnowledgeBaseFile = {
  kb_id: string;
  file_id: string;
  file_name: string;
  file_size: number;
  file_words: number;
  status: string;
  error_message: string;
  created_at: string;
  kb_type: string;
};

const KnowledgeBaseList: React.FC = () => {
  const actionRef = useRef<ActionType>();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewFile, setPreviewFile] = useState<{
    fileName: string;
    fileId: string;
  }>({ fileName: '', fileId: '' });
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [deleting, setDeleting] = useState(false);
  const [dataSource, setDataSource] = useState<KnowledgeBaseFile[]>([]);

  const handleModalOk = () => {
    setIsModalOpen(false);
    actionRef.current?.reload();
  };

  const columns: ProColumns<KnowledgeBaseFile>[] = [
    {
      title: '文件名',
      dataIndex: 'file_name',
      copyable: true,
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      search: false,
      render: (_, record) => {
        let color = 'default';
        let text = record.status;
        let tooltipText = record.error_message;

        if (record.status === 'Done') {
          color = 'success';
          text = '解析完成';
        } else if (record.status === 'Failed') {
          color = 'error';
          text = '解析失败';
        } else {
          color = 'processing';
          text = '处理中';
        }

        return (
          <Tooltip title={tooltipText}>
            <Tag color={color}>{text}</Tag>
          </Tooltip>
        );
      },
    },

    {
      title: '仅自己可见',
      dataIndex: 'kb_type',
      search: false,
      render: (_, record) => {
        return (
          <Switch
            checked={record.kb_type === 'user'}
            checkedChildren="开启"
            unCheckedChildren="关闭"
            onChange={async (checked) => {
              try {
                const result = await fetchWithAuthNew(
                  '/api/v1/rag/file/switch',
                  {
                    method: 'POST',
                    data: {
                      file_id: record.file_id,
                      private: checked,
                    },
                  },
                );
                if (result !== undefined) {
                  message.success(
                    checked ? '已设为私人可见' : '已设为公开可见',
                  );
                  actionRef.current?.reload();
                }
              } catch (error) {
                message.error('切换状态失败');
              }
            }}
          />
        );
      },
    },

    {
      title: '创建时间',
      search: false,
      dataIndex: 'created_at',
      valueType: 'dateTime',
    },
    {
      title: '操作',
      valueType: 'option',
      key: 'option',
      render: (_, record) => [
        record.status === 'Done' && (
          <Button
            key="view"
            type="link"
            onClick={() => {
              setPreviewFile({
                fileName: record.file_name,
                fileId: record.file_id,
              });
              setPreviewVisible(true);
            }}
          >
            查看
          </Button>
        ),
        <Popconfirm
          key="delete"
          title="确定要删除这个文件吗？"
          onConfirm={async () => {
            try {
              const result = await fetchWithAuthNew('/api/v1/rag/files', {
                method: 'DELETE',
                data: {
                  file_ids: [record.file_id],
                },
              });
              if (result !== undefined) {
                message.success('删除成功');
              }
              actionRef.current?.reload();
            } catch (error) {
              message.error('删除失败');
            }
          }}
        >
          <Button type="link" danger>
            删除
          </Button>
        </Popconfirm>,
      ],
    },
  ];

  // 记录所有已选项，支持跨页多选
  const onSelectChange = (newSelectedRowKeys: React.Key[]) => {
    setSelectedRowKeys((prevSelected) => {
      // 当前页所有可能的key
      const currentPageAllKeys = dataSource.map((row) => row.file_id);

      // 从之前选中的key中，过滤掉当前页的所有key
      const keysFromOtherPages = prevSelected.filter(
        (key) => !currentPageAllKeys.includes(key as string),
      );

      // 合并：其他页面选中的 + 当前页新选中的
      return [...keysFromOtherPages, ...newSelectedRowKeys];
    });
  };

  return (
    <>
      <ProTable<KnowledgeBaseFile>
        columns={columns}
        actionRef={actionRef}
        cardBordered
        options={false}
        request={async (params) => {
          const { current, pageSize, ...rest } = params;
          try {
            const response = await fetchWithAuthNew('/api/v1/rag/files', {
              params: {
                page: current,
                page_size: pageSize,
                category: 'user_all',
                ...rest,
              },
            });

            // 更新当前页数据源
            setDataSource(response.list || []);

            return {
              data: response.list,
              success: true,
              total: response.total,
            };
          } catch (error) {
            message.error('获取列表失败');
            return {
              data: [],
              success: false,
              total: 0,
            };
          }
        }}
        rowKey="file_id"
        pagination={{
          showSizeChanger: true,
          pageSizeOptions: [1, 20, 50, 100],
        }}
        dateFormatter="string"
        headerTitle="知识库文件列表"
        rowSelection={{
          selectedRowKeys,
          onChange: onSelectChange,
        }}
        toolBarRender={() => [
          selectedRowKeys.length > 0 && (
            <Popconfirm
              key="batch-delete"
              title={`确定要删除选中的 ${selectedRowKeys.length} 个文件吗？`}
              onConfirm={async () => {
                setDeleting(true);
                try {
                  const result = await fetchWithAuthNew('/api/v1/rag/files', {
                    method: 'DELETE',
                    data: {
                      file_ids: selectedRowKeys,
                    },
                  });
                  if (result !== undefined) {
                    message.success('批量删除成功');
                    setSelectedRowKeys((prev) =>
                      prev.filter((key) => !selectedRowKeys.includes(key)),
                    );
                    actionRef.current?.reload();
                  }
                } catch (error) {
                  message.error('批量删除失败');
                } finally {
                  setDeleting(false);
                }
              }}
              okButtonProps={{ loading: deleting }}
            >
              <Button danger loading={deleting} disabled={deleting}>
                批量删除
              </Button>
            </Popconfirm>
          ),
          <Button
            key="upload"
            icon={<UploadOutlined />}
            onClick={() => setIsModalOpen(true)}
            type="primary"
          >
            文件上传
          </Button>,
        ]}
      />
      <Modal
        title="上传文件"
        open={isModalOpen}
        onOk={handleModalOk}
        onCancel={() => {}}
        closable={false}
        maskClosable={false}
        width={600}
        cancelButtonProps={{ style: { display: 'none' } }}
        destroyOnClose
      >
        <FileUpload category="user" />
      </Modal>
      <FilePreview
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        fileName={previewFile.fileName}
        fetchFile={async () => {
          const response = await fetchWithAuthStream(
            `/api/v1/rag/files/${previewFile.fileId}/download`,
            { method: 'GET' },
            true,
          );
          if (!response) {
            throw new Error('Failed to fetch file');
          }
          const blob = await response.blob();
          return URL.createObjectURL(blob);
        }}
      />
    </>
  );
};

export default KnowledgeBaseList;
