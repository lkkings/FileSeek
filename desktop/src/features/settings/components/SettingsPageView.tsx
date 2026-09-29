import { useMemo, useState } from "react";

import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import { useSettingsPreferences } from "../hooks/useSettingsPreferences";
import { StorageDriveManager } from "./StorageDriveManager";
import { TagManager } from "./TagManager";
import { SystemIntegrationCard } from "./SystemIntegrationCard";
import "./settings.css";

export function SettingsPageView() {
  const t = useTranslate();
  const {
    preferences,
    loading,
    loadError,
    setLocale,
    addTag,
    removeTag,
    addStorageDrive,
    removeStorageDrive,
    testStorageDrive,
  } = useSettingsPreferences();

  const localeOptions = useMemo(() => ([
    { value: "zh-CN" as const, labelId: "settings.languageChinese", label: "简体中文" },
    { value: "en-US" as const, labelId: "settings.languageEnglish", label: "English" },
  ]), []);
  const [storageFormOpen, setStorageFormOpen] = useState(false);

  return (
    <div className="settings-page">

      <div className="settings-primary-grid">
        <section className="settings-card settings-language-card">
          <div className="settings-card-header">
            <div className="settings-card-heading">
              <span className="settings-card-icon">
                <Icon name="settings" size={19} />
              </span>
              <div>
                <h2>{t("settings.languageTitle", "语言设置")}</h2>
                <p>{t("settings.languageDescription", "选择您喜欢的语言，切换应用界面语言")}</p>
              </div>
            </div>
            <div className="settings-language-options" role="group" aria-label={t("settings.language", "语言")}>
              {localeOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={preferences.locale === option.value ? "is-active" : ""}
                  aria-pressed={preferences.locale === option.value}
                  onClick={() => setLocale(option.value)}
                >
                  <span>{t(option.labelId, option.label)}</span>
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="settings-card settings-tag-card">
          <div className="settings-card-header">
            <div className="settings-card-heading">
              <span className="settings-card-icon">
                <Icon name="archive" size={19} />
              </span>
              <div>
                <h2>{t("settings.tagTitle", "模型标签管理")}</h2>
                <p>{t("settings.tagDescription", "管理文档、图片、视频的标签分类")}</p>
              </div>
            </div>
          </div>
          <TagManager preferences={preferences} onAddTag={addTag} onRemoveTag={removeTag} />
          {loading && <p className="settings-empty">{t("settings.loading", "正在读取设置...")}</p>}
          {loadError && <p className="settings-inline-error">{loadError}</p>}
        </section>
      </div>

      <SystemIntegrationCard />

      <section className="settings-card settings-storage-card">
        <div className="settings-card-header">
          <div className="settings-card-heading">
            <span className="settings-card-icon">
              <Icon name="nas" size={19} />
            </span>
            <div>
              <h2>{t("settings.storageTitle", "存储管理")}</h2>
              <p>{t("settings.storageDescription", "管理您的文件存储来源，支持添加多个 NAS")}</p>
            </div>
          </div>
          <button
            type="button"
            className="settings-add-drive"
            onClick={() => setStorageFormOpen((open) => !open)}
          >
            <Icon name="nas" size={16} />
            <span>{t("settings.addStorageDrive", "添加存储驱动")}</span>
          </button>
        </div>
        <StorageDriveManager
          drives={preferences.storageDrives}
          onAddDrive={addStorageDrive}
          onRemoveDrive={removeStorageDrive}
          onTestDrive={testStorageDrive}
          formOpen={storageFormOpen}
        />
      </section>
    </div>
  );
}
