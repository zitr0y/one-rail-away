import type { Station } from "./types";

export function localDate(offsetDays = 0, now = new Date()): string {
  const date = new Date(now);
  date.setDate(date.getDate() + offsetDays);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function bookingUrl(origin: Station, dest: Station, date: string, ref: string): string {
  const params = new URLSearchParams();
  if (ref) params.set("aff", ref);
  const route = [origin.name, dest.name, date].map(encodeURIComponent).join("/");
  return `https://www.trainline.eu/search/${route}/${params.size ? `?${params}` : ""}`;
}
