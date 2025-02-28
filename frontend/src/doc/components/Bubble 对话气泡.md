用于聊天的气泡组件。

## 何时使用

常用于聊天的时候。

## 代码演示

#### 基本

基础用法

```tsx
import React from 'react';
import { Bubble } from '@ant-design/x';

const App = () => <Bubble content="hello world !" />;

export default App;
```

#### 支持位置和头像

通过 `avatar` 设置自定义头像，通过 `placement` 设置位置，提供了 `start`、`end` 两个选项。

```tsx
import React from 'react';
import { UserOutlined } from '@ant-design/icons';
import { Flex } from 'antd';
import { Bubble } from '@ant-design/x';

const fooAvatar: React.CSSProperties = {
  color: '#f56a00',
  backgroundColor: '#fde3cf',
};

const barAvatar: React.CSSProperties = {
  color: '#fff',
  backgroundColor: '#87d068',
};

const hideAvatar: React.CSSProperties = {
  visibility: 'hidden',
};

const App: React.FC = () => (
  <Flex gap="middle" vertical>
    <Bubble
      placement="start"
      content="Good morning, how are you?"
      avatar={{ icon: <UserOutlined />, style: fooAvatar }}
    />
    <Bubble
      placement="start"
      content="What a beautiful day!"
      styles={{ avatar: hideAvatar }}
      avatar={{}}
    />
    <Bubble
      placement="end"
      content="Hi, good morning, I'm fine!"
      avatar={{ icon: <UserOutlined />, style: barAvatar }}
    />
    <Bubble
      placement="end"
      content="Thank you!"
      styles={{ avatar: hideAvatar }}
      avatar={{}}
    />
  </Flex>
);

export default App;
```

#### 头和尾

通过 `header` 和 `footer` 属性设置气泡的头部和底部。

```tsx
import { CopyOutlined, SyncOutlined, UserOutlined } from '@ant-design/icons';
import { Bubble } from '@ant-design/x';
import { Button, Space, theme } from 'antd';
import React from 'react';

const App: React.FC = () => {
  const { token } = theme.useToken();

  return (
    <Bubble
      content="Hello, welcome to use Ant Design X! Just ask if you have any questions."
      avatar={{ icon: <UserOutlined /> }}
      header="Ant Design X"
      footer={
        <Space size={token.paddingXXS}>
          <Button
            color="default"
            variant="text"
            size="small"
            icon={<SyncOutlined />}
          />
          <Button
            color="default"
            variant="text"
            size="small"
            icon={<CopyOutlined />}
          />
        </Space>
      }
    />
  );
};

export default App;
```

#### 加载中

通过 `loading` 属性控制加载状态。

```tsx
import React from 'react';
import { UserOutlined } from '@ant-design/icons';
import { Flex, Switch } from 'antd';
import { Bubble } from '@ant-design/x';

const App: React.FC = () => {
  const [loading, setLoading] = React.useState<boolean>(true);
  return (
    <Flex gap="large" vertical>
      <Bubble
        loading={loading}
        content="hello world !"
        avatar={{ icon: <UserOutlined /> }}
      />
      <Flex gap="large" wrap>
        Loading state:
        <Switch checked={loading} onChange={setLoading} />
      </Flex>
    </Flex>
  );
};

export default App;
```

#### 打字效果

通过设置 `typing` 属性，开启打字效果。更新 `content` 如果是之前的子集，则会继续输出，否则会重新输出。

```tsx
import { UserOutlined } from '@ant-design/icons';
import { Bubble } from '@ant-design/x';
import { Button, Flex } from 'antd';
import React from 'react';

const text = 'Ant Design X love you! ';

const App = () => {
  const [repeat, setRepeat] = React.useState(1);

  return (
    <Flex vertical gap="small">
      <Bubble
        content={text.repeat(repeat)}
        typing={{ step: 2, interval: 50 }}
        avatar={{ icon: <UserOutlined /> }}
      />
      <Bubble
        content={text.repeat(repeat)}
        typing={{ step: 2, interval: 50, suffix: <>💗</> }}
        avatar={{ icon: <UserOutlined /> }}
      />

      <Button
        style={{ alignSelf: 'flex-end' }}
        onClick={() => {
          setRepeat((ori) => (ori < 5 ? ori + 1 : 1));
        }}
      >
        Repeat {repeat} Times
      </Button>
    </Flex>
  );
};

export default App;
```

