import htmlDocx from "html-docx-js/dist/html-docx";
import html2pdf from "html2pdf.js";

export const saveAsDocx = (content) => {
  const convertedblob = htmlDocx.asBlob(content);
  const link = document.createElement("a");
  link.href = URL.createObjectURL(convertedblob);
  link.download = "售前方案写作助手.docx";
  link.click();
  URL.revokeObjectURL(link.href);
};

export const saveAsPdf = () => {
  const element = document.querySelector('.aie-container-main');
  const opt = {
    margin: 1,
    filename: "售前方案.pdf",
    image: { type: "jpeg", quality: 0.98 },
    html2canvas: { scale: 2 },
    jsPDF: {
      unit: "in",
      format: "letter",
      orientation: "portrait",
    },
  };

  return html2pdf().set(opt).from(element).save();
};
