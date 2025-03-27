declare module 'react-file-viewer' {
  import { FC } from 'react';

  interface FileViewerProps {
    fileType: string;
    filePath: string;
    onError?: (error: Error) => void;
    errorComponent?: FC;
  }

  const FileViewer: FC<FileViewerProps>;
  export default FileViewer;
}