#### 自定义渲染

配合 `markdown-it` 实现自定义渲染内容。

```tsx
import { UserOutlined } from '@ant-design/icons';
import { Bubble } from '@ant-design/x';
import type { BubbleProps } from '@ant-design/x';
import { Typography } from 'antd';
import markdownit from 'markdown-it';
/* eslint-disable react/no-danger */
import React from 'react';

const md = markdownit({ html: true, breaks: true });

const text = `
> Render as markdown content to show rich text!

Link: [Ant Design X](https://x.ant.design)
`.trim();

const renderMarkdown: BubbleProps['messageRender'] = (content) => (
  <Typography>
    {/* biome-ignore lint/security/noDangerouslySetInnerHtml: used in demo */}
    <div dangerouslySetInnerHTML={{ __html: md.render(content) }} />
  </Typography>
);

const App = () => {
  const [renderKey, setRenderKey] = React.useState(0);

  React.useEffect(() => {
    const id = setTimeout(() => {
      setRenderKey((prev) => prev + 1);
    }, text.length * 100 + 2000);

    return () => {
      clearTimeout(id);
    };
  }, [renderKey]);

  return (
    <div style={{ height: 100 }} key={renderKey}>
      <Bubble
        typing
        content={text}
        messageRender={renderMarkdown}
        avatar={{ icon: <UserOutlined /> }}
      />
    </div>
  );
};

export default App;
```

#### 变体

通过 `variant` 属性设置气泡的样式变体。

```tsx
import {
  CoffeeOutlined,
  FireOutlined,
  SmileOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Bubble, Prompts, PromptsProps } from '@ant-design/x';
import { Flex } from 'antd';
import React from 'react';

const items: PromptsProps['items'] = [
  {
    key: '6',
    icon: <CoffeeOutlined style={{ color: '#964B00' }} />,
    description: 'How to rest effectively after long hours of work?',
  },
  {
    key: '7',
    icon: <SmileOutlined style={{ color: '#FAAD14' }} />,
    description: 'What are the secrets to maintaining a positive mindset?',
  },
  {
    key: '8',
    icon: <FireOutlined style={{ color: '#FF4D4F' }} />,
    description: 'How to stay calm under immense pressure?',
  },
];

const App = () => (
  <Flex vertical gap="middle">
    <Bubble
      variant="filled"
      avatar={{ icon: <UserOutlined /> }}
      content="variant: filled"
    />
    <Bubble
      variant="outlined"
      avatar={{ icon: <UserOutlined /> }}
      content="variant: outlined"
    />
    <Bubble
      variant="shadow"
      avatar={{ icon: <UserOutlined /> }}
      content="variant: shadow"
    />
    <Bubble
      variant="borderless"
      avatar={{ icon: <UserOutlined /> }}
      content={
        <Prompts
          title="variant: borderless to customize"
          items={items}
          vertical
        />
      }
    />
  </Flex>
);

export default App;
```

#### 形状

通过 `shape` 属性设置气泡的形状。

```tsx
import { Bubble, type BubbleProps } from '@ant-design/x';
import { Flex } from 'antd';
import React from 'react';

const sharedLongTextProps: BubbleProps = {
  placement: 'end',
  content:
    'This is a long text message to show the multiline view of the bubble component. '.repeat(
      3,
    ),
  styles: { content: { maxWidth: 500 } },
};

const App = () => (
  <Flex gap="middle" vertical>
    <Bubble content="shape: default" />
    <Bubble {...sharedLongTextProps} />
    <Bubble content="shape: round" shape="round" />
    <Bubble {...sharedLongTextProps} shape="round" />
    <Bubble content="shape: corner" shape="corner" />
    <Bubble {...sharedLongTextProps} shape="corner" />
  </Flex>
);

export default App;
```

#### 气泡列表

预设样式的气泡列表，支持自动滚动。使用 `roles` 设置气泡默认属性。

```tsx
import React from 'react';
import { UserOutlined } from '@ant-design/icons';
import { Bubble } from '@ant-design/x';
import { Button, Flex } from 'antd';
import type { GetProp, GetRef } from 'antd';

const roles: GetProp<typeof Bubble.List, 'roles'> = {
  ai: {
    placement: 'start',
    avatar: { icon: <UserOutlined />, style: { background: '#fde3cf' } },
    typing: { step: 5, interval: 20 },
    style: {
      maxWidth: 600,
    },
  },
  user: {
    placement: 'end',
    avatar: { icon: <UserOutlined />, style: { background: '#87d068' } },
  },
};

const App = () => {
  const [count, setCount] = React.useState(3);
  const listRef = React.useRef<GetRef<typeof Bubble.List>>(null);

  return (
    <Flex vertical gap="small">
      <Flex gap="small" style={{ alignSelf: 'flex-end' }}>
        <Button
          onClick={() => {
            setCount((i) => i + 1);
          }}
        >
          Add Bubble
        </Button>

        <Button
          onClick={() => {
            listRef.current?.scrollTo({ key: 0, block: 'nearest' });
          }}
        >
          Scroll To First
        </Button>
      </Flex>

      <Bubble.List
        ref={listRef}
        style={{ maxHeight: 300 }}
        roles={roles}
        items={Array.from({ length: count }).map((_, i) => {
          const isAI = !!(i % 2);
          const content = isAI
            ? 'Mock AI content. '.repeat(20)
            : 'Mock user content.';

          return {
            key: i,
            role: isAI ? 'ai' : 'user',
            content,
          };
        })}
      />
    </Flex>
  );
};

export default App;
```

#### 语义化自定义

示例通过语义化以及加载定制，来调整气泡效果。

```tsx
import {
  FrownOutlined,
  SmileOutlined,
  SyncOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Bubble } from '@ant-design/x';
import { Button, Flex, Space, Spin } from 'antd';
import type { GetProp, GetRef } from 'antd';
import React from 'react';

const roles: GetProp<typeof Bubble.List, 'roles'> = {
  ai: {
    placement: 'start',
    avatar: { icon: <UserOutlined />, style: { background: '#fde3cf' } },
    typing: { step: 5, interval: 20 },
    style: {
      maxWidth: 600,
      marginInlineEnd: 44,
    },
    styles: {
      footer: {
        width: '100%',
      },
    },
    loadingRender: () => (
      <Space>
        <Spin size="small" />
        Custom loading...
      </Space>
    ),
  },
  user: {
    placement: 'end',
    avatar: { icon: <UserOutlined />, style: { background: '#87d068' } },
  },
};

const App = () => {
  const listRef = React.useRef<GetRef<typeof Bubble.List>>(null);

  return (
    <Bubble.List
      ref={listRef}
      style={{ maxHeight: 300 }}
      roles={roles}
      items={[
        {
          key: 'welcome',
          role: 'ai',
          content: 'Mock welcome content. '.repeat(10),
          footer: (
            <Flex>
              <Button
                size="small"
                type="text"
                icon={<SyncOutlined />}
                style={{ marginInlineEnd: 'auto' }}
              />
              <Button size="small" type="text" icon={<SmileOutlined />} />
              <Button size="small" type="text" icon={<FrownOutlined />} />
            </Flex>
          ),
        },
        {
          key: 'ask',
          role: 'user',
          content: 'Mock user content.',
        },
        {
          key: 'ai',
          role: 'ai',
          loading: true,
        },
      ]}
    />
  );
};

export default App;
```

#### 自定义列表内容

自定义气泡列表内容，这对于个性化定制场景非常有用。

```tsx
import {
  CoffeeOutlined,
  FireOutlined,
  SmileOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Attachments, Bubble, Prompts } from '@ant-design/x';
import { Flex, GetProp, Typography } from 'antd';
import React from 'react';

const roles: GetProp<typeof Bubble.List, 'roles'> = {
  ai: {
    placement: 'start',
    typing: true,
    avatar: { icon: <UserOutlined />, style: { background: '#fde3cf' } },
  },
  suggestion: {
    placement: 'start',
    avatar: { icon: <UserOutlined />, style: { visibility: 'hidden' } },
    variant: 'borderless',
    messageRender: (items) => <Prompts vertical items={items as any} />,
  },
  file: {
    placement: 'start',
    avatar: { icon: <UserOutlined />, style: { visibility: 'hidden' } },
    variant: 'borderless',
    messageRender: (items: any) => (
      <Flex vertical gap="middle">
        {(items as any[]).map((item) => (
          <Attachments.FileCard key={item.uid} item={item} />
        ))}
      </Flex>
    ),
  },
};

const App = () => {
  return (
    <Bubble.List
      roles={roles}
      items={[
        // Normal
        {
          key: 0,
          role: 'ai',
          content: 'Normal message',
        },

        // ReactNode
        {
          key: 1,
          role: 'ai',
          content: (
            <Typography.Text type="danger">ReactNode message</Typography.Text>
          ),
        },

        // Role: suggestion
        {
          key: 2,
          role: 'suggestion',
          content: [
            {
              key: '6',
              icon: <CoffeeOutlined style={{ color: '#964B00' }} />,
              description: 'How to rest effectively after long hours of work?',
            },
            {
              key: '7',
              icon: <SmileOutlined style={{ color: '#FAAD14' }} />,
              description:
                'What are the secrets to maintaining a positive mindset?',
            },
            {
              key: '8',
              icon: <FireOutlined style={{ color: '#FF4D4F' }} />,
              description: 'How to stay calm under immense pressure?',
            },
          ],
        },
        // Role: file
        {
          key: 3,
          role: 'file',
          content: [
            {
              uid: '1',
              name: 'excel-file.xlsx',
              size: 111111,
              description: 'Checking the data',
            },
            {
              uid: '2',
              name: 'word-file.docx',
              size: 222222,
              status: 'uploading',
              percent: 23,
            },
          ],
        },
      ]}
    />
  );
};

export default App;
```

### Bubble

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| **属性** | **说明** | **类型** | **默认值** | **版本** |
| **avatar** | 展示头像 | React.ReactNode | - |  |
| **classNames** | 语义化结构 class | Record<SemanticDOM, string> | - |  |
| **content** | 聊天内容 | string | - |  |
| **footer** | 底部内容 | React.ReactNode | - |  |
| **header** | 头部内容 | React.ReactNode | - |  |
| **loading** | 聊天内容加载状态 | boolean | - |  |
| **placement** | 信息位置 | `start`<br><br>\| `end` | `start` |  |
| **shape** | 气泡形状 | `round`<br><br>\| `corner` | - |  |
| **styles** | 语义化结构 style | Record<SemanticDOM, CSSProperties> | - |  |
| **typing** | 设置聊天内容打字动画 | boolean \| { step?: number, interval?: number } | false |  |
| **variant** | 气泡样式变体 | `filled`<br><br>\| `borderless`<br><br>\| `outlined`<br><br>\| `shadow` | `filled` |  |
| **loadingRender** | 自定义渲染加载态内容 | () => ReactNode | - |  |
| **messageRender** | 自定义渲染内容 | (content?: string) => ReactNode | - |  |
| **onTypingComplete** | 打字效果完成时的回调，如果没有设置 typing 将在渲染时立刻触发 | () => void | - |  |

### Bubble.List

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| **属性** | **说明** | **类型** | **默认值** | **版本** |
| **autoScroll** | 当内容更新时，自动滚动到最新位置。如果用户滚动，则会暂停自动滚动。 | boolean | true |  |
| **items** | 气泡数据列表 | (BubbleProps & { key?: string \| number, role?: string })[] | - |  |
| **roles** | 设置气泡默认属性，`items`<br><br>中的 `role`<br><br>会进行自动对应 | Record<string, BubbleProps> \| (bubble) => BubbleProps | - |  |
