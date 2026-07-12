// The C0 mascot as a rider: train only — the real journey line replaces the
// logo's baked-in route line and station dots. Returned as a markup string so
// the Marker element can be filled via innerHTML with theme colors baked in.
// viewBox is vertically symmetric about the rail (y=80): with the Marker's
// default center anchor, the wheels sit ON the polyline and rotation pivots
// on the rail point. Spec: 2026-07-12-branding-phase2-design.md §Sprite.
export function riderSvg(stroke: string, hollow: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="32 28 132 104" width="46">
  <path d="M38 80 V46 Q38 36 48 36 H118 Q136 36 146 50 L156 68 Q160 76 152 80 Z"
        stroke="${stroke}" stroke-width="4" fill="${hollow}" stroke-linejoin="round"/>
  <circle cx="58" cy="80" r="7" stroke="${stroke}" stroke-width="3" fill="${hollow}"/>
  <circle cx="126" cy="80" r="7" stroke="${stroke}" stroke-width="3" fill="${hollow}"/>
  <circle cx="122" cy="52" r="2.2" fill="${stroke}"/>
  <circle cx="136" cy="56" r="2.2" fill="${stroke}"/>
  <path d="M124 62 Q130 66 135 61" stroke="${stroke}" stroke-width="2" fill="none"
        stroke-linecap="round"/>
  <path d="M48 46 H100" stroke="${stroke}" stroke-width="2" stroke-dasharray="1 7"
        stroke-linecap="round"/>
  <text x="66" y="70" font-size="15" fill="#ffcc00" stroke="#eab308"
        stroke-width="0.5">★</text>
</svg>`;
}
