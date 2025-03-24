# 技术上下文

## 开发环境

1. 核心技术栈

   - Node.js 环境
   - TypeScript v5.0.3
   - React v18
   - UmiJS v4.4.4
   - Ant Design v5.4.0

2. 开发工具链
   - 包管理器: pnpm
   - 代码格式化: Prettier v2.8.7
   - Git Hooks: Husky v9
   - 代码检查: ESLint
   - 样式处理: Less

## 主要依赖说明

### 1. 框架相关

- @umijs/max v4.4.4

  - UmiJS 的增强版本
  - 提供路由、状态管理等核心功能
  - 集成了常用的开发工具和插件

- React v18.0
  - 使用新版本 React
  - 支持并发特性
  - 利用 React Hooks

### 2. UI 组件库

- antd v5.4.0

  - 主要 UI 组件库
  - 提供完整的设计体系
  - 响应式设计支持

- @ant-design/icons v5.0.1

  - 图标系统
  - 可定制的图标组件

- @ant-design/pro-components v2.4.4
  - 扩展的高级组件
  - 面向中后台的组件集

### 3. 功能类库

- aieditor v1.3.5

  - AI 辅助编辑器核心库
  - 提供智能写作功能

- docx v9.1.1 & html2pdf.js v0.10.2

  - 文档格式转换
  - 支持导出多种格式

- markdown-it v14.1.0 & turndown v7.2.0

  - Markdown 解析和转换
  - 支持富文本和 Markdown 互转

- ahooks v3.8.4

  - React Hooks 工具库
  - 提供常用的功能性 Hooks

- lodash v4.17.21
  - 工具函数库
  - 提供常用的数据处理方法

### 4. 开发工具依赖

- TypeScript v5.0.3

  - 类型检查
  - 提供代码智能提示
  - 增强代码可维护性

- Prettier 相关

  - prettier v2.8.7
  - prettier-plugin-organize-imports
  - prettier-plugin-packagejson
  - 统一的代码格式化配置

- Husky & lint-staged
  - Git 提交前的代码检查
  - 自动化的代码质量控制

## 开发规范

### 1. 代码规范

```typescript
// 文件命名
components/
  ├── MyComponent/
      ├── index.tsx      // 组件主文件
      ├── index.less     // 样式文件
      └── interface.ts   // 类型定义
```

### 2. 样式规范

```less
// 使用 CSS Modules
.container {
  .header {
    // 嵌套规则
  }

  &:hover {
    // 状态样式
  }
}
```

### 3. TypeScript 规范

```typescript
// 接口定义
interface IProps {
  data: DataType;
  onChange?: (value: string) => void;
}

// 组件定义
const MyComponent: React.FC<IProps> = ({ data, onChange }) => {
  // ...
};
```

## 构建和部署

### 1. 开发命令

```bash
# 开发环境
npm run dev

# 构建生产
npm run build

# 代码格式化
npm run format
```

### 2. 环境配置

- 开发环境: development
- 生产环境: production
- 测试环境: test

### 3. 构建输出

- 资源优化
- 代码分割
- 静态资源处理

## 性能考虑

1. 代码分割

   - 路由级别分割
   - 组件懒加载
   - 第三方库按需加载

2. 缓存策略

   - 浏览器缓存
   - 状态缓存
   - API 响应缓存

3. 渲染优化
   - 虚拟列表
   - 组件缓存
   - 懒加载图片

## 安全考虑

1. 数据安全

   - HTTPS 传输
   - 敏感信息加密
   - XSS 防护

2. 认证授权
   - Token 基础认证
   - 路由权限控制
   - API 访问控制
