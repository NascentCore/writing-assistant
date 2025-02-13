转换可读数据流

## 何时使用

- 将 SSE 协议的 `ReadableStream` 转换为 `Record`
- 将任何协议的 `ReadableStream` 解码并读取

## 使用说明

常见的 `ReadableStream` 实例，如 `await fetch(...).body` 使用示例:

```
import { XStream } from '@ant-design/x';

async function request() {
  const response = await fetch();
  // .....

  for await (const chunk of XStream({
    readableStream: response.body,
  })) {
    console.log(chunk);
  }
}
```

#### 默认协议 - SSE

XStream 默认的 `transformStream` 是用于 SSE 协议的流转换器。`readableStream` 接收一个 `new ReadableStream(...)` 实例，常见的如 `await fetch(...).body`

```
import { TagsOutlined } from '@ant-design/icons';
import { Bubble, ThoughtChain, XStream } from '@ant-design/x';
import { Button, Splitter } from 'antd';
import React from 'react';

const contentChunks = ['He', 'llo', ', w', 'or', 'ld!'];

function mockReadableStream() {
  const sseChunks: string[] = [];

  for (let i = 0; i < contentChunks.length; i++) {
    const sseEventPart = `event: message\ndata: {"id":"${i}","content":"${contentChunks[i]}"}\n\n`;
    sseChunks.push(sseEventPart);
  }

  return new ReadableStream({
    async start(controller) {
      for (const chunk of sseChunks) {
        await new Promise((resolve) => setTimeout(resolve, 100));
        controller.enqueue(new TextEncoder().encode(chunk));
      }
      controller.close();
    },
  });
}

const App = () => {
  const [lines, setLines] = React.useState<Record<string, string>[]>([]);
  const content = lines.map((line) => JSON.parse(line.data).content).join('');

  async function readStream() {
    // 🌟 Read the stream
    for await (const chunk of XStream({
      readableStream: mockReadableStream(),
    })) {
      console.log(chunk);
      setLines((pre) => [...pre, chunk]);
    }
  }

  return (
    <Splitter>
      <Splitter.Panel>
        {/* -------------- Emit -------------- */}
        <Button type="primary" onClick={readStream} style={{ marginBottom: 16 }}>
          Mock Default Protocol - SSE
        </Button>
        {/* -------------- Content Concat -------------- */}
        {content && <Bubble content={content} />}
      </Splitter.Panel>
      {/* -------------- Log -------------- */}
      <Splitter.Panel style={{ marginLeft: 16 }}>
        <ThoughtChain
          items={
            lines.length
              ? [
                  {
                    title: 'Mock Default Protocol - Log',
                    status: 'success',
                    icon: <TagsOutlined />,
                    content: (
                      <pre style={{ overflow: 'scroll' }}>
                        {lines.map((i) => (
                          <code key={i.data}>{i.data}</code>
                        ))}
                      </pre>
                    ),
                  },
                ]
              : []
          }
        />
      </Splitter.Panel>
    </Splitter>
  );
};

export default App;
```
