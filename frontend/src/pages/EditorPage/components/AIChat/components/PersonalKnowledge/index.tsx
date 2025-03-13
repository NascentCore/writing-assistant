import { fetchWithAuthNew } from '@/utils/fetch';
import type { ActionType, ProColumns } from '@ant-design/pro-components';
import { ProTable } from '@ant-design/pro-components';
import { message, Tag, Tooltip } from 'antd';
import { useRef, useState } from 'react';
// import FileUpload from './components/FileUpload';

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

interface KnowledgeBaseListProps {
  onSelectChange?: (selectedRowKeys: React.Key[]) => void;
  onSelectFiles?: (selectedFiles: KnowledgeBaseFile[]) => void;
  maxSelectCount?: number;
}

const KnowledgeBaseList: React.FC<KnowledgeBaseListProps> = ({
  onSelectChange,
  onSelectFiles,
  maxSelectCount = 5,
}) => {
  const actionRef = useRef<ActionType>();
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  const handleSelectChange = (
    newSelectedRowKeys: React.Key[],
    selectedRows: KnowledgeBaseFile[],
  ) => {
    // 限制选择的文件数量
    let finalSelectedRowKeys = [...newSelectedRowKeys];
    let finalSelectedRows = [...selectedRows];

    if (newSelectedRowKeys.length > maxSelectCount) {
      message.warning(`最多只能选择${maxSelectCount}个文件`);
      // 只保留前maxSelectCount个选择的文件
      finalSelectedRowKeys = newSelectedRowKeys.slice(0, maxSelectCount);
      finalSelectedRows = selectedRows.slice(0, maxSelectCount);
    }

    setSelectedRowKeys(finalSelectedRowKeys);

    if (onSelectChange) {
      onSelectChange(finalSelectedRowKeys);
    }

    if (onSelectFiles) {
      onSelectFiles(finalSelectedRows);
    }
  };

  const rowSelection = {
    selectedRowKeys,
    onChange: handleSelectChange,
    selections: [
      {
        key: 'info',
        text: `最多可选择${maxSelectCount}个文件`,
        onSelect: () => {},
      },
    ],
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
                category: 'user',
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
        rowSelection={rowSelection}
        pagination={{
          pageSize: 10,
        }}
        dateFormatter="string"
        headerTitle="知识库文件列表"
        options={false}
      />
    </>
  );
};

export default KnowledgeBaseList;
