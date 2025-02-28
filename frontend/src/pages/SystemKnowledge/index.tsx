import { fetchWithAuthNew } from '@/utils/fetch';
import { UploadOutlined } from '@ant-design/icons';
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
      tooltip: '文件名过长会自动收缩',
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
                category: 'system',
                ...rest,
              },
            });
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
          pageSize: 10,
        }}
        search={false}
        dateFormatter="string"
        headerTitle="知识库文件列表"
        toolBarRender={() => [
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
        <FileUpload />
      </Modal>
    </>
  );
};

export default KnowledgeBaseList;
