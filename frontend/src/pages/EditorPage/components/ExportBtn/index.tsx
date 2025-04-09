import { AiEditor } from 'aieditor';
import { Button, Dropdown, Form, Image, Menu, Modal, Radio, Space } from 'antd';
import React, { useState } from 'react';
import { API_BASE_URL } from '../../../../config';
import { downloadFile } from '../../../../utils/fetch';

interface ExportBtnGroupProps {
  editorRef: React.MutableRefObject<AiEditor | null>; // 添加 editorRef
}

const ExportBtnGroup: React.FC<ExportBtnGroupProps> = ({ editorRef }) => {
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [exportFormat, setExportFormat] = useState<string>('');
  const [form] = Form.useForm();

  // 处理导出逻辑
  const handleExport = async (format: string) => {
    setExportFormat(format);
    setIsModalVisible(true);
  };

  // 处理实际导出
  const handleConfirmExport = async () => {
    try {
      const values = await form.validateFields();
      if (!editorRef.current) return;

      const currentDocId = new URLSearchParams(window.location.search).get(
        'document_id',
      );
      if (!currentDocId) return;

      const numberingType = values.numbering_type;
      const url = `${API_BASE_URL}/api/v1/documents/${currentDocId}/export/${exportFormat}?numbering_type=${numberingType}`;

      downloadFile(url, exportFormat);
      setIsModalVisible(false);
      form.resetFields(); // 导出成功后也重置表单
    } catch (error) {
      console.error('Export error:', error);
      alert('导出失败，请稍后重试');
    }
  };

  // 关闭Modal
  const handleCancel = () => {
    setIsModalVisible(false);
    form.resetFields(); // 重置表单字段为初始值
  };

  // 定义下拉菜单内容，保留按钮原先的处理函数调用
  const menu = (
    <Menu>
      <Menu.Item
        key="pdf"
        onClick={() => {
          handleExport('pdf');
        }}
      >
        导出为 PDF
      </Menu.Item>
      <Menu.Item
        key="docx"
        onClick={() => {
          handleExport('docx');
        }}
      >
        导出为 Word
      </Menu.Item>
    </Menu>
  );

  return (
    <div>
      <Dropdown overlay={menu} trigger={['click']}>
        <Button>导出</Button>
      </Dropdown>

      <Modal
        title="选择导出样式"
        open={isModalVisible}
        width={600}
        destroyOnClose={true}
        onOk={handleConfirmExport}
        onCancel={handleCancel}
      >
        <Form
          layout="vertical"
          form={form}
          initialValues={{ numbering_type: 'chinese' }}
        >
          <Form.Item name="numbering_type" label="编号样式：">
            <Radio.Group>
              <Space>
                <Radio value="chinese">
                  <Space>
                    <Image
                      preview={false}
                      width={200}
                      src="/chinese.png"
                      alt="中文编号示例"
                    />
                  </Space>
                </Radio>
                <Radio value="number">
                  <Space>
                    <Image
                      preview={false}
                      width={200}
                      src="/number.png"
                      alt="数字编号示例"
                    />
                  </Space>
                </Radio>
              </Space>
            </Radio.Group>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ExportBtnGroup;
