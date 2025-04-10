import FilePreview from '@/components/FilePreview';
import KnowledgeSearch from '@/components/KnowledgeSearch';
import { API_BASE_URL } from '@/config';
import { fetchWithAuthNew, fetchWithAuthStream } from '@/utils/fetch';
import {
  BookOutlined,
  CloudUploadOutlined,
  DeleteOutlined,
  EyeOutlined,
  FileOutlined,
  PaperClipOutlined,
  PlusOutlined,
  SwapOutlined,
} from '@ant-design/icons';
import { Attachments, XProvider, Sender as XSender } from '@ant-design/x';
import { history } from '@umijs/max';
import {
  Badge,
  Button,
  Flex,
  GetRef,
  List,
  Select,
  Switch,
  message,
} from 'antd';
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

interface KnowledgeFileItem {
  kb_id: string;
  file_id: string;
  file_name: string;
  file_size: number;
  file_words: number;
  status: string;
  error_message: string;
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
    const [saveToKb, setSaveToKb] = useState<boolean>(() => {
      const saved = localStorage.getItem('ai_save_to_kb');
      return saved ? saved === 'true' : true;
    });
    console.log('saveToKb', saveToKb);

    const [webSearch, setWebSearch] = useState<boolean>(() => {
      const saved = localStorage.getItem('ai_web_search');
      return saved ? saved === 'true' : true;
    });

    // 添加知识库相关状态
    const [kbSearchModalVisible, setKbSearchModalVisible] = useState(false);
    const [kbFilesOpen, setKbFilesOpen] = useState(false);
    const [knowledgeFiles, setKnowledgeFiles] = useState<KnowledgeFileItem[]>(
      [],
    );
    const [previewVisible, setPreviewVisible] = useState(false);
    const [previewFile, setPreviewFile] = useState<{
      fileName: string;
      fileId: string;
    }>({ fileName: '', fileId: '' });

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

    // 处理知识库文件选择
    const handleKnowledgeFilesSelect = (files: KnowledgeFileItem[]) => {
      // 直接使用选择的文件列表替换原有列表
      setKnowledgeFiles(files);
      setKbSearchModalVisible(false);
      setKbFilesOpen(true);
    };

    // 删除知识库文件
    const handleDeleteKnowledgeFile = (fileId: string) => {
      setKnowledgeFiles((prevFiles) => {
        const newFiles = prevFiles.filter((file) => file.file_id !== fileId);
        // 如果删除后没有文件了，自动关闭面板
        if (newFiles.length === 0) {
          setKbFilesOpen(false);
        }
        return newFiles;
      });
    };

