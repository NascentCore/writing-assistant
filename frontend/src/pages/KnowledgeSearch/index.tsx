import { fetchWithAuthNew } from '@/utils/fetch';
import type { ProColumns } from '@ant-design/pro-components';
import { ProTable } from '@ant-design/pro-components';
import { Alert, message } from 'antd';
import React, { useState } from 'react';

interface FileItem {
  kb_id: string;
  file_id: string;
  file_name: string;
  file_size: number;
  file_words: number;
  status: string;
  error_message: string;
  created_at: string;
}

interface SearchResponse {
  list: FileItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

const KnowledgeSearch: React.FC = () => {
  const [totalCount, setTotalCount] = useState<number>(0);

  const formatFileSize = (size: number) => {
    if (size < 1024) return `${size}B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)}KB`;
    return `${(size / (1024 * 1024)).toFixed(2)}MB`;
  };

  const columns: ProColumns<FileItem>[] = [
    {
      title: '文件名',
      dataIndex: 'file_name',
      key: 'file_name',
      ellipsis: true,
      fieldProps: {
        placeholder: '请输入文件名',
      },
    },
    {
      title: '大小',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 120,
      search: false,
      render: (_, record) => formatFileSize(record.file_size),
    },

    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      search: false,
      render: (text) => new Date(text as string).toLocaleString(),
    },
  ];

  return (
    <div>
      <ProTable<FileItem>
        columns={columns}
        cardBordered
        manualRequest
        options={false}
        request={async (params) => {
          if (!params.file_name?.trim()) {
            message.warning('请输入搜索关键词');
            setTotalCount(0);
            return {
              data: [],
              success: true,
              total: 0,
              page: 1,
              pageSize: 50,
            };
          }

          try {
            const response = await fetchWithAuthNew<SearchResponse>(
              '/api/v1/rag/files',
              {
                method: 'GET',
                params: {
                  category: 'all_shared',
                  page: params.current || 1,
                  page_size: 50,
                  file_name: params.file_name.trim(),
                },
              },
            );

            if (!response) {
              return {
                data: [],
                success: false,
                total: 0,
              };
            }

            const result = response as SearchResponse;
            setTotalCount(result.total);

            return {
              data: result.list.slice(0, 50),
              success: true,
              total: Math.min(result.total, 50),
            };
          } catch (error) {
            message.error('获取文件列表失败');
            return {
              data: [],
              success: false,
              total: 0,
            };
          }
        }}
        rowKey="file_id"
        pagination={{
          showQuickJumper: true,
          showSizeChanger: true,
          pageSize: 50,
          total: Math.min(totalCount, 50),
        }}
        search={{
          labelWidth: 'auto',
        }}
        dateFormatter="string"
        headerTitle={
          totalCount > 50 ? (
            <Alert
              style={{ marginTop: 16 }}
              message={`共找到 ${totalCount} 条结果，当前仅显示前 50 条，建议优化搜索关键词以获得更精确的匹配`}
              type="info"
              showIcon
            />
          ) : (
            '知识库检索'
          )
        }
      />
    </div>
  );
};

export default KnowledgeSearch;
