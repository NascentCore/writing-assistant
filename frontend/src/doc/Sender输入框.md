用于聊天的输入框组件。

## 何时使用

- 需要构建一个对话场景下的输入框

#### 基本用法：

基础用法，受控进行状态管理。

```tsx
import { Sender } from '@ant-design/x';
import { App, Flex } from 'antd';
import React, { useState } from 'react';

const Demo: React.FC = () => {
  const [value, setValue] = useState<string>('Hello? this is X!');
  const [loading, setLoading] = useState<boolean>(false);

  const { message } = App.useApp();

  // Mock send message
  React.useEffect(() => {
    if (loading) {
      const timer = setTimeout(() => {
        setLoading(false);
        message.success('Send message successfully!');
      }, 3000);
      return () => {
        clearTimeout(timer);
      };
    }
  }, [loading]);

  return (
    <Flex vertical gap="middle">
      <Sender
        loading={loading}
        value={value}
        onChange={(v) => {
          setValue(v);
        }}
        onSubmit={() => {
          setValue('');
          setLoading(true);
          message.info('Send message!');
        }}
        onCancel={() => {
          setLoading(false);
          message.error('Cancel sending!');
        }}
      />
      <Sender value="Force as loading" loading readOnly />
      <Sender disabled value="Set to disabled" />
    </Flex>
  );
};

export default () => (
  <App>
    <Demo />
  </App>
);
```

#### 提交模式：

通过 `submitType` 控制换行与提交模式。

```tsx
import React from 'react';
import { Sender } from '@ant-design/x';
import { App } from 'antd';

const Demo: React.FC = () => {
  const { message } = App.useApp();

  return (
    <Sender
      submitType="shiftEnter"
      placeholder="Press Shift + Enter to send message"
      onSubmit={() => {
        message.success('Send message successfully!');
      }}
    />
  );
};

export default () => (
  <App>
    <Demo />
  </App>
);
```

#### 自定义语音输入：

自定义语音逻辑，从而实现调用三方库的语音识别功能。

```tsx
import { Sender } from '@ant-design/x';
import { App } from 'antd';
import React from 'react';

const Demo: React.FC = () => {
  const { message } = App.useApp();
  const [recording, setRecording] = React.useState(false);

  return (
    <Sender
      onSubmit={() => {
        message.success('Send message successfully!');
      }}
      allowSpeech={{
        // When setting `recording`, the built-in speech recognition feature will be disabled
        recording,
        onRecordingChange: (nextRecording) => {
          message.info(`Mock Customize Recording: ${nextRecording}`);
          setRecording(nextRecording);
        },
      }}
    />
  );
};

export default () => (
  <App>
    <Demo />
  </App>
);
```

#### 自定义按钮：

通过 `actions` 属性，可以自定义发送按钮的行为。

```tsx
import { OpenAIOutlined } from '@ant-design/icons';
import { Sender } from '@ant-design/x';
import { App, Space, Spin, Typography } from 'antd';
import React from 'react';

const Demo: React.FC = () => {
  const [loading, setLoading] = React.useState(false);
  const [value, setValue] = React.useState<string>('');

  const { message } = App.useApp();

  React.useEffect(() => {
    if (loading) {
      const timer = setTimeout(() => {
        setLoading(false);
        setValue('');
        message.success('Send message successfully!');
      }, 2000);
      return () => {
        clearTimeout(timer);
      };
    }
  }, [loading]);

  return (
    <Sender
      submitType="shiftEnter"
      value={value}
      loading={loading}
      onChange={setValue}
      onSubmit={() => {
        setLoading(true);
      }}
      onCancel={() => {
        setLoading(false);
      }}
      actions={(_, info) => {
        const { SendButton, LoadingButton, ClearButton } = info.components;

        return (
          <Space size="small">
            <Typography.Text type="secondary">
              <small>`Shift + Enter` to submit</small>
            </Typography.Text>
            <ClearButton />
            {loading ? (
              <LoadingButton
                type="default"
                icon={<Spin size="small" />}
                disabled
              />
            ) : (
              <SendButton
                type="primary"
                icon={<OpenAIOutlined />}
                disabled={false}
              />
            )}
          </Space>
        );
      }}
    />
  );
};

export default () => (
  <App>
    <Demo />
  </App>
);
```

#### 展开面板：

使用 `header` 自定义文件上传示例。

