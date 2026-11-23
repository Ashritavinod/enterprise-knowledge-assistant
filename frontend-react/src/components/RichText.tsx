import type { ReactNode } from "react";

/**
 * Inline formatting: **bold**, *italic*, `code`, [1]-style citations and the FAQ's
 * bold "Q:" / "A:" labels. Unclosed markers (mid-stream) stay as plain text.
 */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`|\[\d{1,2}\]|\bQ:|\bA:)/).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      return <em key={i}>{part.slice(1, -1)}</em>;
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return <code key={i}>{part.slice(1, -1)}</code>;
    }
    if (/^\[\d{1,2}\]$/.test(part)) {
      const n = part.slice(1, -1);
      return (
        <span key={i} className="cite" title={`Source ${n}`}>
          {n}
        </span>
      );
    }
    if (part === "Q:" || part === "A:") {
      return (
        <strong key={i} className="qa-label">
          {part}
        </strong>
      );
    }
    return part;
  });
}

const BULLET = /^(?:•|[-*])\s+/;
const NUMBERED = /^\d{1,2}[.)]\s+/;
const HEADING = /^#{1,4}\s+/;
// Markdown table separator rows like "|---|:--:|".
const TABLE_SEPARATOR = /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$/;

const isTableRow = (line: string) => line.includes(" | ") || /^\|.*\|$/.test(line);
const cells = (line: string) => line.replace(/^\|\s*|\s*\|$/g, "").split(/\s*\|\s*/);

/**
 * Render document excerpts and chat replies: paragraphs, "•" / "-" / "*"
 * bullets, "1." numbered lists, "#" headings and " | " tables (one row per
 * line, as in the PDFs, or Markdown-style). Consecutive list items or table
 * rows are grouped.
 */
export function RichText({ text }: { text: string }) {
  const lines = text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
  const blocks: ReactNode[] = [];

  for (let i = 0; i < lines.length; ) {
    const line = lines[i];
    if (BULLET.test(line) || NUMBERED.test(line)) {
      const pattern = BULLET.test(line) ? BULLET : NUMBERED;
      const items: string[] = [];
      while (i < lines.length && pattern.test(lines[i])) items.push(lines[i++].replace(pattern, ""));
      const List = pattern === NUMBERED ? "ol" : "ul";
      blocks.push(
        <List key={blocks.length}>
          {items.map((b, j) => (
            <li key={j}>{inline(b)}</li>
          ))}
        </List>,
      );
    } else if (HEADING.test(line)) {
      blocks.push(
        <p key={blocks.length} className="md-heading">
          <strong>{inline(line.replace(HEADING, ""))}</strong>
        </p>,
      );
      i++;
    } else if (isTableRow(line)) {
      const rows: string[][] = [];
      while (i < lines.length && (isTableRow(lines[i]) || TABLE_SEPARATOR.test(lines[i]))) {
        const row = lines[i++];
        if (!TABLE_SEPARATOR.test(row)) rows.push(cells(row));
      }
      const width = Math.max(...rows.map((r) => r.length));
      blocks.push(
        <div className="table-wrap" key={blocks.length}>
          <table>
            <tbody>
              {rows.map((row, r) => (
                <tr key={r}>
                  {Array.from({ length: width }, (_, c) => (
                    <td key={c}>{inline(row[c] ?? "")}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
    } else {
      blocks.push(<p key={blocks.length}>{inline(line)}</p>);
      i++;
    }
  }

  return <div className="rich-text">{blocks}</div>;
}
