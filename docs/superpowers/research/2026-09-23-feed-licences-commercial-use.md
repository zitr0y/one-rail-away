# Commercial-use licence check (2026-09-23)

Not legal advice. Primary sources were fetched on 2026-09-23 unless marked otherwise.

## 1. db_fern — gtfs.de `fv_free` (derived from DELFI NeTEx)
**Verdict: OK, with conditions.**
- The gtfs.de feed page lists "Source: NeTEx Datensatz, DELFI e.V." and "License: Creative Commons 4.0", which links to CC BY 4.0. The DELFI dataset on opendata-oepnv.de is licensed "Creative Commons Attribution". CC BY allows commercial use and derived works, and it has no share-alike requirement.
- Conditions: credit the source, link the licence, and say that the data was changed.
- Suggested attribution (neither publisher prescribes exact wording): "Timetable data: DELFI e.V. via GTFS.DE, CC BY 4.0 (modified)".
- Sources: https://gtfs.de/en/feeds/de_fv/ , https://www.opendata-oepnv.de (DELFI "deutschlandweite Sollfahrplandaten" dataset)
- Next step: add the credit to the map credits. No email needed.

## 2. rejseplanen — Rejseplanen Labs static GTFS
**Verdict: OK, with conditions. This is explicitly settled.**
- The "Retningslinjer for Labs" (Labs guidelines) say (translated): "you may use our static data in a commercial context, e.g. … show data on a website that is user-paid or advertising-funded". It is the **API** that needs a paid agreement for commercial use, and we do not use the API. Access is "under Creative Commons BY 4.0".
- Conditions ("Use it – don't abuse it"):
  - Do not change the data so that it deviates from the original.
  - Do not present it in a misleading way.
  - Rejseplanen may close access without notice.
  - Our filtering and derived travel times should be fine as long as they are accurate.
- The "Adgang til data" page says access is requested through a contact form. We use the public `rejseplanen.info/labs/GTFS.zip` without registering, so this is a small grey area.
- Suggested attribution: "Timetable data: Rejseplanen, CC BY 4.0 (modified)".
- Sources: https://labs.rejseplanen.dk/hc/en-us/articles/21553298043165-Retningslinjer-for-Labs , https://labs.rejseplanen.dk/hc/en-us/articles/21553113674909
- Next step (optional): send a short note through the Labs contact form describing the use, so there is a record of it.

## 3. cp — Comboios de Portugal (publico.cp.pt/gtfs/gtfs.zip)
**Verdict: Unclear, but probably tolerated.**
- PT NAP record 176 has "Contrato ou Licença: **Sem licença – Sem contrato**". Owner and publisher are both CP (institucional@cp.pt). The download is public, updated weekly, and has no terms page.
- The CC0 tags on dados.gov.pt were applied by Lisbon city council when it republished the data, not by CP.
- No stated licence means no express grant. The permission rests on MMTIS Art. 8 (below) plus the fact that CP publishes the data for reuse through the NAP.
- Suggested attribution: "Timetable data: CP – Comboios de Portugal (via NAP Portugal)".
- Source: https://nap-portugal.imt-ip.pt/nap/multimodalsupplydetail/176
- Next step: email institucional@cp.pt asking them to confirm that commercial reuse of derived data is fine, with attribution.

## 4. trenitalia — Italian NAP asset 1080596 (dataset 1077621)
**Verdict: Unclear, but probably tolerated.**
- The dataset's metadata has the field `licence = no_licence_no_contract` ("No licence – No contract"). This field is hidden on the rendered page and only appears in the page's embedded JSON. There are no other terms.
- Suggested attribution: "Timetable data: Trenitalia S.p.A. (via Italian NAP, cciss.it)".
- Source: https://www.cciss.it/nap/mmtis/public/en/catalog/Dataset/1077621
- Next step: email the NAP operator (CCISS/MIT) or Trenitalia open-data to confirm.
- Side note: **Italo is on the same NAP** (Dataset 1813935, NeTEx L1). This closes the "not researched" gap in data-sources.md.

## MMTIS angle (Delegated Reg. 2017/1926, amended by 2024/490)
- **Art. 8(1):** data on the NAP must be "accessible for exchange and reuse within the Union on a non-discriminatory basis". The regulation does not limit reuse to non-commercial use. The travel-information services it targets are mostly commercial.
- **Art. 8(4):** a publisher *may* impose terms through a licence, and those terms must "not unnecessarily restrict possibilities for reuse". "No licence – No contract" is best read as reuse permitted with no extra terms, beyond what the regulation itself requires. This is my reading, not a binding ruling.
- **Obligations on us when reusing NAP data:**
  - **Art. 8(3):** "the source of those data shall be indicated. The date and time of the last update of the static data shall also be indicated." This applies to CP and Trenitalia, and arguably to every feed, since DELFI and Rejseplanen are NAP publishers too. **Action: show the feed source and last-update date per feed in the credits or coverage view.**
  - **Art. 8(2):** reuse must be "neutral … without discrimination or bias". Ranking must not depend on "the commercial consideration related to the reuse". **With the Trainline affiliate:** do not change the map or reach results based on which journeys Trainline can sell. A Book button that is only shown where a Trainline id exists is fine.
- Sources: https://eur-lex.europa.eu/eli/reg_del/2017/1926/oj/eng , https://eur-lex.europa.eu/eli/reg_del/2024/490/oj/eng . I quoted the Art. 8 text from legislation.gov.uk because EUR-Lex blocked automated fetches. I did not verify whether 2024/490 reworded Art. 8, so check the consolidated text.
