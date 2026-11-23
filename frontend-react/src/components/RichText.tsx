import type { ReactNode } from "react";

/** Bold "Q:" / "A:" labels used by the FAQ document. */
function inline(text: string): ReactNode[] {
  return text.split(/\b(Q:|A:)/).map((part, i) =>
    part === "Q:" || part === "A:" ? (
      <strong key={i} className="qa-label">
        {part}
      </strong>
    ) : (
      part
    ),
  );
}

const isTableRow = (line: string) => line.includes(" | ");
const isBullet = (line: string) => line.startsWith("•");

/**
 * Render an excerpt: one paragraph, "•" bullet or " | " table row per line.
 * Consecutive bullets become a list; consecutive table rows become a table
 * whose first row is the header when the excerpt starts the table.
 */
export function RichText({ text }: { text: string }) {
  const lines = text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
  const blocks: ReactNode[] = [];

  for (let i = 0; i < lines.length; ) {
    const line = lines[i];
    if (isBullet(line)) {
      const items: string[] = [];
      while (i < lines.length && isBullet(lines[i])) items.push(lines[i++].replace(/^•\s*/, ""));
      blocks.push(
        <ul key={blocks.length}>
          {items.map((b, j) => (
            <li key={j}>{inline(b)}</li>
          ))}
        </ul>,
      );
    } else if (isTableRow(line)) {
      const rows: string[][] = [];
      while (i < lines.length && isTableRow(lines[i])) rows.push(lines[i++].split(" | "));
      const width = Math.max(...rows.map((r) => r.length));
      blocks.push(
        <div className="table-wrap" key={blocks.length}>
          <table>
            <tbody>
              {rows.map((cells, r) => (
                <tr key={r}>
                  {Array.from({ length: width }, (_, c) => (
                    <td key={c}>{cells[c] ?? ""}</td>
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
