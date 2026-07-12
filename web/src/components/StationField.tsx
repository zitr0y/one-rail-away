import { useEffect, useRef, useState } from "react";
import { keyNav } from "../lib/keynav";
import type { Station } from "../lib/types";

interface Props {
  placeholder: string;
  disabled?: boolean;
  armed?: boolean; // this is the armed field — the next map click fills it
  value: string; // selected station name, or "" when none
  search: (q: string) => Station[] | Promise<Station[]>;
  onPick: (s: Station) => void;
  onClear: () => void;
  onFocusField: () => void;
}

export default function StationField(
  { placeholder, disabled, armed, value, search, onPick, onClear, onFocusField }: Props,
) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Station[]>([]);
  const [active, setActive] = useState(-1);
  const [editing, setEditing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // When the parent supplies a new selected value (e.g. filled by a map click),
  // drop back to the chip display.
  useEffect(() => {
    setEditing(false);
    setQ("");
  }, [value]);

  useEffect(() => {
    setActive(-1);
    if (!editing || q.trim().length < 2) {
      setResults([]);
      return;
    }
    let cancelled = false;
    const t = setTimeout(async () => {
      try {
        const r = await search(q);
        if (!cancelled) setResults(r);
      } catch {
        if (!cancelled) setResults([]);
      }
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [q, editing, search]);

  function beginEdit() {
    if (disabled) return;
    onFocusField();
    setEditing(true);
    setQ("");
    setResults([]);
    requestAnimationFrame(() => inputRef.current?.focus());
  }

  function pick(s: Station) {
    onPick(s);
    setEditing(false);
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
      setEditing(false);
    }
  }

  if (value && !editing) {
    return (
      <div className={`station-field filled${armed ? " active" : ""}`}>
        <button className="field-value" onClick={beginEdit} disabled={disabled}>{value}</button>
        <button className="field-clear" onClick={onClear} aria-label="Clear">×</button>
      </div>
    );
  }

  return (
    <div className={`station-field${armed ? " active" : ""}`}>
      <input
        ref={inputRef}
        placeholder={placeholder}
        disabled={disabled}
        value={q}
        onFocus={() => {
          onFocusField();
          setEditing(true);
        }}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={onKeyDown}
      />
      {results.length > 0 && (
        <ul>
          {results.map((s, i) => (
            <li key={s.id} className={i === active ? "active" : ""}>
              {/* onMouseDown preventDefault keeps the input from blurring before click */}
              <button
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pick(s)}
                onMouseEnter={() => setActive(i)}
              >
                {s.name} <span className="country">{s.country}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
