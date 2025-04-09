import { Form, Input, Modal, Switch } from 'antd';
import { useEffect } from 'react';
import type { TemplateFormValues } from '../type';

interface TemplateFormProps {
  open: boolean;
  title: string;
  values?: TemplateFormValues;
  onOk: (values: TemplateFormValues) => void;
  onCancel: () => void;
  confirmLoading: boolean;
}

const defaultBackgroundUrl =
  'https://lf-flow-web-cdn.doubao.com/obj/flow-doubao/samantha/writing-templates/template_composition2.png';

const TemplateForm: React.FC<TemplateFormProps> = ({
  open,
  title,
  values,
  onOk,
  onCancel,
  confirmLoading,
}) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (open && values) {
      form.setFieldsValue(values);
    } else if (open) {
      form.setFieldsValue({
        show_name: '',
        value: '',
        description: '',
        has_steps: false,
        background_url: defaultBackgroundUrl,
        outline_ids: [],
      });
    }
  }, [open, values, form]);

  const handleOk = async () => {
    try {
      const formValues = await form.validateFields();
      onOk(formValues);
    } catch (error) {
      console.error('验证表单失败：', error);
    }
  };

  return (
    <Modal
      title={title}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={confirmLoading}
      destroyOnClose
    >
      <Form form={form} layout="vertical" preserve={false}>
        <Form.Item
          name="show_name"
          label="模板名称"
          rules={[{ required: true, message: '请输入模板名称' }]}
        >
          <Input placeholder="请输入模板名称" />
        </Form.Item>

        <Form.Item
          name="value"
          label="提示词"
          rules={[{ required: true, message: '请输入提示词' }]}
        >
          <Input.TextArea rows={4} placeholder="请输入提示词" />
        </Form.Item>

        <Form.Item
          name="description"
          label="描述"
          rules={[{ required: true, message: '请输入描述' }]}
        >
          <Input.TextArea rows={2} placeholder="请输入描述" />
        </Form.Item>

        <Form.Item
          name="background_url"
          label="背景图片URL"
          initialValue={defaultBackgroundUrl}
        >
          <Input placeholder="请输入背景图片URL" />
        </Form.Item>

        <Form.Item
          name="has_steps"
          label="是否有步骤"
          valuePropName="checked"
          initialValue={false}
        >
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default TemplateForm;
