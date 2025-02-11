### USER

在页面中有一个 div 容器，该容器是支持滚动的，但问题是，当该容器滚动到底或者到顶的时候，就会触发整个页面的滚动，我不知道你 get 到我表达的内容没

### ASSISTANT

是的，我已经理解了你的问题。你描述的情况是：当一个支持滚动的 `div` 容器滚动到顶部或底部时，继续滚动会导致整个页面也开始滚动。这种行为在用户体验上可能会显得不友好，尤其是在需要限制滚动范围的场景中。

以下是问题的原因分析以及解决方案：

---

### **原因分析**

1. **事件冒泡**：
   - 当用户滚动 `div` 容器时，滚动事件会触发。如果容器已经滚动到边界（顶部或底部），浏览器会将多余的滚动行为传递给父级元素（即页面本身），从而导致页面滚动。
2. **默认行为**：
   - 浏览器的默认行为是允许滚动事件在边界条件下继续传播，这会导致页面滚动。

---

### **解决方案**

为了阻止这种行为，可以通过 JavaScript 捕获滚动事件，并在适当的情况下调用 `event.preventDefault()` 来阻止默认行为。以下是具体的实现方法：

#### **HTML 结构示例**

```html
<div class="scrollable-container">
  <div class="content">
    <!-- 这里是内容 -->
  </div>
</div>
```

#### **CSS 样式**

```css
.scrollable-container {
  width: 300px;
  height: 200px;
  overflow: auto; /* 支持滚动 */
  border: 1px solid #ccc;
}

.content {
  height: 600px; /* 内容高度大于容器高度 */
}
```

#### **JavaScript 实现**

```javascript
document.querySelector('.scrollable-container').addEventListener(
  'wheel',
  function (event) {
    const container = event.currentTarget;

    // 判断是否滚动到了顶部或底部
    const isAtTop = container.scrollTop === 0;
    const isAtBottom =
      container.scrollHeight - container.scrollTop === container.clientHeight;

    // 如果滚动方向与边界冲突，则阻止默认行为
    if ((isAtTop && event.deltaY < 0) || (isAtBottom && event.deltaY > 0)) {
      event.preventDefault();
    }
  },
  { passive: false },
); // 注意：必须设置 passive 为 false，否则无法调用 preventDefault
```

---

### **代码解析**

1. **事件监听**：

   - 使用 `wheel` 事件监听用户的滚动操作。
   - `event.deltaY` 表示滚动的方向和幅度，正值表示向下滚动，负值表示向上滚动。

2. **边界判断**：

   - `container.scrollTop === 0`：判断是否滚动到了顶部。
   - `container.scrollHeight - container.scrollTop === container.clientHeight`：判断是否滚动到了底部。

3. **阻止默认行为**：

   - 当滚动方向与边界冲突时（例如，已经滚动到顶部但用户继续向上滚动），调用 `event.preventDefault()` 阻止页面滚动。

4. **`passive: false`**：
   - 默认情况下，现代浏览器会将 `wheel` 事件标记为被动事件（`passive: true`），以提高性能。但这样会导致无法调用 `preventDefault()`，因此需要显式设置 `{ passive: false }`。

---

### **注意事项**

1. **兼容性**：

   - 上述代码在现代浏览器中表现良好，但在某些旧版浏览器中可能需要额外的兼容性处理。

2. **性能优化**：

   - 如果页面中有多个滚动容器，建议对事件监听进行优化，避免频繁触发事件回调。

3. **用户体验**：
   - 确保滚动行为的限制不会影响用户的正常操作，避免过度干预。

---

如果你有其他需求或需要进一步优化，请随时补充说明！