```tsx
import { CloudUploadOutlined, LinkOutlined } from '@ant-design/icons';
import { Sender } from '@ant-design/x';
import { App, Button, Flex, Typography, theme } from 'antd';
import React from 'react';

const Demo: React.FC = () => {
  const { message } = App.useApp();
  const { token } = theme.useToken();

  const [open, setOpen] = React.useState(false);

  const headerNode = (
    <Sender.Header title="Upload Sample" open={open} onOpenChange={setOpen}>
      <Flex
        vertical
        align="center"
        gap="small"
        style={{ marginBlock: token.paddingLG }}
      >
        <CloudUploadOutlined style={{ fontSize: '4em' }} />
        <Typography.Title level={5} style={{ margin: 0 }}>
          Drag file here (just demo)
        </Typography.Title>
        <Typography.Text type="secondary">
          Support pdf, doc, xlsx, ppt, txt, image file types
        </Typography.Text>
        <Button
          onClick={() => {
            message.info('Mock select file');
          }}
        >
          Select File
        </Button>
      </Flex>
    </Sender.Header>
  );

  return (
    <Flex style={{ height: 350 }} align="end">
      <Sender
        header={headerNode}
        prefix={
          <Button
            type="text"
            icon={<LinkOutlined />}
            onClick={() => {
              setOpen(!open);
            }}
          />
        }
        placeholder="← Click to open"
        onSubmit={() => {
          message.success('Send message successfully!');
        }}
      />
    </Flex>
  );
};

export default () => (
  <App>
    <Demo />
  </App>
);
```

#### 引用：

使用 `header` 做引用效果。

```tsx
import { EnterOutlined } from '@ant-design/icons';
import { Sender } from '@ant-design/x';
import { App, Flex, Space, Switch, Typography } from 'antd';
import React from 'react';

const Demo: React.FC = () => {
  const { message } = App.useApp();
  const [hasRef, setHasRef] = React.useState(true);

  const headerNode = (
    <Sender.Header
      open={hasRef}
      title={
        <Space>
          <EnterOutlined />
          <Typography.Text type="secondary">
            "Tell more about Ant Design X"
          </Typography.Text>
        </Space>
      }
      onOpenChange={setHasRef}
    />
  );

  return (
    <Flex vertical gap="middle" align="flex-start">
      <Switch
        checked={hasRef}
        onChange={() => setHasRef(!hasRef)}
        checkedChildren="With Reference"
        unCheckedChildren="With Reference"
      />
      <Sender
        header={headerNode}
        onSubmit={() => {
          message.success('Send message successfully!');
        }}
      />
    </Flex>
  );
};

export default () => (
  <App>
    <Demo />
  </App>
);
```

#### 调整样式：

通过 `actions` 属性，调整默认样式。

```tsx
import { SendOutlined } from '@ant-design/icons';
import { Sender } from '@ant-design/x';
import { App, type ButtonProps, Flex, Tooltip } from 'antd';
import React from 'react';

const Demo: React.FC = () => {
  const [value, setValue] = React.useState('Ask something?');
  const [loading, setLoading] = React.useState(false);

  const { message } = App.useApp();

  React.useEffect(() => {
    if (loading) {
      const timer = setTimeout(() => {
        setLoading(false);
      }, 3000);

      return () => {
        clearTimeout(timer);
      };
    }
  }, [loading]);

  const renderSend = (
    props: ButtonProps & { ignoreLoading?: boolean; placeholder?: string } = {},
  ) => {
    const { ignoreLoading, placeholder, ...btnProps } = props;

    return (
      <Sender
        value={value}
        onChange={setValue}
        loading={loading}
        onSubmit={(msg) => {
          message.success(`Send: ${msg}`);
          setValue('');
          setLoading(true);
        }}
        placeholder={placeholder}
        onCancel={() => {
          setLoading(false);
        }}
        actions={(_, info) => {
          const { SendButton, LoadingButton } = info.components;

          if (!ignoreLoading && loading) {
            return (
              <Tooltip title="Click to cancel">
                <LoadingButton />
              </Tooltip>
            );
          }

          let node = <SendButton {...btnProps} />;

          if (!ignoreLoading) {
            node = (
              <Tooltip title={value ? 'Send \u21B5' : 'Please type something'}>
                {node}
              </Tooltip>
            );
          }

          return node;
        }}
      />
    );
  };

  return (
    <Flex vertical gap="middle">
      {renderSend({
        shape: 'default',
        placeholder: 'Change button border radius',
        style: { borderRadius: 12 },
      })}
      {renderSend({
        variant: 'text',
        placeholder: 'Change button icon',
        color: 'primary',
        icon: <SendOutlined />,
        shape: 'default',
      })}
      {renderSend({
        ignoreLoading: true,
        placeholder: 'Loading not change button',
      })}
    </Flex>
  );
};

export default () => (
  <App>
    <Demo />
  </App>
);
```

#### 黏贴图片：

配合 Attachments 进行黏贴文件上传。

