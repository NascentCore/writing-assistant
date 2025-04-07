import Icon from '@ant-design/icons';

import React from 'react';

import { ReactComponent as Binding } from './assets/icon_binding.svg';
import { ReactComponent as FilePreview } from './assets/icon_collect_sel.svg';
import { ReactComponent as Delete } from './assets/icon_delete.svg';
import { ReactComponent as EditArrow } from './assets/icon_edit_arrow.svg';
import { ReactComponent as EditRect } from './assets/icon_edit_rect.svg';
import { ReactComponent as EditText } from './assets/icon_edit_text.svg';
import { ReactComponent as Edit } from './assets/icon_editor.svg';
import { ReactComponent as File } from './assets/icon_file.svg';
import { ReactComponent as Excel } from './assets/icon_file_excel.svg';
import { ReactComponent as Image } from './assets/icon_file_image.svg';
import { ReactComponent as Pdf } from './assets/icon_file_pdf.svg';
import { ReactComponent as Txt } from './assets/icon_file_txt.svg';
import { ReactComponent as Word } from './assets/icon_file_word.svg';
import { ReactComponent as FormArrow } from './assets/icon_form_arrow.svg';
import { ReactComponent as FormPrint } from './assets/icon_form_print.svg';
import { ReactComponent as DownloadCenter } from './assets/icon_header_down.svg';
import { ReactComponent as NotificationDot } from './assets/icon_header_message-1.svg';
import { ReactComponent as Notification } from './assets/icon_header_message.svg';
import { ReactComponent as Person } from './assets/icon_header_personage.svg';
import { ReactComponent as Logout } from './assets/icon_header_quit.svg';
import { ReactComponent as Link } from './assets/icon_link.svg';
import { ReactComponent as Message } from './assets/icon_message.svg';
import { ReactComponent as RectTangle } from './assets/icon_rectangle.svg';
import { ReactComponent as Remove } from './assets/icon_remove.svg';
import { ReactComponent as Rotate } from './assets/icon_rotate.svg';
import { ReactComponent as Setting } from './assets/icon_settings.svg';
import { ReactComponent as MoneyDetail } from './assets/icon_table_detail.svg';
import { ReactComponent as TreeUser } from './assets/icon_tree_user.svg';
import { ReactComponent as Untie } from './assets/icon_untie.svg';
import { ReactComponent as ZoomIn } from './assets/icon_zoom_in.svg';
import { ReactComponent as ZoomOut } from './assets/icon_zoom_out.svg';

import { ReactComponent as ImageSpace } from './assets/icon_image_space.svg';
import { ReactComponent as ImageAnnotation } from './assets/icon_picture_annotation.svg';
import { ReactComponent as Up } from './assets/icon_up.svg';
import { ReactComponent as ImageView } from './assets/icon_view_artwork.svg';

import { ReactComponent as AIChat } from './assets/icon_ai_chat.svg';
import { ReactComponent as Close } from './assets/icon_close.svg';
import { ReactComponent as DepartKn } from './assets/icon_depart_kn.svg';
import { ReactComponent as DepartMana } from './assets/icon_depart_manage.svg';
import { ReactComponent as Down } from './assets/icon_down.svg';
import { ReactComponent as PreviewClose } from './assets/icon_form_preview_close.svg';
import { ReactComponent as KnSearch } from './assets/icon_kn_search.svg';
import { ReactComponent as PersonalKnowledge } from './assets/icon_personal_knowledge.svg';
import { ReactComponent as RecentChat } from './assets/icon_recent_chat.svg';
import { ReactComponent as SystemKnowledge } from './assets/icon_system_knowledge.svg';
import { ReactComponent as TemplateManage } from './assets/icon_template_manage.svg';
import { ReactComponent as VideoDisplay } from './assets/icon_video_display.svg';
import { ReactComponent as WritingAssistant } from './assets/icon_writing_assistant.svg';

type IconType =
  | 'Setting'
  | 'Delete'
  | 'Binding'
  | 'Untie'
  | 'Remove'
  | 'Link'
  | 'FilePreview'
  | 'Notification'
  | 'NotificationDot'
  | 'TreeUser'
  | 'DownloadCenter'
  | 'Logout'
  | 'Person'
  | 'MoneyDetail'
  | 'Message'
  | 'Excel'
  | 'Image'
  | 'Pdf'
  | 'Txt'
  | 'Word'
  | 'File'
  | 'Edit'
  | 'ZoomIn'
  | 'ZoomOut'
  | 'Rotate'
  | 'FormArrow'
  | 'FormPrint'
  | 'EditText'
  | 'EditArrow'
  | 'RectTangle'
  | 'ImageView'
  | 'ImageAnnotation'
  | 'EditRect'
  | 'Up'
  | 'ImageSpace'
  | 'VideoDisplay'
  | 'Close'
  | 'PreviewClose'
  | 'Down'
  | 'PersonalKnowledge'
  | 'SystemKnowledge'
  | 'WritingAssistant'
  | 'KnSearch'
  | 'DepartKn'
  | 'DepartMana'
  | 'RecentChat'
  | 'AIChat'
  | 'TemplateManage';

