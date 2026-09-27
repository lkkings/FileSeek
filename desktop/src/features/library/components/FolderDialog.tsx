import { useState, type FormEvent } from "react";
import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import type { FolderFormValues, FolderRecord } from "../types";
import "./library.css";

interface FolderDialogProps {
  mode: "create" | "edit";
  folder?: FolderRecord;
  submitting: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (values: FolderFormValues) => void;
}

export function FolderDialog({ mode, folder, submitting, error, onClose, onSubmit }: FolderDialogProps) {
  const t = useTranslate();
  const [values, setValues] = useState<FolderFormValues>({
    name: folder?.name ?? "",
    iconType: folder?.iconType ?? "default",
    description: folder?.description ?? "",
  });
  const [validationError, setValidationError] = useState<string | null>(null);
  const isEdit = mode === "edit";

  function updateValue<Key extends keyof FolderFormValues>(key: Key, value: FolderFormValues[Key]) {
    setValues((current) => ({ ...current, [key]: value }));
    if (key === "name") setValidationError(null);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!values.name.trim()) {
      setValidationError(t("folder.nameRequired", "请输入文件夹名称"));
      return;
    }
    onSubmit(values);
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target && !submitting) onClose(); }}>
      <form className={`folder-dialog modal-dialog ${isEdit ? "is-edit" : "is-create"}`} role="dialog" aria-modal="true" aria-labelledby="folder-dialog-title" onSubmit={handleSubmit}>
        <div className="dialog-header">
          <div className="dialog-title-group">
            <span className="dialog-kicker"><Icon name="folder" size={16} />{isEdit ? t("folder.editKicker", "文件夹属性") : t("folder.createKicker", "文件库")}</span>
            <h2 id="folder-dialog-title">{isEdit ? t("folder.editTitle", "编辑文件夹") : t("folder.createTitle", "新建文件夹")}</h2>
            <p>{isEdit ? t("folder.editSubtitle", "修改文件夹名称、图标和描述") : t("folder.createSubtitle", "创建一个用于整理文件的文件夹")}</p>
          </div>
          <button className="dialog-close" type="button" aria-label={t("dialog.close", "关闭")} onClick={onClose} disabled={submitting}><Icon name="close" size={21} /></button>
        </div>

        <div className="dialog-fields">
          <label className="dialog-field">
            <span>{t("folder.name", "文件夹名称")}</span>
            <input autoFocus value={values.name} onChange={(event) => updateValue("name", event.target.value)} placeholder={t("folder.namePlaceholder", "例如：项目资料")} disabled={submitting} />
          </label>
          <label className="dialog-field">
            <span>{t("folder.icon", "文件夹图标")}</span>
            <span className="dialog-select-wrap">
              <select value={values.iconType} onChange={(event) => updateValue("iconType", event.target.value)} disabled={submitting}>
                <option value="default">{t("folder.iconDefault", "默认")}</option>
                <option value="travel">{t("folder.iconTravel", "旅行")}</option>
                <option value="work">{t("folder.iconWork", "工作")}</option>
                <option value="photos">{t("folder.iconPhotos", "相册")}</option>
                <option value="videos">{t("folder.iconVideos", "视频")}</option>
              </select>
              <Icon name="chevron" size={17} />
            </span>
          </label>
          <label className="dialog-field dialog-field-description">
            <span>{t("folder.description", "描述")}</span>
            <textarea value={values.description} onChange={(event) => updateValue("description", event.target.value)} placeholder={t("folder.descriptionPlaceholder", "添加一句描述")} rows={3} disabled={submitting} />
          </label>
        </div>

        {(validationError || error) && <p className="dialog-error" role="alert">{validationError || error}</p>}
        <div className="dialog-actions">
          <button className="dialog-secondary" type="button" onClick={onClose} disabled={submitting}>{t("dialog.cancel", "取消")}</button>
          <button className="dialog-primary" type="submit" disabled={submitting}><Icon name={isEdit ? "edit" : "plus"} size={18} /><span>{submitting ? t("dialog.saving", "保存中...") : isEdit ? t("folder.save", "保存更改") : t("folder.create", "创建文件夹")}</span></button>
        </div>
      </form>
    </div>
  );
}
