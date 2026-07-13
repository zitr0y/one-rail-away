# Trenitalia national timetable source — research record (2026-07-14)

## Verdict: usable with an explicit reuse caveat

The Italian National Access Point’s [Trenitalia asset 1080596](https://www.cciss.it/nap/mmtis/public/en/catalog/Dataset/1077621)
is a registration-free, authoritative timetable publication. The dataset describes
it as Trenitalia railway-service scheduling data in NeTEx Italian Profile L1; the
asset page identifies its distribution as `gz:xml`, categorizes it as validated,
and exposes a direct download. A `curl -I` check on 2026-07-14 returned HTTP 200,
`application/gzip`, and `IT-IT-TRENITALIA_L1.xml.gz`.

The NAP metadata’s licence value is exactly **“No licence – No contract.”** It does
not grant a named open-data licence, so the feed is included with Trenitalia
attribution and a mandatory re-check before commercial use. This is the same
explicitly caveated metadata state already accepted for the project’s official CP
feed; it must not be represented as CC0, CC BY, or otherwise openly licensed.

## Asset inspection

Downloaded 2026-07-14: 13 MB gzipped XML, publication timestamp
`2026-07-09T12:45:37Z`, one operator (`TRENITALIA`). UIC operating periods span
2026-06-13 through 2026-12-12, covering the project sample date 2026-07-14.

- 1,948 `StopPlace` records; `ScheduledStopPoint → StopPlace` is the actual
  station relationship. IDs carry Trenitalia’s internal 9-digit codes, not a
  documented UIC scheme; names are predominantly all-caps.
- The archive includes foreign stations: Germany (6), Austria (4), France (10),
  plus a malformed coordinate on `NAPOLI AFRAGOLA` (lat 10.1, lon 40.1). Feed
  order therefore follows DB, ÖBB and SNCF, which retain ownership of their
  station canonicals. The parser corrects that upstream defect to 40.931758,
  14.331131, the geotagged station location recorded by Wikimedia/OpenStreetMap.
- `ServiceJourneyPattern` product counts: REG 13,350; RV 1,807; FR 1,505; IC
  701; ICN 533; EC 237; FB 55; FA 48; EN 32; EXP 12; BUS 6,564; SFM 598; MET
  502. The implemented national long-distance selection is FR/FA/FB/EC/IC/ICN/
  EN/EXP; REG/RV/SFM/MET and BUS/FrecciaLink are excluded.

Italo was not added: no registration-free official static timetable feed and
reuse licence was found during this check. No timetable scraping is used.
