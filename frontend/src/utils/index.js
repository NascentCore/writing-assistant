import { API_BASE_URL } from "./../config";

export const bindAiBtnHandleClick = (clickFn) => {
  const container = document.querySelector(".aie-container");

  if (container) {
    const observer = new MutationObserver((mutationsList, observer) => {
      for (let mutation of mutationsList) {
        if (mutation.type === "childList") {
          const element = document.getElementById("ai");
          if (element) {
            console.log("Element ai is now available:", element);
            element.addEventListener("click", () => {
              console.log("Element id was clicked!");
              clickFn();
            });
          }
        }
      }
    });
    observer.observe(container, {
      childList: true,
      subtree: false,
    });
  } else {
    console.error(".aie-container element not found!");
  }
};

// 防抖函数
export function debounce(func, delay = 300) {
  let timer;
  return function (...args) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      func(...args);
    }, delay);
  };
}

// 复制文本到剪贴板
export function copyToClipboardLegacy(text) {
  if (!text) return;
  const textArea = document.createElement("textarea");
  textArea.value = text;
  document.body.appendChild(textArea);
  textArea.select();
  document.execCommand("copy");
  document.body.removeChild(textArea);
  console.log("Text copied to clipboard");
  alert("复制成功");
}

// 发送请求获取AI生成的内容
export async function fetchStreamedResponse({
  content,
  onMessage,
  onComplete,
}) {
  const url = `${API_BASE_URL}/api/v1/completions`;
  const headers = {
    Accept: "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    Connection: "keep-alive",
    "Content-Type": "application/json",
  };
  const body = JSON.stringify({
    messages: [{ role: "user", content: content }],
    max_tokens: null,
    temperature: null,
    stream: true,
  });

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: headers,
      body: body,
      signal: new AbortController().signal,
    });

    if (!response.ok) {
      throw new Error("Network response was not ok");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullChunk = "";
    let fullResponse = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      fullChunk += chunk;
      const lines = chunk.split("\n");
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            const content = data.choices[0].delta.content;
            if (content) {
              fullResponse += content;
            }
          } catch (e) {
            console.error("解析JSON时出错:", e);
          }
        }
      }
      onMessage(fullResponse);
    }

    onComplete(fullResponse);
  } catch (error) {
    console.error("Fetch error:", error);
    onComplete(null, error);
  }
}
