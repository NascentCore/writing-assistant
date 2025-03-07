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
      el.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
        inline: 'nearest',
      });
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
