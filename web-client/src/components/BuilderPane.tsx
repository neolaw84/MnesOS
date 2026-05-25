import type { ChangeEvent } from "react";

export interface BuilderPaneProps {
  title: string;
  filename: string;
  content: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
  language?: string;
  format?: "yaml" | "js";
  onDownload?: () => void;
}

export default function BuilderPane({
  title,
  filename,
  content,
  onChange,
  readOnly,
  language,
  onDownload,
}: BuilderPaneProps) {
  const handleDownload = () => {
    if (onDownload) {
      onDownload();
      return;
    }

    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const handleChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    onChange(event.target.value);
  };

  return (
    <section className="builder-pane" aria-label={`${title} pane`} data-language={language}>
      <div className="builder-pane-header">
        <h3>{title}</h3>
        <button className="btn btn-small btn-secondary" onClick={handleDownload}>
          ⬇ Download
        </button>
      </div>
      <textarea
        className="builder-editor"
        aria-label={`${title} editor`}
        value={content}
        onChange={handleChange}
        readOnly={readOnly}
        spellCheck={false}
      />
    </section>
  );
}
