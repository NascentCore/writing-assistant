用于展示一组附件信息集合。

## 何时使用

Attachments 组件用于需要展示一组附件信息集合的场景。

#### 基本

基础用法，可以通过 `getDropContainer` 支持拖拽上传。

```tsx
import { CloudUploadOutlined, LinkOutlined } from '@ant-design/icons';
import { Attachments, Sender } from '@ant-design/x';
import { App, Button, Flex, Switch } from 'antd';
import React from 'react';

const Demo = () => {
  const { message } = App.useApp();

  const [fullScreenDrop, setFullScreenDrop] = React.useState(false);
  const divRef = React.useRef<HTMLDivElement>(null);

  return (
    <Flex vertical gap="middle" align="flex-start" ref={divRef}>
      <Sender
        prefix={
          <Attachments
            beforeUpload={() => false}
            onChange={({ file }) => {
              message.info(`Mock upload: ${file.name}`);
            }}
            getDropContainer={() =>
              fullScreenDrop ? document.body : divRef.current
            }
            placeholder={{
              icon: <CloudUploadOutlined />,
              title: 'Drag & Drop files here',
              description:
                'Support file type: image, video, audio, document, etc.',
            }}
          >
            <Button type="text" icon={<LinkOutlined />} />
          </Attachments>
        }
      />

      <Switch
        checked={fullScreenDrop}
        onChange={setFullScreenDrop}
        checkedChildren="Full screen drop"
        unCheckedChildren="Full screen drop"
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

#### 占位信息

修改占位信息。

```tsx
import { CloudUploadOutlined } from '@ant-design/icons';
import { Attachments, type AttachmentsProps } from '@ant-design/x';
import { Button, Flex, GetProp, Result, theme } from 'antd';
import React from 'react';

const presetFiles: AttachmentsProps['items'] = [
  {
    uid: '1',
    name: 'uploading file.xlsx',
    status: 'uploading',
    url: 'http://www.baidu.com/xxx.png',
    percent: 93,
  },
  {
    uid: '2',
    name: 'uploaded file.docx',
    status: 'done',
    size: 123456,
    description: 'Customize description',
    url: 'http://www.baidu.com/yyy.png',
  },
  {
    uid: '3',
    name: 'upload error with long text file name.zip',
    status: 'error',
    response: 'Server Error 500', // custom error message to show
    url: 'http://www.baidu.com/zzz.png',
  },
  {
    uid: '4',
    name: 'image uploading preview.png',
    status: 'uploading',
    percent: 33,
    thumbUrl:
      'https://zos.alipayobjects.com/rmsportal/jkjgkEfvpUPVyRjUImniVslZfWPnJuuZ.png',
    url: 'https://zos.alipayobjects.com/rmsportal/jkjgkEfvpUPVyRjUImniVslZfWPnJuuZ.png',
  },
  {
    uid: '5',
    name: 'image done preview.png',
    status: 'done',
    size: 123456,
    thumbUrl:
      'https://zos.alipayobjects.com/rmsportal/jkjgkEfvpUPVyRjUImniVslZfWPnJuuZ.png',
    url: 'https://zos.alipayobjects.com/rmsportal/jkjgkEfvpUPVyRjUImniVslZfWPnJuuZ.png',
  },
  {
    uid: '6',
    name: 'image error preview.png',
    status: 'error',
    response: 'Server Error 500', // custom error message to show
    thumbUrl:
      'https://zos.alipayobjects.com/rmsportal/jkjgkEfvpUPVyRjUImniVslZfWPnJuuZ.png',
    url: 'https://zos.alipayobjects.com/rmsportal/jkjgkEfvpUPVyRjUImniVslZfWPnJuuZ.png',
  },
];

type ExtractFunc<T> = T extends (...args: any) => any ? T : never;

const getPlaceholderFn = (
  inlinePlaceholder: ReturnType<ExtractFunc<AttachmentsProps['placeholder']>>,
) => {
  return (type: 'inline' | 'drop') =>
    type === 'drop'
      ? {
          title: 'Drop file here',
        }
      : inlinePlaceholder;
};