    const formatFileSize = (size: number) => {
      if (size < 1024) return `${size}B`;
      if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)}KB`;
      return `${(size / (1024 * 1024)).toFixed(2)}MB`;
    };

    // 处理文件预览
    const handleFilePreview = (fileName: string, fileId: string) => {
      setPreviewFile({
        fileName,
        fileId,
      });
      setPreviewVisible(true);
    };

    // 添加知识库文件展示的headerNode
    const kbFilesHeaderNode = (
      <XSender.Header
        title="知识库文件"
        open={kbFilesOpen}
        onOpenChange={setKbFilesOpen}
        styles={{
          content: {
            padding: 0,
          },
        }}
        forceRender
      >
        <div style={{ padding: '16px', maxHeight: 300, overflow: 'auto' }}>
          <Flex vertical gap={12}>
            <List
              size="small"
              bordered
              dataSource={knowledgeFiles}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <Button
                      key="preview"
                      type="text"
                      icon={<EyeOutlined style={{ color: '#1677ff' }} />}
                      onClick={() =>
                        handleFilePreview(item.file_name, item.file_id)
                      }
                    />,
                    <Button
                      key="delete"
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => handleDeleteKnowledgeFile(item.file_id)}
                    />,
                  ]}
                >
                  <div style={{ flex: 1, overflow: 'hidden' }}>
                    <div
                      style={{
                        fontWeight: 500,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {item.file_name}
                    </div>
                    <div style={{ fontSize: '12px', color: '#8c8c8c' }}>
                      {formatFileSize(item.file_size)}
                    </div>
                  </div>
                </List.Item>
              )}
              footer={
                <Button
                  type="dashed"
                  block
                  icon={<PlusOutlined />}
                  onClick={() => setKbSearchModalVisible(true)}
                >
                  添加知识库文件
                </Button>
              }
            />
          </Flex>
        </div>
      </XSender.Header>
    );

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
            formData.append('save_to_kb', saveToKb.toString());

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
        // 根据has_steps选择不同的API路径
        const apiPath = has_steps
          ? '/api/v1/writing/outlines/generate'
          : '/api/v1/writing/content/generate';

        // 构建请求数据
        const requestData: {
          model_name: string;
          file_ids: string[];
          prompt: string;
          outline_id?: number;
          save_to_kb: boolean;
          web_search?: boolean;
          files?: FileItem[];
          at_file_ids?: string[];
          atfiles?: KnowledgeFileItem[];
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
          save_to_kb: saveToKb,
          files: selectedFiles.length > 0 ? selectedFiles : undefined,
        };

        // 如果是内容生成接口，添加web_search参数
        if (apiPath === '/api/v1/writing/content/generate') {
          requestData.web_search = webSearch;
        }

        // 如果选择了大纲，添加到请求数据中
        if (selectedOutlineId) {
          requestData.outline_id = selectedOutlineId;
        }

        // 添加知识库文件ID和文件信息
        if (knowledgeFiles.length > 0) {
          requestData.at_file_ids = knowledgeFiles.map((file) => file.file_id);
          requestData.atfiles = knowledgeFiles;
        }

        // 调用回调函数
        onMessageSent?.(value);

        // 清空输入和文件
        setValue('');
        setOpen(false);
        setSelectedFiles([]);
        setItems([]);
        // 清空知识库文件选择
        setKbFilesOpen(false);
        setKnowledgeFiles([]);

        // 发送请求
        const response = await fetchWithAuthNew(apiPath, {
          method: 'POST',
          data: requestData,
        });
        //向外部页面通知创建session_id
        if ((window as any).createChatId) {
          window.parent.postMessage(
            {
              type: 'onCreateChatId',
              value: response.session_id,
            },
            '*',
          );
        }

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
                  <div style={{ fontSize: '16px' }}>模型：</div>
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
                  <div
                    style={{
                      display: 'none',
                      marginLeft: 20,
                      fontSize: '16px',
                    }}
                  >
                    同步到个人知识库：
                  </div>
                  <Switch
                    style={{ display: 'none' }}
                    checked={saveToKb}
                    onChange={(checked) => {
                      setSaveToKb(checked);
                      localStorage.setItem('ai_save_to_kb', checked.toString());
                    }}
                    checkedChildren="开启"
                    unCheckedChildren="关闭"
                  />
                  <div
                    style={{
                      marginLeft: 20,
                      fontSize: '16px',
                    }}
                  >
                    联网搜索：
                  </div>
                  <Switch
                    checked={webSearch}
                    onChange={(checked) => {
                      setWebSearch(checked);
                      localStorage.setItem('ai_web_search', checked.toString());
                    }}
                    checkedChildren="开启"
                    unCheckedChildren="关闭"
                  />
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
              header={[headerNode, kbFilesHeaderNode]}
              value={value}
              prefix={
                <>
                  <Badge dot={!open && selectedFiles.length > 0}>
                    <Button
                      icon={<PaperClipOutlined style={{ fontSize: 18 }} />}
                      onClick={() => setOpen(!open)}
                    />
                  </Badge>
                  <Badge dot={!kbFilesOpen && knowledgeFiles.length > 0}>
                    <Button
                      style={{ marginLeft: 8 }}
                      icon={<BookOutlined style={{ fontSize: 18 }} />}
                      onClick={() => setKbFilesOpen(!kbFilesOpen)}
                    />
                  </Badge>
                </>
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

        {/* 知识库文件选择弹窗 */}
        {kbSearchModalVisible && (
          <KnowledgeSearch
            isModal={true}
            onSelect={handleKnowledgeFilesSelect}
            onCancel={() => setKbSearchModalVisible(false)}
            selectedFiles={knowledgeFiles}
          />
        )}

        {/* 文件预览弹窗 */}
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
      </XProvider>
    );
  },
);

export default Sender;
