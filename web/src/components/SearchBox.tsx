import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { keyNav } from "../lib/keynav";
import type { Station } from "../lib/types";

export default function SearchBox(props: { onSelect: (s: Station) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Station[]>([]);
  const [active, setActive] = useState(-1);

  useEffect(() => {
    setActive(-1);
    if (q.length < 2) return setResults([]);
    const t = setTimeout(
      () => api.searchStations(q).then((r) => setResults(r.stations)).catch(() => setResults([])),
      250);
    return () => clearTimeout(t);
  }, [q]);

  function pick(s: Station) {
    props.onSelect(s);
    setQ("");
    setResults([]);
    setActive(-1);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    const r = keyNav(e.key, { index: active, count: results.length });
    if (r.type === "pass") return;
    e.preventDefault();
    if (r.type === "move") setActive(r.index);
    else if (r.type === "select") pick(results[r.index]);
    else {
      setResults([]);
      setActive(-1);
    }
  }

  return (
    <div className="search-box">
      <input placeholder="Start from…" value={q} onChange={(e) => setQ(e.target.value)}
             onKeyDown={onKeyDown} />
      {results.length > 0 && (
        <ul>
          {results.map((s, i) => (
            <li key={s.id} className={i === active ? "active" : ""}>
              <button onClick={() => pick(s)} onMouseEnter={() => setActive(i)}>
                {s.name} <span className="country">{s.country}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
