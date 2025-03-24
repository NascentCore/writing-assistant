import { API_BASE_URL } from '@/config';
import { fetchWithAuthNew } from '@/utils/fetch';
import {
  CloudUploadOutlined,
  FileOutlined,
  PaperClipOutlined,
  SwapOutlined,
} from '@ant-design/icons';
import { Attachments, XProvider, Sender as XSender } from '@ant-design/x';
import { history } from '@umijs/max';
import { Badge, Button, Flex, GetRef, Select, message } from 'antd';
import { forwardRef, useEffect, useRef, useState } from 'react';
import styles from './Sender.module.less';

interface FileItem {
  file_id: string;
  name: string;
  size: number;
  type: string;
  status: number;
  created_at: string;
}

interface SenderProps {
  onMessageSent?: (message: string) => void;
  value?: string;
  selectedOutlineId?: number | null;
  outlines?: { id: number; title: string }[] | null;
  has_steps?: boolean;
}

interface Model {
  id: string;
  name: string;
  description: string;
}

const Sender = forwardRef<any, SenderProps>(
  ({
    onMessageSent,
    value: initialValue,
    selectedOutlineId: initialOutlineId,
    outlines = [],
    has_steps = false,
  }) => {
    const [value, setValue] = useState(initialValue || '');
    const [items, setItems] = useState<any[]>([]);
    const [open, setOpen] = useState(false);
    const [selectedFiles, setSelectedFiles] = useState<FileItem[]>([]);
    const [models, setModels] = useState<Model[]>([]);
    const [selectedModel, setSelectedModel] = useState<string>(() => {
      return localStorage.getItem('ai_chat_model') || '';
    });
    const [selectedOutlineId, setSelectedOutlineId] = useState<number | null>(
      initialOutlineId || null,
    );

    const attachmentsRef = useRef<GetRef<typeof Attachments>>(null);
    const senderRef = useRef<GetRef<typeof XSender>>(null);

    // 获取模型列表
    useEffect(() => {
      const fetchModels = async () => {
        try {
          const response = await fetchWithAuthNew('/api/v1/models');
          setModels(response.models);
          if (!selectedModel && response.models.length > 0) {
            setSelectedModel(response.models[0].name);
            localStorage.setItem('ai_chat_model', response.models[0].name);
          }
        } catch (error) {
          console.error('获取模型列表失败:', error);
        }
      };
      fetchModels();
    }, []);

    // 当 initialValue 或 initialOutlineId 变化时更新内部状态
    useEffect(() => {
      if (initialValue) {
        setValue(initialValue);
      }
      if (initialOutlineId !== undefined) {
        setSelectedOutlineId(initialOutlineId);
      }
    }, [initialValue, initialOutlineId]);

    const handleModelChange = (value: string) => {
      setSelectedModel(value);
      localStorage.setItem('ai_chat_model', value);
    };

    const handleOutlineChange = (value: number) => {
      setSelectedOutlineId(value);
    };

    const headerNode = (
      <XSender.Header
        title="附件"
        open={open}
        onOpenChange={setOpen}
        styles={{
          content: {
            padding: 0,
          },
        }}
        forceRender
      >
        <Attachments
          accept=".doc,.docx,.pdf"
          multiple
          ref={attachmentsRef}
          beforeUpload={() => true}
          customRequest={({ file, onSuccess, onError, onProgress }) => {
            const formData = new FormData();
            formData.append('files', file);
            const xhr = new XMLHttpRequest();
            xhr.open('POST', `${API_BASE_URL}/api/v1/rag/attachments`);
            xhr.setRequestHeader(
              'authorization',
              `Bearer ${localStorage.getItem('token')}`,
            );

            xhr.upload.onprogress = (event) => {
              if (event.lengthComputable) {
                const percent = Math.round((event.loaded / event.total) * 100);
                onProgress?.({ percent });
              }
            };

            xhr.onload = () => {
              if (xhr.status === 200) {
                try {
                  const response = JSON.parse(xhr.responseText);
                  if (response.code !== 200) {
                    onError?.(new Error('上传失败'));
                    message.error(`${response.message}`);
                    return;
                  }
                  onSuccess?.(response);
                } catch (e) {
                  onError?.(new Error('解析响应失败'));
                }
              } else {
                onError?.(new Error('上传失败'));
              }
            };
            xhr.onerror = () => {
              onError?.(new Error('网络错误'));
            };
            xhr.send(formData);
          }}
          items={items}
          onChange={({ fileList }) => {
            setItems(fileList);
            setSelectedFiles((prev) =>
              prev.filter((file) =>
                fileList.some(
                  (f) => f.response?.data?.[0]?.file_id === file.file_id,
                ),
              ),
            );

            if (fileList.length === 0) {
              setOpen(false);
            }

            const completedFiles = fileList
              .filter((file) => {
                return file.status === 'done' && file.response?.code === 200;
              })
              .map((file) => {
                const fileData = file.response.data?.[0];
                return {
                  file_id: fileData.file_id,
                  name: fileData.name || file.name,
                  size: fileData.size || file.size || 0,
                  type: fileData.content_type || '',
                  status: 1,
                  created_at: new Date().toISOString(),
                  percent: 100,
                };
              });

            if (completedFiles.length > 0) {
              setSelectedFiles((prev) => {
                const existingIds = new Set(prev.map((f) => f.file_id));
                const newFiles = completedFiles.filter(
                  (f) => !existingIds.has(f.file_id),
                );
                if (newFiles.length > 0) {
                  setOpen(true);
                }
                return [...prev, ...newFiles];
              });
            }
          }}
          placeholder={(type) =>
            type === 'drop'
              ? {
                  title: '拖拽文件到这里',
                }
              : {
                  icon: <CloudUploadOutlined />,
                  title: '上传文件',
                  description: (
                    <div>
                      <div>
                        点击或拖拽文件到此区域上传，此处仅上传背景资料，字数不宜超过2000字
                      </div>
                      <div>相关参考文件提前上传至个人知识库并自动解析</div>
                    </div>
                  ),
                }
          }
          getDropContainer={() => senderRef.current?.nativeElement}
        />
      </XSender.Header>
    );

    const handleSubmit = async () => {
      if (!value.trim()) return;

      try {
        // 构建请求数据
        const requestData: {
          model_name: string;
          file_ids: string[];
          prompt: string;
          outline_id?: number;
        } = {
          model_name: selectedModel,
          file_ids: selectedFiles
            .filter(
              (file) =>
                file.type === 'docx' ||
                file.type === 'pdf' ||
                file.type === 'doc',
            )
            .map((file) => file.file_id),
          prompt: value,
        };

        // 如果选择了大纲，添加到请求数据中
        if (selectedOutlineId) {
          requestData.outline_id = selectedOutlineId;
        }

        // 调用回调函数
        onMessageSent?.(value);

        // 清空输入和文件
        setValue('');
        setOpen(false);
        setSelectedFiles([]);
        setItems([]);

        // 根据has_steps选择不同的API路径
        const apiPath = has_steps
          ? '/api/v1/writing/outlines/generate'
          : '/api/v1/writing/content/generate';

        // 发送请求
        const response = await fetchWithAuthNew(apiPath, {
          method: 'POST',
          data: requestData,
        });
        history.push(
          `/WritingHistory?task_id=${response.task_id}&id=${response.session_id}`,
        );
        console.log('response', response);
      } catch (error) {
        console.error('发送消息失败:', error);
        message.error('发送消息失败，请稍后重试');
      }
    };
    const handleSelectedModel = (selectedModel: string) => {
      if (models.length === 0) {
        return '';
      }

      // 判断下selectedModel是否在models中
      const model = models.find((model) => model.name === selectedModel);
      if (model) {
        return selectedModel;
      }
      return models[0].name;
    };
    return (
      <XProvider>
        <div className={styles.senderContainer}>
          <Flex vertical gap={8}>
            <Flex
              justify="space-between"
              align="center"
              className={styles.modelSelector}
            >
              <div
                style={{ display: 'flex', alignItems: 'center', gap: '16px' }}
              >
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <div style={{ fontSize: '16px', fontWeight: 500 }}>
                    模型：
                  </div>
                  <Select
                    size="small"
                    value={handleSelectedModel(selectedModel)}
                    onChange={handleModelChange}
                    popupMatchSelectWidth={false}
                    prefix={<SwapOutlined />}
                  >
                    {models.map((model) => (
                      <Select.Option
                        key={model.id}
                        value={model.name}
                        title={model.description}
                      >
                        {model.name}
                      </Select.Option>
                    ))}
                  </Select>
                </div>

                {outlines && outlines.length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <div style={{ fontSize: '16px', fontWeight: 500 }}>
                      大纲：
                    </div>
                    <Select
                      size="small"
                      value={selectedOutlineId}
                      onChange={handleOutlineChange}
                      popupMatchSelectWidth={false}
                      placeholder="选择大纲"
                      allowClear
                      prefix={<FileOutlined />}
                      style={{ minWidth: '120px' }}
                    >
                      {outlines.map((outline) => (
                        <Select.Option
                          key={outline.id}
                          value={outline.id}
                          title={outline.title}
                        >
                          {outline.title}
                        </Select.Option>
                      ))}
                    </Select>
                  </div>
                )}
              </div>
            </Flex>
            <XSender
              ref={senderRef}
              header={headerNode}
              value={value}
              prefix={
                <Badge dot={!open && selectedFiles.length > 0}>
                  <Button
                    icon={<PaperClipOutlined style={{ fontSize: 18 }} />}
                    onClick={() => setOpen(!open)}
                  />
                </Badge>
              }
              onChange={(nextVal: string) => {
                setValue(nextVal);
              }}
              onPasteFile={(file) => {
                attachmentsRef.current?.upload(file);
                setOpen(true);
              }}
              onSubmit={handleSubmit}
            />
          </Flex>
        </div>
      </XProvider>
    );
  },
);

export default Sender;
