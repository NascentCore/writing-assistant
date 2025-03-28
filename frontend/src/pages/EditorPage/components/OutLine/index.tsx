import { AiEditor } from 'aieditor';
import { Tree, Typography } from 'antd';
import type { DataNode } from 'antd/es/tree';

interface OutlineNode extends DataNode {
  pos: number;
  size: number;
  level: number;
}

interface OutLineProps {
  editorRef: React.MutableRefObject<AiEditor | null>;
  outlineData: OutlineNode[];
}

const OutLine: React.FC<OutLineProps> = ({ editorRef, outlineData }) => {
  const handleOutlineSelect = (selectedKeys: React.Key[], info: any) => {
    if (!editorRef.current || selectedKeys.length === 0) return;

    const editor = editorRef.current;
    const selectedNode = info.node as OutlineNode;
    const el = editor.innerEditor.view.dom.querySelector(
      `#${selectedNode.key}`,
    );

    if (el) {
      // 滚动到目标位置
      el.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
        inline: 'nearest',
      });

      // 创建覆盖层实现高亮效果
      // 首先移除之前可能存在的覆盖层
      const previousOverlays = document.querySelectorAll(
        '.heading-highlight-overlay',
      );
      previousOverlays.forEach((overlay) => {
        overlay.remove();
      });

      // 获取元素位置信息
      const rect = el.getBoundingClientRect();
      const scrollTop =
        window.pageYOffset || document.documentElement.scrollTop;
      const scrollLeft =
        window.pageXOffset || document.documentElement.scrollLeft;

      // 创建覆盖层
      const overlay = document.createElement('div');
      overlay.className = 'heading-highlight-overlay';

      // 设置覆盖层样式
      Object.assign(overlay.style, {
        position: 'absolute',
        top: `${rect.top + scrollTop}px`,
        left: `${rect.left + scrollLeft}px`,
        width: `${rect.width}px`,
        height: `${rect.height}px`,
        backgroundColor: 'rgba(255, 230, 0, 0.4)',
        pointerEvents: 'none', // 确保不会阻止点击事件
        zIndex: '9999', // 设置非常高的层级
        borderRadius: '3px',
        boxShadow: '0 0 8px 2px rgba(255, 230, 0, 0.6)',
        animation: 'headingFlash 2s ease-out',
        display: 'flex',
        alignItems: 'center',
      });

      // 添加到文档中
      document.body.appendChild(overlay);

      // 添加动画样式（如果尚未添加）
      if (!document.getElementById('heading-flash-style')) {
        const style = document.createElement('style');
        style.id = 'heading-flash-style';
        style.innerHTML = `
          @keyframes headingFlash {
            0% { opacity: 1; transform: scale(1.05); }
            70% { opacity: 0.7; transform: scale(1); }
            100% { opacity: 0; transform: scale(1); }
          }
          .heading-highlight-overlay {
            animation: headingFlash 1s ease-out forwards;
          }
        `;
        document.head.appendChild(style);
      }

      // 动画结束后自动移除覆盖层
      setTimeout(() => {
        overlay.remove();
      }, 1000);
    }
  };

  return (
    <div style={{ padding: 20, marginTop: 18, background: '#fff' }}>
      <h5>文档目录</h5>

      <Tree<OutlineNode>
        treeData={outlineData}
        onSelect={handleOutlineSelect}
        defaultExpandAll
        blockNode
        motion={false}
        titleRender={(node: OutlineNode) => (
          <Typography.Text
            style={{
              fontSize: node.level === 1 ? '14px' : '12px',
              fontWeight: node.level === 1 ? 500 : 'normal',
              paddingLeft: (node.level - 1) * 8,
            }}
          >
            {typeof node.title === 'function' ? node.title(node) : node.title}
          </Typography.Text>
        )}
      />
    </div>
  );
};

export default OutLine;
