import React, { useState, useRef, useEffect } from 'react';
import '../styles/export-btn-group.css';

const ExportBtnGroup = ({ handleExport }) => {
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  return (
    <div className="export-btn-group" ref={dropdownRef}>
      <button 
        className="export-btn"
        onClick={() => setShowDropdown(!showDropdown)}
      >
        导出
      </button>
      {showDropdown && (
        <div className="export-dropdown">
          <button onClick={() => {
            handleExport('pdf');
            setShowDropdown(false);
          }}>
            导出为 PDF
          </button>
          <button onClick={() => {
            handleExport('docx');
            setShowDropdown(false);
          }}>
            导出为 Word
          </button>
        </div>
      )}
    </div>
  );
};

export default ExportBtnGroup; 