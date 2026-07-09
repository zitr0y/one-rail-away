export function statusText(origin: string | null, dest: string | null): string | null {
  if (!origin) return null;
  return dest ? `${origin} → ${dest}` : `From ${origin} — click a dot for details`;
}