const Demo = () => {
  const { token } = theme.useToken();

  const [items, setItems] = React.useState<GetProp<AttachmentsProps, 'items'>>(
    [],
  );

  const sharedBorderStyle: React.CSSProperties = {
    borderRadius: token.borderRadius,
    overflow: 'hidden',
    background: token.colorBgContainer,
  };

  const sharedAttachmentProps: AttachmentsProps = {
    beforeUpload: () => false,
    items,
    onChange: ({ fileList }) => {
      console.log('onChange:', fileList);
      setItems(fileList);
    },
  };

  return (
    <Flex
      vertical
      gap="middle"
      style={{
        padding: token.padding,
        background: token.colorBgContainerDisabled,
      }}
    >
      <div style={sharedBorderStyle}>
        <Attachments
          {...sharedAttachmentProps}
          placeholder={getPlaceholderFn({
            icon: <CloudUploadOutlined />,
            title: 'Click or Drop files here',
            description:
              'Support file type: image, video, audio, document, etc.',
          })}
        />
      </div>

      <div style={sharedBorderStyle}>
        <Attachments
          {...sharedAttachmentProps}
          placeholder={getPlaceholderFn(
            <Result
              title="Custom Placeholder Node"
              icon={<CloudUploadOutlined />}
              extra={<Button type="primary">Do Upload</Button>}
              style={{ padding: 0 }}
            />,
          )}
        />
      </div>

      <Flex gap="middle">
        <Button
          style={{ flex: '1 1 50%' }}
          disabled={!!items.length}
          type="primary"
          onClick={() => setItems(presetFiles)}
        >
          Fill Files
        </Button>
        <Button
          style={{ flex: '1 1 50%' }}
          disabled={!items.length}
          onClick={() => setItems([])}
        >
          Reset Files
        </Button>
      </Flex>
    </Flex>
  );
};

export default Demo;
```

#### 超出样式

控制附件超出区域长度时的展示方式。

```tsx
import { CloudUploadOutlined } from '@ant-design/icons';
import { Attachments, type AttachmentsProps } from '@ant-design/x';
import { Flex, GetProp, Segmented, Switch } from 'antd';
import React from 'react';

const presetFiles: AttachmentsProps['items'] = Array.from({ length: 30 }).map(
  (_, index) => ({
    uid: String(index),
    name: `file-${index}.jpg`,
    status: 'done',
    thumbUrl:
      'https://zos.alipayobjects.com/rmsportal/jkjgkEfvpUPVyRjUImniVslZfWPnJuuZ.png',
    url: 'https://zos.alipayobjects.com/rmsportal/jkjgkEfvpUPVyRjUImniVslZfWPnJuuZ.png',
  }),
);

const Demo = () => {
  const [overflow, setOverflow] =
    React.useState<AttachmentsProps['overflow']>('wrap');
  const [items, setItems] =
    React.useState<GetProp<AttachmentsProps, 'items'>>(presetFiles);
  const [disabled, setDisabled] = React.useState(false);

  return (
    <Flex vertical gap="middle">
      <Flex gap="middle" align="center">
        <Segmented
          options={[
            { value: 'wrap', label: 'Wrap' },
            { value: 'scrollX', label: 'Scroll X' },
            { value: 'scrollY', label: 'Scroll Y' },
          ]}
          value={overflow}
          onChange={setOverflow}
          style={{ marginInlineEnd: 'auto' }}
        />
        <Switch
          checked={items.length !== 0}
          onChange={() => setItems((prev) => (prev.length ? [] : presetFiles))}
          checkedChildren="Data"
          unCheckedChildren="Data"
        />
        <Switch
          checked={disabled}
          onChange={setDisabled}
          checkedChildren="Disabled"
          unCheckedChildren="Disabled"
        />
      </Flex>
      <Attachments
        overflow={overflow}
        items={items}
        onChange={(info) => setItems(info.fileList)}
        beforeUpload={() => false}
        placeholder={{
          icon: <CloudUploadOutlined />,
          title: 'Click or Drop files here',
          description: 'Support file type: image, video, audio, document, etc.',
        }}
        disabled={disabled}
      />
    </Flex>
  );
};

export default Demo;
```

#### 组合示例

配合 Sender.Header 使用，在对话中插入附件。

```tsx
import { CloudUploadOutlined, LinkOutlined } from '@ant-design/icons';
import { Attachments, AttachmentsProps, Sender } from '@ant-design/x';
import {
  App,
  Badge,
  Button,
  Flex,
  type GetProp,
  type GetRef,
  Typography,
} from 'antd';
import React from 'react';

