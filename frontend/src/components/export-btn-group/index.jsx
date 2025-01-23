const ExportBtnGroup = ({ handleExport }) => {
  return (
    <div className="btn-group">
      <button
        onClick={() => handleExport("pdf")}
        style={{
          padding: "4px 12px",
          border: "1px solid #e8e8e8",
          background: "none",
          cursor: "pointer",
          fontSize: "14px",
          borderRadius: "4px",
          display: "flex",
          alignItems: "center",
          gap: "4px",
        }}
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <line x1="12" y1="18" x2="12" y2="12"></line>
          <line x1="9" y1="15" x2="15" y2="15"></line>
        </svg>
        导出 PDF
      </button>
      <button
        onClick={() => handleExport("docx")}
        style={{
          padding: "4px 12px",
          border: "1px solid #e8e8e8",
          background: "none",
          cursor: "pointer",
          fontSize: "14px",
          borderRadius: "4px",
          display: "flex",
          alignItems: "center",
          gap: "4px",
        }}
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <line x1="16" y1="13" x2="8" y2="13"></line>
          <line x1="16" y1="17" x2="8" y2="17"></line>
          <polyline points="10 9 9 9 8 9"></polyline>
        </svg>
        导出 Word
      </button>
    </div>
  );
};

export default ExportBtnGroup;
