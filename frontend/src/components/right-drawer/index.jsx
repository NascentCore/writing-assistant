import React, { useEffect, useState } from "react";
import "./index.css";
import {
  bindAiBtnHandleClick,
  debounce,
  copyToClipboardLegacy,
  fetchStreamedResponse,
} from "../../utils/index.js";
import { bubblePanelMenus } from "./../../App.js";

const RightDrawer = ({ isOpen, onClose, children }) => {
  return (
    <div className={`drawer ${isOpen ? "open" : ""}`}>
      <div className="drawer-content">
        <button className="close-button" onClick={onClose}>
          X
        </button>
        {children}
      </div>
    </div>
  );
};

const Index = ({ editorRef }) => {
  const [isDrawerOpen, setDrawerOpen] = useState(false);

  const [selectText, setSelectText] = useState("");
  const toggleDrawer = () => {
    setDrawerOpen(!isDrawerOpen);
  };

  const [selectedOption, setSelectedOption] = useState("");
  const [generatedContent, setGeneratedContent] = useState("");

  const handleGenerate = () => {
    if (selectedOption && selectText) {
      const prompt = bubblePanelMenus?.find(
        (item) => item.title === selectedOption
      )?.prompt;
      const content = prompt.replace(/{content}/g, selectText);

      fetchStreamedResponse({
        content: content,
        onMessage: (result) => {
          setGeneratedContent(result);
        },
        onComplete: (result) => {
          setGeneratedContent(result);
        },
      });
    }
  };

  const handleUseGeneratedContent = () => {
    // 使用生成的内容
    console.log("使用生成的内容");
    copyToClipboardLegacy(selectText);
  };

  useEffect(() => {
    bindAiBtnHandleClick(
      debounce(() => {
        console.log("ai btn clicked");
        setDrawerOpen(true);
        const selectText = editorRef.current.getSelectedText();
        setSelectText(selectText);
      })
    );
  }, []);

  return (
    <div>
      <RightDrawer isOpen={isDrawerOpen} onClose={toggleDrawer}>
        <div className="tip-text" style={{ marginTop: 20 }}>
          选中的内容
        </div>
        <div className="generated-content">{selectText}</div>
        {/* 下拉选择组件 */}
        <select
          value={selectedOption}
          onChange={(e) => setSelectedOption(e.target.value)}
        >
          <option value="">请选择一个选项</option>
          {bubblePanelMenus?.map((item, index) => {
            return (
              <option key={index} value={item.title}>
                {item.title}
              </option>
            );
          })}
        </select>

        {/* 一键生成 按钮 */}
        <button className="nomal-button" onClick={handleGenerate}>
          一键生成
        </button>

        {/* 生成后内容显示区域 */}
        <div className="tip-text">生成的内容</div>
        <div className="generated-content">{generatedContent}</div>
        <button className="nomal-button" onClick={handleUseGeneratedContent}>
          复制
        </button>
      </RightDrawer>
    </div>
  );
};

export default Index;