const RoadIcon: React.FC<{
  style?: React.CSSProperties;
  spin?: boolean;
  className?: string;
  type: IconType;
  rotate?: number;
  twoToneColor?: string | string[];
}> = ({ ...props }) => {
  let IconComponent;
  const { type, ...rest } = props;
  if (type === 'Setting') {
    IconComponent = Setting;
  } else if (type === 'Delete') {
    IconComponent = Delete;
  } else if (type === 'Binding') {
    IconComponent = Binding;
  } else if (type === 'Untie') {
    IconComponent = Untie;
  } else if (type === 'Remove') {
    IconComponent = Remove;
  } else if (type === 'Link') {
    IconComponent = Link;
  } else if (type === 'FilePreview') {
    IconComponent = FilePreview;
  } else if (type === 'Message') {
    IconComponent = Message;
  } else if (type === 'Notification') {
    IconComponent = Notification;
  } else if (type === 'NotificationDot') {
    IconComponent = NotificationDot;
  } else if (type === 'TreeUser') {
    IconComponent = TreeUser;
  } else if (type === 'DownloadCenter') {
    IconComponent = DownloadCenter;
  } else if (type === 'Logout') {
    IconComponent = Logout;
  } else if (type === 'Person') {
    IconComponent = Person;
  } else if (type === 'MoneyDetail') {
    IconComponent = MoneyDetail;
  } else if (type === 'Excel') {
    IconComponent = Excel;
  } else if (type === 'Image') {
    IconComponent = Image;
  } else if (type === 'Pdf') {
    IconComponent = Pdf;
  } else if (type === 'Txt') {
    IconComponent = Txt;
  } else if (type === 'Word') {
    IconComponent = Word;
  } else if (type === 'File') {
    IconComponent = File;
  } else if (type === 'Edit') {
    IconComponent = Edit;
  } else if (type === 'ZoomIn') {
    IconComponent = ZoomIn;
  } else if (type === 'ZoomOut') {
    IconComponent = ZoomOut;
  } else if (type === 'Rotate') {
    IconComponent = Rotate;
  } else if (type === 'FormArrow') {
    IconComponent = FormArrow;
  } else if (type === 'FormPrint') {
    IconComponent = FormPrint;
  } else if (type === 'EditText') {
    IconComponent = EditText;
  } else if (type === 'EditArrow') {
    IconComponent = EditArrow;
  } else if (type === 'RectTangle') {
    IconComponent = RectTangle;
  } else if (type === 'ImageView') {
    IconComponent = ImageView;
  } else if (type === 'ImageAnnotation') {
    IconComponent = ImageAnnotation;
  } else if (type === 'EditRect') {
    IconComponent = EditRect;
  } else if (type === 'Up') {
    IconComponent = Up;
  } else if (type === 'ImageSpace') {
    IconComponent = ImageSpace;
  } else if (type === 'VideoDisplay') {
    IconComponent = VideoDisplay;
  } else if (type === 'Close') {
    IconComponent = Close;
  } else if (type === 'PreviewClose') {
    IconComponent = PreviewClose;
  } else if (type === 'Down') {
    IconComponent = Down;
  } else if (type === 'PersonalKnowledge') {
    IconComponent = PersonalKnowledge;
  } else if (type === 'SystemKnowledge') {
    IconComponent = SystemKnowledge;
  } else if (type === 'WritingAssistant') {
    IconComponent = WritingAssistant;
  } else if (type === 'RecentChat') {
    IconComponent = RecentChat;
  } else if (type === 'AIChat') {
    IconComponent = AIChat;
  } else if (type === 'KnSearch') {
    IconComponent = KnSearch;
  } else if (type === 'DepartKn') {
    IconComponent = DepartKn;
  } else if (type === 'DepartMana') {
    IconComponent = DepartMana;
  } else if (type === 'TemplateManage') {
    IconComponent = TemplateManage;
  }

  return <Icon style={{ fontSize: 24 }} component={IconComponent} {...rest} />;
};

export default RoadIcon;
