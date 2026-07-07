import type { Station } from "./types";

export function bookingUrl(origin: Station, dest: Station, ref: string): string {
  const tomorrow = new Date(Date.now() + 24 * 3600 * 1000).toISOString().slice(0, 10);
  const params = new URLSearchParams({
    origin: origin.name,
    destination: dest.name,
    outwardDate: tomorrow,
  });
  if (ref) params.set("aff", ref);
  return `https://www.thetrainline.com/book/results?${params.toString()}`;
}