```tsx
import { CloudUploadOutlined, LinkOutlined } from '@ant-design/icons';
import { Attachments, AttachmentsProps, Sender } from '@ant-design/x';
import { App, Button, Flex, type GetProp, type GetRef } from 'antd';
import React from 'react';

const Demo = () => {
  const [open, setOpen] = React.useState(false);
  const [items, setItems] = React.useState<GetProp<AttachmentsProps, 'items'>>(
    [],
  );
  const [text, setText] = React.useState('');

  const attachmentsRef = React.useRef<GetRef<typeof Attachments>>(null);

  const senderRef = React.useRef<GetRef<typeof Sender>>(null);

  const senderHeader = (
    <Sender.Header
      title="Attachments"
      styles={{
        content: {
          padding: 0,
        },
      }}
      open={open}
      onOpenChange={setOpen}
      forceRender
    >
      <Attachments
        ref={attachmentsRef}
        // Mock not real upload file
        beforeUpload={() => false}
        items={items}
        onChange={({ fileList }) => setItems(fileList)}
        placeholder={(type) =>
          type === 'drop'
            ? {
                title: 'Drop file here',
              }
            : {
                icon: <CloudUploadOutlined />,
                title: 'Upload files',
                description: 'Click or drag files to this area to upload',
              }
        }
        getDropContainer={() => senderRef.current?.nativeElement}
      />
    </Sender.Header>
  );

  return (
    <Flex style={{ height: 220 }} align="end">
      <Sender
        ref={senderRef}
        header={senderHeader}
        prefix={
          <Button
            type="text"
            icon={<LinkOutlined />}
            onClick={() => {
              setOpen(!open);
            }}
          />
        }
        value={text}
        onChange={setText}
        onPasteFile={(file) => {
          attachmentsRef.current?.upload(file);
          setOpen(true);
        }}
        onSubmit={() => {
          setItems([]);
          setText('');
        }}
      />
    </Flex>
  );
};

export default () => (
  <App>
    <Demo />
  </App>
);
```

#### 聚焦：

使用 `ref` 选项控制聚焦。

```tsx
import { Sender } from '@ant-design/x';
import { Button, Flex, type GetRef } from 'antd';
import React, { useRef } from 'react';

const App: React.FC = () => {
  const senderRef = useRef<GetRef<typeof Sender>>(null);

  const senderProps = {
    defaultValue: 'Hello, welcome to use Ant Design X!',
    ref: senderRef,
  };

  return (
    <Flex wrap gap={12}>
      <Button
        onClick={() => {
          senderRef.current!.focus({
            cursor: 'start',
          });
        }}
      >
        Focus at first
      </Button>
      <Button
        onClick={() => {
          senderRef.current!.focus({
            cursor: 'end',
          });
        }}
      >
        Focus at last
      </Button>
      <Button
        onClick={() => {
          senderRef.current!.focus({
            cursor: 'all',
          });
        }}
      >
        Focus to select all
      </Button>
      <Button
        onClick={() => {
          senderRef.current!.focus({
            preventScroll: true,
          });
        }}
      >
        Focus prevent scroll
      </Button>
      <Button
        onClick={() => {
          senderRef.current!.blur();
        }}
      >
        Blur
      </Button>
      <Sender {...senderProps} />
    </Flex>
  );
};

export default App;
```

##

API

### SenderProps

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| **属性** | **说明** | **类型** | **默认值** | **版本** |
| **actions** | 自定义按钮 | ReactNode \| (oriNode, info: { components }) => ReactNode | - | - |
| **allowSpeech** | 是否允许语音输入 | boolean \| SpeechConfig | false | - |
| **classNames** | 样式类名 |  | - | - |
| **components** | 自定义组件 | Record<'input', ComponentType> | - | - |
| **defaultValue** | 输入框默认值 | string | - | - |
| **disabled** | 是否禁用 | boolean | false | - |
| **loading** | 是否加载中 | boolean | false | - |
| **header** | 头部面板 | ReactNode | - | - |
| **prefix** | 前缀内容 | ReactNode | - | - |
| **readOnly** | 是否让输入框只读 | boolean | false | - |
| **rootClassName** | 根元素样式类 | string | - | - |
| **styles** | 语义化定义样式 |  | - | - |
| **submitType** | 提交模式 | SubmitType | `enter`<br><br>\| `shiftEnter` | - |
| **value** | 输入框值 | string | - | - |
| **onSubmit** | 点击发送按钮的回调 | (message: string) => void | - | - |
| **onChange** | 输入框值改变的回调 | (value: string, event?: React.FormEvent<`HTMLTextAreaElement`<br><br>> \| React.ChangeEvent<`HTMLTextAreaElement`<br><br>> ) => void | - | - |
| **onCancel** | 点击取消按钮的回调 | () => void | - | - |

```ts
type SpeechConfig = {
  // 当设置 `recording` 时，内置的语音输入功能将会被禁用。
  // 交由开发者实现三方语音输入的功能。
  recording?: boolean;
  onRecordingChange?: (recording: boolean) => void;
};
```

#### Sender Ref

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| **属性** | **说明** | **类型** | **默认值** | **版本** |
| **nativeElement** | 外层容器 | `HTMLDivElement` | - | - |
| **focus** | 获取焦点 | (option?: { preventScroll?: boolean, cursor?: 'start' \| 'end' \| 'all' }) | - | - |
| **blur** | 取消焦点 | () => void | - | - |

### Sender.Header

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| **属性** | **说明** | **类型** | **默认值** | **版本** |
| **children** | 面板内容 | ReactNode | - | - |
| **closable** | 是否可关闭 | boolean | true | - |
| **forceRender** | 强制渲染，在初始化便需要 ref 内部元素时使用 | boolean | false | - |
| **open** | 是否展开 | boolean | - | - |
| **title** | 标题 | ReactNode | - | - |
| **onOpenChange** | 展开状态改变的回调 | (open: boolean) => void | - | - |
