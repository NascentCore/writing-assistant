# DragSortTable - 拖动排序表格

`DragSortTable`排序采用的[dnd-kit](https://dndkit.com/)，需要提供`rowKey`来确定数据的唯一值，否则不能正常工作。

## Demo

### 拖拽排序

使用 request 获取数据源

```tsx
import { MenuOutlined } from '@ant-design/icons';
import type { ActionType, ProColumns } from '@ant-design/pro-components';
import { DragSortTable } from '@ant-design/pro-components';
import { message } from 'antd';
import { useRef, useState } from 'react';

const data = [
  {
    key: 'key1',
    name: 'John Brown',
    age: 32,
    address: 'New York No. 1 Lake Park',
  },
  {
    key: 'key2',
    name: 'Jim Green',
    age: 42,
    address: 'London No. 1 Lake Park',
  },
  {
    key: 'key3',
    name: 'Joe Black',
    age: 32,
    address: 'Sidney No. 1 Lake Park',
  },
];
const wait = async (delay = 1000) =>
  new Promise((resolve) => setTimeout(() => resolve(void 0), delay));

let remoteData = data.map((item) => ({
  ...item,
  name: `[remote data] ${item.name}`,
}));
const request = async () => {
  await wait(3000);
  return {
    data: remoteData,
    total: remoteData.length,
    success: true,
  };
};

export default () => {
  const columns: ProColumns[] = [
    {
      title: '排序',
      dataIndex: 'sort',
      render: (dom, rowData, index) => {
        return (
          <span className="customRender">{`自定义Render[${rowData.name}-${index}]`}</span>
        );
      },
    },
    {
      title: '姓名',
      dataIndex: 'name',
      className: 'drag-visible',
    },
    {
      title: '年龄',
      dataIndex: 'age',
    },
    {
      title: '地址',
      dataIndex: 'address',
    },
  ];
  const columns2: ProColumns[] = [
    {
      title: '排序',
      dataIndex: 'sort',
    },
    {
      title: '姓名',
      dataIndex: 'name',
      className: 'drag-visible',
    },
    {
      title: '年龄',
      dataIndex: 'age',
    },
    {
      title: '地址',
      dataIndex: 'address',
    },
  ];
  const actionRef = useRef<ActionType>();
  const [dataSource1, setDatasource1] = useState(data);
  const [dataSource2, setDatasource2] = useState(data);
  const handleDragSortEnd1 = (
    beforeIndex: number,
    afterIndex: number,
    newDataSource: any,
  ) => {
    console.log('排序后的数据', newDataSource);
    setDatasource1(newDataSource);
    message.success('修改列表排序成功');
  };
  const handleDragSortEnd2 = (
    beforeIndex: number,
    afterIndex: number,
    newDataSource: any,
  ) => {
    console.log('排序后的数据', newDataSource);
    setDatasource2(newDataSource);
    message.success('修改列表排序成功');
  };
  const handleDragSortEnd3 = (
    beforeIndex: number,
    afterIndex: number,
    newDataSource: any,
  ) => {
    console.log('排序后的数据', newDataSource);
    // 模拟将排序后数据发送到服务器的场景
    remoteData = newDataSource;
    // 请求成功之后刷新列表
    actionRef.current?.reload();
    message.success('修改列表排序成功');
  };

  const dragHandleRender = (rowData: any, idx: any) => (
    <>
      <MenuOutlined style={{ cursor: 'grab', color: 'gold' }} />
      &nbsp;{idx + 1} - {rowData.name}
    </>
  );

  return (
    <>
      <DragSortTable
        headerTitle="拖拽排序(默认把手)"
        columns={columns}
        rowKey="key"
        search={false}
        pagination={false}
        dataSource={dataSource1}
        dragSortKey="sort"
        onDragSortEnd={handleDragSortEnd1}
      />
      <DragSortTable
        headerTitle="拖拽排序(自定义把手)"
        columns={columns2}
        rowKey="key"
        search={false}
        pagination={false}
        dataSource={dataSource2}
        dragSortKey="sort"
        dragSortHandlerRender={dragHandleRender}
        onDragSortEnd={handleDragSortEnd2}
      />
      <DragSortTable
        actionRef={actionRef}
        headerTitle="使用 request 获取数据源"
        columns={columns2}
        rowKey="key"
        search={false}
        pagination={false}
        request={request}
        dragSortKey="sort"
        onDragSortEnd={handleDragSortEnd3}
      />
    </>
  );
};
```

## DragSortTable

| 属性 | 描述 | 类型 | 默认值 |
| --- | --- | --- | --- | --- |
| dragSortKey | 如配置此参数，则会在该 key 对应的行显示拖拽排序把手，允许拖拽排序 | `string` | - |
| dragSortHandlerRender | 渲染自定义拖动排序把手的函数 如配置了 dragSortKey 但未配置此参数，则使用默认把手图标 | `(rowData: T, idx: number) => React.ReactNode` | `<MenuOutlined className="dragSortDefaultHandle" style={{ cursor: 'grab', color: '#999' }} />` |
| onDragSortEnd | 拖动排序完成回调 | `(beforeIndex: number, afterIndex: number, newDataSource: T[]) => Promise<void> | void` | - |
