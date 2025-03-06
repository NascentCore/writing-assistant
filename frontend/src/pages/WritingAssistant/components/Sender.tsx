import { API_BASE_URL } from '@/config';
import { fetchWithAuthNew, fetchWithAuthStream } from '@/utils/fetch';
import {
  CloudUploadOutlined,
  PaperClipOutlined,
  SwapOutlined,
} from '@ant-design/icons';
import {
  Attachments,
  XProvider,
  Sender as XSender,
  XStream,
} from '@ant-design/x';
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
}

interface Model {
  id: string;
  name: string;
  description: string;
}

const Sender = forwardRef<any, SenderProps>(({ onMessageSent }) => {
  const [value, setValue] = useState('');
  const [items, setItems] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<FileItem[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>(() => {
    return localStorage.getItem('ai_chat_model') || '';
  });

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

  const handleModelChange = (value: string) => {
    setSelectedModel(value);
    localStorage.setItem('ai_chat_model', value);
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
              const fileData = file.response.data[0];
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
                description: '点击或拖拽文件到此区域上传',
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
      const requestData = {
        model_name: selectedModel,
        file_ids: selectedFiles
          .filter(
            (file) =>
              file.type === 'docx' ||
              file.type === 'pdf' ||
              file.type === 'doc',
          )
          .map((file) => file.file_id),
        question: value,
        stream: true,
      };

      // 调用回调函数
      onMessageSent?.(value);

      // 清空输入和文件
      setValue('');
      setOpen(false);
      setSelectedFiles([]);
      setItems([]);

      // 发送请求
      const response = await fetchWithAuthStream(
        '/api/v1/rag/chat',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestData),
        },
        true,
      );

      if (!response.ok || !response.body) {
        throw new Error('Stream response not available');
      }

      // 处理流式响应
      for await (const chunk of XStream({
        readableStream: response.body,
      })) {
        try {
          let data;
          if (typeof chunk.data === 'string') {
            data = JSON.parse(chunk.data);
          } else {
            data = chunk.data;
          }

          if (data.choices?.[0]?.delta?.content) {
            const content = data.choices[0].delta.content;
            // 这里可以添加处理响应内容的逻辑
            console.log(content);
          }
        } catch (error) {
          console.error('处理响应数据出错:', error);
        }
      }
    } catch (error) {
      console.error('发送消息失败:', error);
      message.error('发送消息失败，请稍后重试');
    }
  };
  const handleSelectedModel = (selectedModel: string) => {
    console.log('models', models);
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
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <div style={{ fontSize: '16px', fontWeight: 500 }}>模型：</div>
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
});

export default Sender;
