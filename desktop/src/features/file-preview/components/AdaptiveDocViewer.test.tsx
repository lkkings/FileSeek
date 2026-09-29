import { fireEvent, render, screen } from "@testing-library/react";
import type { DocViewerRef, DocumentModel } from "anyview";
import { describe, expect, it, vi } from "vitest";

import { AdaptiveDocViewer } from "./AdaptiveDocViewer";

const anyviewMock = vi.hoisted(() => {
  const documentModel = {
    format: "pdf",
    meta: {
      name: "report.pdf",
      size: 1024,
      mimeType: "application/pdf",
    },
    pageCount: 1,
    pages: [
      {
        index: 0,
        width: 200,
        height: 100,
        rotation: 0,
      },
    ],
  } satisfies DocumentModel;
  const setZoom = vi.fn();

  return {
    setZoom,
    documentModel,
    DocViewer: vi.fn(
      ({
        onDocumentLoad,
        ref,
        page,
      }: {
        onDocumentLoad?: (document: DocumentModel) => void;
        ref?: { current: DocViewerRef | null };
        page?: number;
      }) => {
        if (ref) ref.current = { setZoom };
        return (
          <button
            type="button"
            data-testid="trigger-document-load"
            data-page={page}
            onClick={() => onDocumentLoad?.(documentModel)}
          >
            load
          </button>
        );
      },
    ),
  };
});

vi.mock("anyview", () => anyviewMock);

describe("AdaptiveDocViewer", () => {
  it("fits the loaded document to the available container width", () => {
    const clientWidthSpy = vi
      .spyOn(HTMLElement.prototype, "clientWidth", "get")
      .mockReturnValue(400);

    render(
      <AdaptiveDocViewer
        source={{
          kind: "url",
          url: "/api/v1/library/files/preview/file-1",
          filename: "report.pdf",
        }}
      />,
    );

    fireEvent.click(screen.getByTestId("trigger-document-load"));

    expect(anyviewMock.setZoom).toHaveBeenCalledWith(1.76);

    clientWidthSpy.mockRestore();
  });

  it("navigates to the one-based search hit page", () => {
    render(
      <AdaptiveDocViewer
        source={{
          kind: "url",
          url: "/api/v1/library/files/preview/file-1",
          filename: "report.pdf",
        }}
        initialPageNumber={3}
      />,
    );

    expect(screen.getByTestId("trigger-document-load")).toHaveAttribute("data-page", "2");
  });
});