const Demo = () => {
  const [open, setOpen] = React.useState(true);
  const [items, setItems] = React.useState<GetProp<AttachmentsProps, 'items'>>(
    [],
  );
  const [text, setText] = React.useState('');

  const { notification } = App.useApp();

  const senderRef = React.useRef<GetRef<typeof Sender>>(null);

  const senderHeader = (
    <Sender.Header
      title="Attachments"
      open={open}
      onOpenChange={setOpen}
      styles={{
        content: {
          padding: 0,
        },
      }}
    >
      <Attachments
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
    <Flex style={{ minHeight: 250 }} align="flex-end">
      <Sender
        ref={senderRef}
        header={senderHeader}
        prefix={
          <Badge dot={items.length > 0 && !open}>
            <Button onClick={() => setOpen(!open)} icon={<LinkOutlined />} />
          </Badge>
        }
        value={text}
        onChange={setText}
        onSubmit={() => {
          notification.info({
            message: 'Mock Submit',
            description: (
              <Typography>
                <ul>
                  <li>You said: {text}</li>
                  <li>
                    Attachments count: {items.length}
                    <ul>
                      {items.map((item) => (
                        <li key={item.uid}>{item.name}</li>
                      ))}
                    </ul>
                  </li>
                </ul>
              </Typography>
            ),
          });

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

#### 文件卡片

单独的文件卡片，用于一些展示场景。

```tsx
import { Attachments } from '@ant-design/x';
import { App, Flex } from 'antd';
import React from 'react';

const Demo = () => {
  const filesList = [
    {
      uid: '1',
      name: 'excel-file.xlsx',
      size: 111111,
    },
    {
      uid: '2',
      name: 'word-file.docx',
      size: 222222,
    },
    {
      uid: '3',
      name: 'image-file.png',
      size: 333333,
    },
    {
      uid: '4',
      name: 'pdf-file.pdf',
      size: 444444,
    },
    {
      uid: '5',
      name: 'ppt-file.pptx',
      size: 555555,
    },
    {
      uid: '6',
      name: 'video-file.mp4',
      size: 666666,
    },
    {
      uid: '7',
      name: 'audio-file.mp3',
      size: 777777,
    },
    {
      uid: '8',
      name: 'zip-file.zip',
      size: 888888,
    },
    {
      uid: '9',
      name: 'markdown-file.md',
      size: 999999,
      description: 'Custom description here',
    },
    {
      uid: '10',
      name: 'image-file.png',
      thumbUrl:
        'https://zos.alipayobjects.com/rmsportal/jkjgkEfvpUPVyRjUImniVslZfWPnJuuZ.png',
      url: 'https://zos.alipayobjects.com/rmsportal/jkjgkEfvpUPVyRjUImniVslZfWPnJuuZ.png',
      size: 123456,
    },
  ];

  return (
    <Flex vertical gap="middle">
      {filesList.map((file, index) => (
        <Attachments.FileCard key={index} item={file} />
      ))}
    </Flex>
  );
};

export default () => (
  <App>
    <Demo />
  </App>
);
```

### AttachmentsProps

继承 antd [Upload](https://ant.design/components/upload) 属性。

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| **属性** | **说明** | **类型** | **默认值** | **版本** |
| **classNames** | 自定义样式类名，[见下](https://x.ant.design/components/attachments-cn#semantic-dom) | Record<string, string> | - | - |
| **disabled** | 是否禁用 | boolean | false | - |
| **getDropContainer** | 设置拖拽时，可以释放文件的区域 | () => HTMLElement | - | - |
| **items** | 附件列表，同 Upload `fileList` | Attachment[] | - | - |
| **overflow** | 文件列表超出时样式 | 'wrap' \| 'scrollX' \| 'scrollY' | - | - |
| **placeholder** | 没有文件时的占位信息 | PlaceholderType \| ((type: 'inline' \| 'drop') => PlaceholderType) | - | - |
| **rootClassName** | 根节点的样式类名 | string | - | - |
| **rootStyle** | 根节点的样式对象 | React.CSSProperties | - | - |
| **styles** | 自定义样式对象，[见下](https://x.ant.design/components/attachments-cn#semantic-dom) | Record<string, React.CSSProperties> | - | - |

```ts
interface PlaceholderType {
  icon?: React.ReactNode;

  title?: React.ReactNode;

  description?: React.ReactNode;
}
```

### AttachmentsRef

|                   |                  |                      |          |
| ----------------- | ---------------- | -------------------- | -------- |
| **属性**          | **说明**         | **类型**             | **版本** |
| **nativeElement** | 获取原生节点     | HTMLElement          | -        |
| **upload**        | 手工调用上传文件 | (file: File) => void | -        |

### Attachments.FileCard Props

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| **属性** | **说明** | **类型** | **默认值** | **版本** |
| **prefixCls** | 样式类名的前缀 | string | - | - |
| **className** | 样式类名 | string | - | - |
| **style** | 样式对象 | React.CSSProperties | - | - |
| **item** | 附件，同 Upload `UploadFile` | Attachment | - | - |
| **onRemove** | 附件移除时的回调函数 | (item: Attachment) => void | - | - |
