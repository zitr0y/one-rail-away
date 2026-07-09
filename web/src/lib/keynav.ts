export interface KeyNavState {
  index: number; // -1 = nothing highlighted
  count: number;
}

export type KeyNavResult =
  | { type: "move"; index: number }
  | { type: "select"; index: number }
  | { type: "close" }
  | { type: "pass" };

export function keyNav(key: string, state: KeyNavState): KeyNavResult {
  if (state.count === 0) return { type: "pass" };
  if (key === "ArrowDown") return { type: "move", index: (state.index + 1) % state.count };
  if (key === "ArrowUp") {
    const from = state.index === -1 ? 0 : state.index;
    return { type: "move", index: (from - 1 + state.count) % state.count };
  }
  if (key === "Enter") return { type: "select", index: Math.max(0, state.index) };
  if (key === "Escape") return { type: "close" };
  return { type: "pass" };
}
