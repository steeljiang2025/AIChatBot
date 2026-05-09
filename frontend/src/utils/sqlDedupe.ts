/** 折叠模型把同一条 SQL 用分号粘两遍的情况，与后端 `app/sql_string.py` 行为对齐。 */
export function dedupeSemicolonSql(sql: string): string {
  const t = sql.trim();
  if (!t.toUpperCase().includes("SELECT") || !t.includes(";")) {
    return t;
  }
  const parts = t.split(";");
  const out: string[] = [];
  let prev: string | null = null;
  for (const raw of parts) {
    const seg = raw.trim();
    if (!seg) continue;
    if (seg.toUpperCase().startsWith("SELECT")) {
      const key = seg.replace(/\s+/g, " ");
      if (key === prev) continue;
      prev = key;
      out.push(seg);
    } else {
      prev = null;
      out.push(seg);
    }
  }
  return out.length ? out.join(";") : t;
}
