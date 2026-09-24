import { useState } from "react";

const ROWS = [["序列", "财务项目", "预计预算", "实际结算"], ["01", "GPU 训练服务器", "¥45,000", "¥42,500"], ["02", "NAS 集群部署", "¥2,400", "¥2,400"], ["03", "桌面客户端开发", "¥12,000", "¥12,000"]];

export function SpreadsheetPreview() {
  const [sheet, setSheet] = useState("Sheet 1");
  return <div className="preview-spreadsheet"><div className="preview-tabs">{["Sheet 1", "Sheet 2", "Summary"].map((name) => <button key={name} type="button" className={sheet === name ? "is-active" : ""} onClick={() => setSheet(name)}>{name}</button>)}</div><div className="preview-grid-scroll"><table className="preview-grid"><thead><tr>{ROWS[0]?.map((cell) => <th key={cell}>{cell}</th>)}</tr></thead><tbody>{ROWS.slice(1).map((row) => <tr key={row[0]}>{row.map((cell) => <td key={cell}>{cell}</td>)}</tr>)}</tbody></table></div></div>;
}
