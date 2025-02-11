import { Bubble, Sender, ThoughtChain, XProvider } from '@ant-design/x';
import { Card, Flex } from 'antd';
import React from 'react';

import { UserOutlined } from '@ant-design/icons';

export default () => {
  const [value, setValue] = React.useState('');
  const [messages, setMessages] = React.useState([
    {
      key: '1',
      placement: 'end',
      content: 'Hello Ant Design X!',
      avatar: { icon: <UserOutlined /> },
    },
    {
      key: '2',
      content: 'Hello World!1',
      avatar: { icon: <UserOutlined /> },
    },
    {
      key: '3',
      placement: 'start',
      content: 'Hello World!2',
      avatar: { icon: <UserOutlined /> },
    },
  ]);

  const handleSubmit = () => {
    if (!value.trim()) return;

    // 添加用户发送的消息
    const userMessage = {
      key: Date.now().toString(),
      placement: 'end',
      content: value,
      avatar: { icon: <UserOutlined /> },
    };

    // 添加系统回复的消息
    const systemResponse = {
      key: (Date.now() + 1).toString(),
      placement: 'start',
      content: '收到消息',
      avatar: { icon: <UserOutlined /> },
    };

    setMessages([...messages, userMessage, systemResponse]);
    setValue(''); // 清空输入框
  };

  return (
    <>
      <Card>
        <XProvider>
          <Flex style={{ height: 500 }} gap={12}>
            <Flex vertical style={{ flex: 1 }} gap={8}>
              <Bubble.List style={{ flex: 1 }} items={messages} />
              <Sender
                value={value}
                onChange={(nextVal: string) => {
                  setValue(nextVal);
                }}
                onSubmit={handleSubmit}
              />
            </Flex>
          </Flex>
          <ThoughtChain />
        </XProvider>
      </Card>
    </>
  );
};
