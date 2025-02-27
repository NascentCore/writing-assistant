转换可读数据流

## 何时使用

- 将 SSE 协议的 `ReadableStream` 转换为 `Record`
- 将任何协议的 `ReadableStream` 解码并读取

## 使用说明

常见的 `ReadableStream` 实例，如 `await fetch(...).body` 使用示例:

```js
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

```tsx
import { TagsOutlined } from '@ant-design/icons';
import { ThoughtChain, XStream } from '@ant-design/x';
import { Button, Splitter } from 'antd';
import React from 'react';

const sipHeaders = [
  'INVITE sip:[email protected] SIP/2.0\n',
  'Via: SIP/2.0/UDP [host];branch=123456\n',
  'Content-Type: application/sdp\n\n',
];

const sdp = [
  'v=0\n',
  'o=alice 2890844526 2890844526 IN IP4 [host]\n',
  's=\n',
  'c=IN IP4 [host]\n',
  't=0 0\n',
  'm=audio 49170 RTP/AVP 0\n',
  'a=rtpmap:0 PCMU/8000\n',
  'm=video 51372 RTP/AVP 31\n',
  'a=rtpmap:31 H261/90000\n',
  'm=video 53000 RTP/AVP 32\n',
  'a=rtpmap:32 MPV/90000\n\n',
];

function mockReadableStream() {
  return new ReadableStream({
    async start(controller) {
      for (const chunk of sipHeaders.concat(sdp)) {
        await new Promise((resolve) => setTimeout(resolve, 100));
        controller.enqueue(new TextEncoder().encode(chunk));
      }
      controller.close();
    },
  });
}

const App = () => {
  const [lines, setLines] = React.useState<string[]>([]);

  async function readStream() {
    // 🌟 Read the stream
    for await (const chunk of XStream({
      readableStream: mockReadableStream(),
      transformStream: new TransformStream<string, string>({
        transform(chunk, controller) {
          controller.enqueue(chunk);
        },
      }),
    })) {
      setLines((pre) => [...pre, chunk]);
    }
  }

  return (
    <Splitter>
      <Splitter.Panel>
        <Button
          type="primary"
          onClick={readStream}
          style={{ marginBottom: 16 }}
        >
          Mock Custom Protocol - SIP
        </Button>
      </Splitter.Panel>
      {/* -------------- Log -------------- */}
      <Splitter.Panel style={{ marginLeft: 16 }}>
        <ThoughtChain
          items={
            lines.length
              ? [
                  {
                    title: 'Mock Custom Protocol - Log',
                    status: 'success',
                    icon: <TagsOutlined />,
                    content: (
                      <pre style={{ overflow: 'scroll' }}>
                        <code>{lines.join('')}</code>
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
