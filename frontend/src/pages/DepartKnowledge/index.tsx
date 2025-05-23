import FilePreview from '@/components/FilePreview';
import { fetchWithAuthNew, fetchWithAuthStream } from '@/utils/fetch';
import { ReloadOutlined, UploadOutlined } from '@ant-design/icons';
import type { ActionType, ProColumns } from '@ant-design/pro-components';
import { ProTable } from '@ant-design/pro-components';
import { Button, message, Modal, Popconfirm, Tag, Tooltip } from 'antd';
import { useRef, useState } from 'react';
import FileUpload from './components/FileUpload';

type KnowledgeBaseFile = {
  kb_id: string;
  file_id: string;
  file_name: string;
  file_size: number;
  file_words: number;
  status: string;
  error_message: string;
  created_at: string;
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
          <>
            <Tooltip title={tooltipText}>
              <span>
                <Tag color={color} style={{ marginRight: 8 }}>
                  {text}
                </Tag>
              </span>
            </Tooltip>
            {record.status === 'Failed' && (
              <Tooltip title="重新上传">
                <ReloadOutlined
                  style={{ marginTop: 12, color: '#1677ff' }}
                  onClick={async (e) => {
                    e.stopPropagation();
                    try {
                      await fetchWithAuthNew(
                        `/api/v1/rag/file/${record.file_id}/reupload`,
                        {
                          method: 'POST',
                        },
                      );
                      message.success('重新上传已发起');
                      actionRef.current?.reload();
                    } catch (error) {
                      message.error('重新上传失败');
                    }
                  }}
                />
              </Tooltip>
            )}
          </>
        );
      },
    },
    {
      title: '部门名称',
      search: false,
      dataIndex: 'department_name',
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
          <a
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
          </a>
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
          <a type="link" style={{ color: '#f5222d' }}>
            删除
          </a>
        </Popconfirm>,
      ],
    },
  ];

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
        request={async (params) => {
          const { current, pageSize, ...rest } = params;
          try {
            const response = await fetchWithAuthNew('/api/v1/rag/files', {
              params: {
                page: current,
                page_size: pageSize,
                category: 'department_all',
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
        }}
        dateFormatter="string"
        headerTitle="知识库文件列表"
        options={false}
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
        <FileUpload category="department" />
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
