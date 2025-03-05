用于承载用户侧发送的历史对话列表。

#### 何时使用

- 需要对多个会话进行管理
- 查看历史会话列表

#### 基本

基础用法。

```tsx
import { Conversations } from '@ant-design/x';
import type { ConversationsProps } from '@ant-design/x';
import { type GetProp, theme } from 'antd';
import React from 'react';

const items: GetProp<ConversationsProps, 'items'> = Array.from({
  length: 4,
}).map((_, index) => ({
  key: `item${index + 1}`,
  label: `Conversation Item ${index + 1}`,
  disabled: index === 3,
}));

export default () => {
  const { token } = theme.useToken();

  // Customize the style of the container
  const style = {
    width: 256,
    background: token.colorBgContainer,
    borderRadius: token.borderRadius,
  };

  return <Conversations items={items} defaultActiveKey="item1" style={style} />;
};
```

#### 会话操作

配合 `menu` 属性，配置操作菜单

```tsx
import { DeleteOutlined, EditOutlined, StopOutlined } from '@ant-design/icons';
import { Conversations } from '@ant-design/x';
import type { ConversationsProps } from '@ant-design/x';
import { App, type GetProp, theme } from 'antd';
import React from 'react';

const items: GetProp<ConversationsProps, 'items'> = Array.from({
  length: 4,
}).map((_, index) => ({
  key: `item${index + 1}`,
  label: `Conversation Item ${index + 1}`,
  disabled: index === 3,
}));

const Demo = () => {
  const { message } = App.useApp();
  const { token } = theme.useToken();

  const style = {
    width: 256,
    background: token.colorBgContainer,
    borderRadius: token.borderRadius,
  };

  const menuConfig: ConversationsProps['menu'] = (conversation) => ({
    items: [
      {
        label: 'Operation 1',
        key: 'operation1',
        icon: <EditOutlined />,
      },
      {
        label: 'Operation 2',
        key: 'operation2',
        icon: <StopOutlined />,
        disabled: true,
      },
      {
        label: 'Operation 3',
        key: 'operation3',
        icon: <DeleteOutlined />,
        danger: true,
      },
    ],
    onClick: (menuInfo) => {
      message.info(`Click ${conversation.key} - ${menuInfo.key}`);
    },
  });

  return (
    <Conversations
      defaultActiveKey="item1"
      menu={menuConfig}
      items={items}
      style={style}
    />
  );
};

export default () => (
  <App>
    <Demo />
  </App>
);
```

#### 分组排序

通过 `groupable.sort` 属性对分组排序, 通过 `groupable.title` 自定义渲染分组

```tsx
import { CommentOutlined } from '@ant-design/icons';
import type { ConversationsProps } from '@ant-design/x';
import { Conversations } from '@ant-design/x';
import { type GetProp, Space, theme } from 'antd';
import React from 'react';

const items: GetProp<ConversationsProps, 'items'> = Array.from({
  length: 6,
}).map((_, index) => {
  const timestamp = index <= 3 ? 1732204800000 : 1732204800000 - 60 * 60 * 24;

  return {
    key: `item${index + 1}`,
    label: `Conversation ${timestamp + index * 60 * 60}`,
    timestamp: timestamp + index * 60 * 60,
    group: index <= 3 ? 'Today' : 'Yesterday',
  };
});

const App = () => {
  const { token } = theme.useToken();

  // Customize the style of the container
  const style = {
    width: 256,
    background: token.colorBgContainer,
    borderRadius: token.borderRadius,
  };

  const groupable: GetProp<typeof Conversations, 'groupable'> = {
    sort(a, b) {
      if (a === b) return 0;

      return a === 'Today' ? -1 : 1;
    },
    title: (group, { components: { GroupTitle } }) =>
      group ? (
        <GroupTitle>
          <Space>
            <CommentOutlined />
            <span>{group}</span>
          </Space>
        </GroupTitle>
      ) : (
        <GroupTitle />
      ),
  };

  return (
    <Conversations
      style={style}
      groupable={groupable}
      defaultActiveKey="demo1"
      items={items}
    />
  );
};

export default App;
```

