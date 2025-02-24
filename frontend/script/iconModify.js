const fs = require('fs');
const path = require('path');

// 定义目录路径
const dirPath = path.join(__dirname, '../src/Icon/assets');

// 读取并处理SVG文件
function processSVGFiles(dirPath) {
  fs.readdir(dirPath, (err, files) => {
    if (err) {
      console.error('读取目录出错:', err);
      return;
    }

    files.forEach((file) => {
      if (path.extname(file) === '.svg') {
        const filePath = path.join(dirPath, file);

        fs.readFile(filePath, 'utf8', (err, data) => {
          if (err) {
            console.error('读取文件出错:', err);
            return;
          }

          // 替换操作
          let modifiedData = data
            .replace(/width="24"/g, 'width="1em"')
            .replace(/height="24"/g, 'height="1em"')
            .replace(/fill="none"/g, 'fill="currentColor"')
            .replace(/fill="#4E5969"/g, '');

          fs.writeFile(filePath, modifiedData, 'utf8', (err) => {
            if (err) {
              console.error('写入文件出错:', err);
              return;
            }
            console.log(`${file} 已被修改。`);
          });
        });
      }
    });
  });
}

// 调用函数处理文件
processSVGFiles(dirPath);
