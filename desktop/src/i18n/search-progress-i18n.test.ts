import { afterEach, describe, expect, it } from "vitest";

import { activateLocale, i18n } from "./i18n";

const progressKeys = [
  "search.progress.title",
  "search.progress.reasoning",
  "search.progress.searching",
  "search.progress.searchResult",
  "search.progress.failed",
  "search.progress.cache",
  "search.progress.starting",
  "search.progress.building",
  "search.progress.selecting",
  "search.progress.status",
  "search.progress.round",
  "search.progress.keyword",
  "search.progress.categories",
  "search.progress.nameQuery",
  "search.progress.candidates",
  "search.progress.completed",
  "search.progress.viewProcess",
  "search.progress.category.document",
  "search.progress.category.image",
  "search.progress.category.video",
  "search.enhanced.streamFailed",
];

describe("search progress localization", () => {
  afterEach(() => activateLocale("zh-CN"));

  it("provides every progress key in Chinese and English", () => {
    for (const locale of ["zh-CN", "en-US"] as const) {
      activateLocale(locale);
      for (const key of progressKeys) {
        expect(i18n._(key, {}, { message: "__missing__" })).not.toBe("__missing__");
      }
    }
  });
});
