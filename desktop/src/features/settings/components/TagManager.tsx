import { useState } from "react";

import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import type { SettingsPreferences, TagCategory } from "../types";
import { TagListEditor } from "./TagListEditor";

interface TagManagerProps {
  preferences: SettingsPreferences;
  onAddTag: (category: TagCategory, tag: string) => Promise<boolean>;
  onRemoveTag: (category: TagCategory, tag: string) => Promise<void>;
}

const tagCategories: Array<{
  id: TagCategory;
  labelId: string;
  label: string;
  icon: "document" | "image" | "video";
}> = [
  { id: "documentTags", labelId: "settings.documentTags", label: "文档标签", icon: "document" },
  { id: "imageTags", labelId: "settings.imageTags", label: "图片标签", icon: "image" },
  { id: "videoTags", labelId: "settings.videoTags", label: "视频标签", icon: "video" },
];

export function TagManager({ preferences, onAddTag, onRemoveTag }: TagManagerProps) {
  const t = useTranslate();
  const [activeCategory, setActiveCategory] = useState<TagCategory>("documentTags");
  const activeTag = tagCategories.find((category) => category.id === activeCategory) ?? tagCategories[0]!;

  return (
    <div className="settings-tag-manager">
      <div className="settings-tag-tabs" role="tablist" aria-label={t("settings.tags", "标签列表")}>
        {tagCategories.map((category) => {
          const selected = category.id === activeCategory;
          return (
            <button
              key={category.id}
              type="button"
              role="tab"
              id={`${category.id}-tab`}
              aria-selected={selected}
              aria-controls={`${category.id}-panel`}
              className={selected ? "is-active" : ""}
              onClick={() => setActiveCategory(category.id)}
            >
              <Icon name={category.icon} size={18} />
              <span>{t(category.labelId, category.label)}</span>
            </button>
          );
        })}
      </div>

      <div
        className="settings-tag-panel"
        role="tabpanel"
        id={`${activeTag.id}-panel`}
        aria-labelledby={`${activeTag.id}-tab`}
      >
        <TagListEditor
          titleId={activeTag.labelId}
          titleFallback={activeTag.label}
          tags={preferences[activeTag.id]}
          onAdd={(tag) => onAddTag(activeTag.id, tag)}
          onRemove={(tag) => onRemoveTag(activeTag.id, tag)}
        />
      </div>
    </div>
  );
}
