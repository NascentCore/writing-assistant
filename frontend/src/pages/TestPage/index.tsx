import supabase from '@/utils/supabase';
import { faker } from '@faker-js/faker/locale/zh_CN';
import { Button, Form, Input, InputNumber, message, Select, Tabs } from 'antd';
import React, { useState } from 'react';
import { useRegistration } from './hook';
import styles from './index.module.less';
import { RegisterFormValues } from './type';

const TestPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const { loading: registerLoading, registerUser } = useRegistration();
  const [form] = Form.useForm<RegisterFormValues>();

  const insertFakeData = async () => {
    try {
      setLoading(true);

      // 使用faker生成一条假数据
      const fakeData = {
        name: faker.person.fullName(),
        // created_at由Supabase自动生成，无需提供
      };

      // 插入数据到表中
      const { data, error } = await supabase
        .from('测试') // 从截图中看不出确切表名，请替换为实际表名
        .insert(fakeData)
        .select();

      if (error) {
        throw error;
      }

      message.success('数据插入成功！');
      console.log('插入的数据：', data);
    } catch (error: any) {
      message.error(`插入失败：${error.message || '未知错误'}`);
      console.error('插入错误：', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (values: RegisterFormValues) => {
    if (values.password !== values.confirmPassword) {
      message.error('两次输入的密码不一致！');
      return;
    }

    const data = await registerUser(values);
    if (data) {
      form.resetFields();
    }
  };

  return (
    <div className={styles.testPage}>
      <h1>测试页</h1>
      <p>这是一个测试页面。</p>

      <Tabs
        defaultActiveKey="register"
        items={[
          {
            key: 'fakeData',
            label: '测试数据',
            children: (
              <div className={styles.actionArea}>
                <Button
                  type="primary"
                  onClick={insertFakeData}
                  loading={loading}
                >
                  插入假数据到Supabase
                </Button>
              </div>
            ),
          },
          {
            key: 'register',
            label: '用户注册',
            children: (
              <div className={styles.registerForm}>
                <div className={styles.formTitle}>用户注册</div>
                <Form<RegisterFormValues>
                  form={form}
                  layout="vertical"
                  onFinish={handleRegister}
                  requiredMark={false}
                >
                  <Form.Item
                    name="username"
                    label="用户名"
                    rules={[
                      { required: true, message: '请输入用户名' },
                      { min: 3, message: '用户名至少3个字符' },
                      { max: 20, message: '用户名最多20个字符' },
                    ]}
                  >
                    <Input placeholder="请输入用户名" />
                  </Form.Item>

                  <Form.Item
                    name="email"
                    label="邮箱"
                    rules={[
                      { required: true, message: '请输入邮箱' },
                      { type: 'email', message: '请输入有效的邮箱地址' },
                    ]}
                  >
                    <Input placeholder="请输入邮箱" />
                  </Form.Item>

                  <Form.Item
                    name="gender"
                    label="性别"
                    rules={[{ required: false }]}
                  >
                    <Select
                      placeholder="请选择性别"
                      options={[
                        { value: '男', label: '男' },
                        { value: '女', label: '女' },
                        { value: '其他', label: '其他' },
                      ]}
                    />
                  </Form.Item>

                  <Form.Item
                    name="age"
                    label="年龄"
                    rules={[
                      { required: false },
                      {
                        type: 'number',
                        min: 1,
                        max: 120,
                        message: '请输入有效年龄(1-120)',
                      },
                    ]}
                  >
                    <InputNumber
                      placeholder="请输入年龄"
                      style={{ width: '100%' }}
                    />
                  </Form.Item>

                  <Form.Item
                    name="password"
                    label="密码"
                    rules={[
                      { required: true, message: '请输入密码' },
                      { min: 6, message: '密码至少6个字符' },
                    ]}
                  >
                    <Input.Password placeholder="请输入密码" />
                  </Form.Item>

                  <Form.Item
                    name="confirmPassword"
                    label="确认密码"
                    dependencies={['password']}
                    rules={[
                      { required: true, message: '请确认密码' },
                      ({ getFieldValue }) => ({
                        validator(_, value) {
                          if (!value || getFieldValue('password') === value) {
                            return Promise.resolve();
                          }
                          return Promise.reject(
                            new Error('两次输入的密码不一致'),
                          );
                        },
                      }),
                    ]}
                  >
                    <Input.Password placeholder="请再次输入密码" />
                  </Form.Item>

                  <Form.Item>
                    <Button
                      type="primary"
                      htmlType="submit"
                      block
                      loading={registerLoading}
                    >
                      注册
                    </Button>
                  </Form.Item>
                </Form>
              </div>
            ),
          },
        ]}
      />
    </div>
  );
};

export default TestPage;
