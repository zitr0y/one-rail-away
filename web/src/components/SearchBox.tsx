import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Station } from "../lib/types";

export default function SearchBox(props: { onSelect: (s: Station) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Station[]>([]);

  useEffect(() => {
    if (q.length < 2) return setResults([]);
    const t = setTimeout(
      () => api.searchStations(q).then((r) => setResults(r.stations)).catch(() => setResults([])),
      250);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div className="search-box">
      <input placeholder="Start from…" value={q} onChange={(e) => setQ(e.target.value)} />
      {results.length > 0 && (
        <ul>
          {results.map((s) => (
            <li key={s.id}>
              <button onClick={() => { props.onSelect(s); setQ(""); setResults([]); }}>
                {s.name} <span className="country">{s.country}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
