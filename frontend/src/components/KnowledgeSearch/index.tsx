import FilePreview from '@/components/FilePreview';
import { fetchWithAuthNew, fetchWithAuthStream } from '@/utils/fetch';
import type { ProColumns } from '@ant-design/pro-components';
import { ProTable } from '@ant-design/pro-components';
import { Alert, Button, message, Modal, Space, Tag, Tooltip } from 'antd';
import React, { useEffect, useRef, useState } from 'react';

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

interface KnowledgeSearchProps {
  onSelect?: (selectedFiles: FileItem[]) => void;
  onCancel?: () => void;
  isModal?: boolean;
  selectedFiles?: FileItem[];
}

const KnowledgeSearch: React.FC<KnowledgeSearchProps> = ({
  onSelect,
  onCancel,
  isModal = false,
  selectedFiles = [],
}) => {
  const [totalCount, setTotalCount] = useState<number>(0);
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewFile, setPreviewFile] = useState<{
    fileName: string;
    fileId: string;
  }>({ fileName: '', fileId: '' });
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [selectedRows, setSelectedRows] = useState<FileItem[]>([]);
  const [currentPageData, setCurrentPageData] = useState<FileItem[]>([]);

  // 建立file_id到完整文件对象的映射
  const selectedFilesMapRef = useRef<Map<string, FileItem>>(new Map());

  // 初始化已选择的文件
  useEffect(() => {
    if (selectedFiles && selectedFiles.length > 0) {
      const fileIds = selectedFiles.map((file) => file.file_id);
      setSelectedRowKeys(fileIds);

      // 保存所有已选文件的完整信息
      const fileMap = new Map<string, FileItem>();
      selectedFiles.forEach((file) => {
        fileMap.set(file.file_id, file);
      });
      selectedFilesMapRef.current = fileMap;

      // 设置selectedRows为已选择的文件
      setSelectedRows(selectedFiles);
    } else {
      setSelectedRowKeys([]);
      setSelectedRows([]);
      selectedFilesMapRef.current.clear();
    }
  }, [selectedFiles]);

  // 当前页数据变化时，更新selectedRows以匹配当前页面显示的内容
  useEffect(() => {
    if (currentPageData.length > 0 && selectedRowKeys.length > 0) {
      try {
        // 获取所有选中的文件ID
        const allSelectedIds = new Set(selectedRowKeys);

        // 首先添加当前页上被选中的行
        const currentPageSelected = currentPageData.filter(
          (item) => item && item.file_id && allSelectedIds.has(item.file_id),
        );

        // 然后添加不在当前页但被选中的行（从selectedFilesMapRef中获取）
        const nonCurrentPageSelected = Array.from(
          selectedFilesMapRef.current.values(),
        ).filter(
          (item) =>
            item &&
            item.file_id &&
            allSelectedIds.has(item.file_id) &&
            !currentPageData.some(
              (current) => current && current.file_id === item.file_id,
            ),
        );

        setSelectedRows([...currentPageSelected, ...nonCurrentPageSelected]);
      } catch (error) {
        console.error('更新选中行时出错:', error);
      }
    }
  }, [currentPageData, selectedRowKeys]);

  const formatFileSize = (size: number) => {
    if (size < 1024) return `${size}B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)}KB`;
    return `${(size / (1024 * 1024)).toFixed(2)}MB`;
  };

  const handleSelectConfirm = () => {
    if (onSelect) {
      onSelect(selectedRows);
    }
  };

  const columns: ProColumns<FileItem>[] = [
    {
      title: '文件名',
      dataIndex: 'file_name',
      key: 'file_name',
      ellipsis: true,
      copyable: true,
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
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      search: false,
      render: (_, record) => {
        let color = 'default';
        let text = record.status;

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
          <Tooltip title={record.error_message}>
            <Tag color={color}>{text}</Tag>
          </Tooltip>
        );
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      search: false,
      render: (text) => new Date(text as string).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      search: false,
      render: (_, record) =>
        record.status === 'Done' && (
          <Button
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
    },
  ];

  const content = (
    <div>
      <ProTable<FileItem>
        columns={columns}
        cardBordered
        manualRequest
        options={false}
        rowSelection={{
          selectedRowKeys,
          onChange: (keys, rows) => {
            // 更新所选行的状态
            setSelectedRowKeys(keys);

            // 将新选中的行添加到映射中
            rows.forEach((row) => {
              if (row && row.file_id) {
                selectedFilesMapRef.current.set(row.file_id, row);
              }
            });

            // 从映射中移除取消选中的行
            const keySet = new Set(keys);
            const currentIds = currentPageData
              .map((item) => item.file_id)
              .filter(Boolean);
            currentIds.forEach((id) => {
              if (
                id &&
                !keySet.has(id) &&
                selectedFilesMapRef.current.has(id)
              ) {
                selectedFilesMapRef.current.delete(id);
              }
            });

            // 更新选中行列表
            const selectedList = Array.from(
              selectedFilesMapRef.current.values(),
            );
            setSelectedRows(selectedList);
          },
          getCheckboxProps: (record) => ({
            disabled: record.status !== 'Done',
          }),
          preserveSelectedRowKeys: true,
        }}
        request={async (params) => {
          if (!params.file_name?.trim()) {
            message.warning('请输入搜索关键词');
            setTotalCount(0);
            setCurrentPageData([]);
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
              setCurrentPageData([]);
              return {
                data: [],
                success: false,
                total: 0,
              };
            }

            const result = response as SearchResponse;
            setTotalCount(result.total);

            // 确保返回的列表数据有效
            const validList = Array.isArray(result.list)
              ? result.list.filter((item) => item && item.file_id)
              : [];

            // 保存当前页数据，用于更新selectedRows
            setCurrentPageData(validList);

            return {
              data: validList.slice(0, 50),
              success: true,
              total: Math.min(result.total, 50),
            };
          } catch (error) {
            message.error('获取文件列表失败');
            setCurrentPageData([]);
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
        tableAlertRender={({ selectedRowKeys, onCleanSelected }) => (
          <Space size={24}>
            <span>
              已选 {selectedRowKeys.length} 项
              <a
                style={{ marginLeft: 8 }}
                onClick={() => {
                  // 自定义清除函数，清空所有选择状态
                  setSelectedRowKeys([]);
                  setSelectedRows([]);
                  selectedFilesMapRef.current.clear();
                  // 调用原始的清除函数
                  onCleanSelected();
                }}
              >
                取消选择
              </a>
            </span>
          </Space>
        )}
        tableAlertOptionRender={() => {
          return (
            <Space size={16}>
              <Button type="primary" onClick={handleSelectConfirm}>
                确认选择
              </Button>
            </Space>
          );
        }}
      />
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
    </div>
  );

  return isModal ? (
    <Modal
      title="选择知识库文件"
      open={true}
      onCancel={onCancel}
      width={1000}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button key="submit" type="primary" onClick={handleSelectConfirm}>
          确认选择 ({selectedRows.length})
        </Button>,
      ]}
    >
      {content}
    </Modal>
  ) : (
    content
  );
};

export default KnowledgeSearch;