#### 滚动加载

结合 [react-infinite-scroll-component](https://github.com/ankeetmaini/react-infinite-scroll-component) 实现滚动自动加载列表。

```tsx
import { RedoOutlined } from '@ant-design/icons';
import { Conversations, type ConversationsProps } from '@ant-design/x';
import { Avatar, Divider, type GetProp, Spin, theme } from 'antd';
import React, { useEffect, useState } from 'react';
import InfiniteScroll from 'react-infinite-scroll-component';

const App: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<GetProp<ConversationsProps, 'items'>>([]);

  const { token } = theme.useToken();

  // Customize the style of the container
  const style = {
    width: 280,
    height: 600,
    background: token.colorBgContainer,
    borderRadius: token.borderRadius,
    overflow: 'scroll',
  };

  const loadMoreData = () => {
    if (loading) {
      return;
    }
    setLoading(true);
    fetch(
      'https://randomuser.me/api/?results=10&inc=name,gender,email,nat,picture&noinfo',
    )
      .then((res) => res.json())
      .then((body) => {
        const formmatedData = body.results.map((i: any) => ({
          key: i.email,
          label: `${i.name.title} ${i.name.first} ${i.name.last}`,
          icon: <Avatar src={i.picture.thumbnail} />,
          group: i.nat,
        }));

        setData([...data, ...formmatedData]);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    loadMoreData();
  }, []);

  return (
    <div id="scrollableDiv" style={style}>
      <InfiniteScroll
        dataLength={data.length}
        next={loadMoreData}
        hasMore={data.length < 50}
        loader={
          <div style={{ textAlign: 'center' }}>
            <Spin indicator={<RedoOutlined spin />} size="small" />
          </div>
        }
        endMessage={<Divider plain>It is all, nothing more 🤐</Divider>}
        scrollableTarget="scrollableDiv"
      >
        <Conversations items={data} defaultActiveKey="demo1" groupable />
      </InfiniteScroll>
    </div>
  );
};

export default App;
```

### ConversationsProps

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| **属性** | **说明** | **类型** | **默认值** | **版本** |
| **activeKey** | 当前选中的值 | string | - | - |
| **defaultActiveKey** | 默认选中值 | string | - | - |
| **items** | 会话列表数据源 | `Conversation`<br><br>[] | - | - |
| **onActiveChange** | 选中变更回调 | (value: string) => void | - | - |
| **menu** | 会话操作菜单 | MenuProps \| ((value: `Conversation`<br><br>) => MenuProps) | - | - |
| **groupable** | 是否支持分组, 开启后默认按 `Conversation.group`<br><br>字段分组 | boolean \| GroupableProps | - | - |
| **styles** | 语义化结构 style | Record<'item', React.CSSProperties> | - | - |
| **classNames** | 语义化结构 className | Record<'item', string> | - | - |

### Conversation

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| **属性** | **说明** | **类型** | **默认值** | **版本** |
| **key** | 唯一标识 | string | - | - |
| **label** | 会话名称 | React.ReactNode | - | - |
| **timestamp** | 会话时间戳 | number | - | - |
| **group** | 会话分组类型，与 `ConversationsProps.groupable`<br><br>联动 | string | - | - |
| **icon** | 会话图标 | React.ReactNode | - | - |
| **disabled** | 是否禁用 | boolean | - | - |

### GroupableProps

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| **属性** | **说明** | **类型** | **默认值** | **版本** |
| `**sort**` | 分组排序函数 | (a: string, b: string) => number | - | - |
| `**title**` | 自定义渲染组件 | ((group: string, info: { components: { GroupTitle: React.ComponentType } }) => React.ReactNode) | - | - |
