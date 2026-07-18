import { Fragment, useEffect, useRef, useState } from "react";
import { keyNav } from "../lib/keynav";
import type { FieldOption } from "../lib/planner";

interface Props {
  placeholder: string;
  disabled?: boolean;
  hidden?: boolean;
  armed?: boolean; // this is the armed field — the next map click fills it
  value: string; // selected station name, or "" when none
  search: (q: string) => FieldOption[] | Promise<FieldOption[]>;
  onPick: (option: FieldOption) => void;
  onClear: () => void;
  onFocusField: () => void;
  autoEdit?: boolean; // parent wants the entry box opened (e.g. tapped collapsed route line)
  onAutoEditDone?: () => void;
}

export default function StationField(
  { placeholder, disabled, hidden, armed, value, search, onPick, onClear, onFocusField,
    autoEdit, onAutoEditDone }: Props,
) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<FieldOption[]>([]);
  const [active, setActive] = useState(-1);
  const [editing, setEditing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // The keyboard/selection index only walks the selectable (enabled) options.
  const selectable = results.filter((o) => !o.disabled);

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

  useEffect(() => {
    if (!autoEdit || disabled) return;
    setEditing(true);
    setQ("");
    setResults([]);
    requestAnimationFrame(() => inputRef.current?.focus());
    onAutoEditDone?.();
  }, [autoEdit, disabled, onAutoEditDone]);

  function beginEdit() {
    if (disabled) return;
    onFocusField();
    setEditing(true);
    setQ("");
    setResults([]);
    requestAnimationFrame(() => inputRef.current?.focus());
  }

  function pick(option: FieldOption) {
    onPick(option);
    setEditing(false);
    setQ("");
    setResults([]);
    setActive(-1);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    const r = keyNav(e.key, { index: active, count: selectable.length });
    if (r.type === "pass") return;
    e.preventDefault();
    if (r.type === "move") setActive(r.index);
    else if (r.type === "select") pick(selectable[r.index]);
    else {
      setResults([]);
      setActive(-1);
      setEditing(false);
    }
  }

  if (value && !editing) {
    return (
      <div className={`station-field filled${armed ? " active" : ""}`} hidden={hidden}>
        <button className="field-value" onClick={beginEdit} disabled={disabled}>{value}</button>
        <button className="field-clear" onClick={onClear} aria-label="Clear">×</button>
      </div>
    );
  }

  // Walk results, inserting group headers on change and mapping enabled rows to
  // their index within `selectable` for the active highlight.
  let prevGroup: string | null = null;
  let selIndex = -1;
  return (
    <div className={`station-field${armed ? " active" : ""}`} hidden={hidden}>
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
          {results.map((o) => {
            const header = o.group && o.group !== prevGroup
              ? <li key={`h-${o.group}`} className="group-header" aria-hidden="true">{o.group}</li>
              : null;
            prevGroup = o.group || prevGroup;
            const key = o.kind === "city" ? `city-${o.city}` : o.station.id;
            if (o.disabled) {
              return (
                <Fragment key={key}>
                  {header}
                  <li className="opt-row disabled">
                    {o.station.name} <span className="country">{o.station.country}</span>
                  </li>
                </Fragment>
              );
            }
            selIndex += 1;
            const i = selIndex;
            return (
              <Fragment key={key}>
                {header}
                <li className={`opt-row${i === active ? " active" : ""}`}>
                  {/* onMouseDown preventDefault keeps the input from blurring before click */}
                  <button
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => pick(o)}
                    onMouseEnter={() => setActive(i)}
                  >
                    {o.kind === "city"
                      ? o.label
                      : <>{o.station.name} <span className="country">{o.station.country}</span></>}
                  </button>
                </li>
              </Fragment>
            );
          })}
        </ul>
      )}
    </div>
  );
}
