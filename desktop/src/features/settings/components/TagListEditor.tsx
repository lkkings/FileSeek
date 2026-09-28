import { useState, type FormEvent } from "react";

import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";

interface TagListEditorProps {
  titleId: string;
  titleFallback: string;
  tags: string[];
  onAdd: (tag: string) => Promise<boolean>;
  onRemove: (tag: string) => Promise<void>;
}

export function TagListEditor({ titleId, titleFallback, tags, onAdd, onRemove }: TagListEditorProps) {
  const t = useTranslate();
  const [value, setValue] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    const normalized = value.trim();
    if (!normalized) {
      setError(t("settings.tagName", "标签名称"));
      return;
    }

    try {
      const added = await onAdd(normalized);
      if (added) {
        setValue("");
        setError("");
      } else {
        setError(t("settings.tagExists", "标签已存在"));
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("settings.saveFailed", "保存设置失败"));
    }
  };

  return (
    <section className="settings-tag-group" aria-label={t(titleId, titleFallback)}>
      <form className="settings-tag-form" onSubmit={handleSubmit}>
        <label className="settings-visually-hidden" htmlFor={`${titleId}-input`}>
          {t("settings.tagName", "标签名称")}
        </label>
        <input
          id={`${titleId}-input`}
          value={value}
          placeholder={t("settings.tagName", "标签名称")}
          onChange={(event) => setValue(event.target.value)}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${titleId}-error` : undefined}
        />
        <button type="submit">
          <Icon name="plus" size={15} />
          <span>{t("settings.addTag", "添加标签")}</span>
        </button>
        {error && <p id={`${titleId}-error`} className="settings-inline-error">{error}</p>}
      </form>
      {tags.length === 0 ? (
        <p className="settings-empty">{t("settings.noTags", "暂无标签")}</p>
      ) : (
        <ul className="settings-tag-list">
          {tags.map((tag) => (
            <li key={tag}>
              <span>{tag}</span>
              <button type="button" onClick={() => onRemove(tag)} aria-label={`${t("common.remove", "移除")} ${tag}`}>
                <Icon name="close" size={13} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
