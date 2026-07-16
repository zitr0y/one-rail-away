# Intra-City Transfer Candidates for RAPTOR Engine

> [!NOTE]
> This document lists European cities with multiple railway terminals and analyzes their pairwise connectivity.
> It identifies where the routing engine needs injected synthetic transfer edges to enable passenger journeys
> across terminals (e.g. walking or local transit) in the absence of direct train connections.

## Shortlist of Cities Needing Transfer Edges
These cities have major disconnected terminals (zero direct connectivity) that represent independent hubs. Injected synthetic transfer edges are **critical** for successful routing (e.g., to fix failed routes like Lille → Forbach via Paris).

| City | Major Disconnected Pairs | Max Stations Distance | Max Destinations | User Impact / Priority |
| :--- | :--- | :---: | :---: | :--- |
| **Hamburg** | Hamburg-Harburg(S) ↔ Hamburg-Langenfelde Bf, Hamburg-Harburg(S) ↔ Hamburg-Eidelstedt Bf | 16.48 km | 1125 | High |
| **Berlin** | Berlin Ostkreuz ↔ Berlin-Spandau, Berlin Ostkreuz ↔ Berlin Gesundbrunnen, Berlin Ostkreuz ↔ Berlin Südkreuz, Berlin Ostkreuz ↔ Berlin Hbf | 18.72 km | 1248 | High |
| **Frankfurt** | Frankfurt(M) Flughafen Fernbf ↔ Frankfurt(Main)West, Frankfurt(Main)West ↔ Frankfurt(Main)Süd, Frankfurt(Main)Süd ↔ Frankfurt(Main)Hbf | 9.80 km | 1208 | High |
| **Wien** | Wien Hbf ↔ Wien Hütteldorf, Wien Westbahnhof ↔ Wien Hauptbahnhof Autoreisezug, Wien Meidling ↔ Wien Hütteldorf, Wien Hütteldorf ↔ Wien Hauptbahnhof Autoreisezug | 9.94 km | 1051 | High |
| **Amsterdam** | Amsterdam Centraal ↔ Amsterdam Zuid, Amsterdam Sloterdijk ↔ Amsterdam Zuid, Amsterdam Zuid ↔ Amsterdam Amstel | 11.31 km | 926 | High |
| **Köln** | Köln Hbf ↔ Köln Messe/Deutz | 13.33 km | 1184 | High |
| **Zürich** | Zürich Flughafen ↔ Zürich Enge, Zürich Oerlikon ↔ Zürich Enge | 9.88 km | 736 | High |
| **Paris** | Paris Est ↔ Paris Gare du Nord, Paris Est ↔ Paris Montparnasse Hall 1 - 2, Paris Est ↔ Paris Austerlitz, Paris Est ↔ Paris Gare de Lyon Hall 1 - 2, Paris Est ↔ Paris Bercy Bourg. Pays d'Auv., Paris Gare du Nord ↔ Paris Montparnasse Hall 1 - 2, Paris Gare du Nord ↔ Paris Austerlitz, Paris Gare du Nord ↔ Paris Gare de Lyon Hall 1 - 2, Paris Gare du Nord ↔ Paris Bercy Bourg. Pays d'Auv., Paris Montparnasse Hall 1 - 2 ↔ Paris Austerlitz, Paris Montparnasse Hall 1 - 2 ↔ Paris Gare de Lyon Hall 1 - 2, Paris Montparnasse Hall 1 - 2 ↔ Paris Bercy Bourg. Pays d'Auv., Paris Austerlitz ↔ Paris Gare de Lyon Hall 1 - 2, Paris Austerlitz ↔ Paris Bercy Bourg. Pays d'Auv., Paris Gare de Lyon Hall 1 - 2 ↔ Paris Bercy Bourg. Pays d'Auv. | 5.01 km | 709 | Critical (Prime Hub, 6 major terminals completely disconnected) |
| **Jena** | Jena Paradies ↔ Jena West | 0.70 km | 664 | Medium (Paradies Saalbahn ↔ West Weimar-Gera line, ~700m) |
| **Budapest** | Budapest-Nyugati ↔ Budapest-Keleti | 2.30 km | 667 | High (Keleti ↔ Nyugati separate major terminals) |
| **Ústí** | Ústí nad Orlicí ↔ Ústí nad Orlicí město | 1.25 km | 607 | Low (Ústí nad Orlicí ↔ Ústí nad Orlicí město) |
| **Lille** | Lille Europe ↔ Lille Flandres | 0.52 km | 598 | High (Europe Eurostar/TGV ↔ Flandres regional, ~500m walk) |
| **Grenchen** | Grenchen Nord ↔ Grenchen Süd | 0.72 km | 554 | Low (Grenchen Nord ↔ Grenchen Süd regional lines) |
| **Avignon** | Avignon TGV ↔ Avignon Centre | 2.70 km | 749 | Medium (Avignon TGV ↔ Avignon Centre regional) |
| **Massy** | Massy-Palaiseau ↔ Massy TGV | 0.28 km | 568 | Medium (Massy TGV ↔ Massy-Palaiseau regional, adjacent) |
| **Madrid** | Madrid-Chamartín-Clara Campoamor ↔ Madrid-Puerta de Atocha-Almudena Grandes, Madrid-Puerta de Atocha-Almudena Grandes ↔ Madrid-Atocha Cercanías | 7.23 km | 184 | High (Links North/South high-speed networks - Chamartín & Atocha) |
| **Bern** | Bern Brünnen Westside ↔ Bern Bümpliz Nord | 1.12 km | 235 | Low (Suburban S-Bahn stops) |
| **València** | València-Estació del Nord ↔ València-Joaquín Sorolla | 1.00 km | 159 | High (Joaquín Sorolla high-speed ↔ Estació del Nord regional) |
| **Medina** | Medina del Campo ↔ Medina del Campo AV | 0.02 km | 151 | Medium (Medina del Campo AV high-speed ↔ conventional) |

## Borderline Cities
These cities have pairs with extremely low direct connectivity (e.g., exactly 1 train/day) or disconnected pairs where one station is a smaller hub (10–25 destinations). Adding transfer edges is **optional but recommended** to improve routing robustness.

| City | Low-Connectivity Pairs | Direct Trains/Day | Distance | Verdict Reason |
| :--- | :--- | :---: | :---: | :--- |
| **Graz** | Graz Hbf ↔ Graz Liebenau Murpark | 1/0 | 5.06 km | Low frequency or secondary terminal |
| **Graz** | Graz Don Bosco Bahnhof ↔ Graz Ostbahnhof | 1/1 | 2.28 km | Low frequency or secondary terminal |
| **Graz** | Graz Don Bosco Bahnhof ↔ Graz Liebenau Murpark | 1/0 | 3.97 km | Low frequency or secondary terminal |
| **Graz** | Graz Ostbahnhof ↔ Graz Puntigam Bahnhof | 1/1 | 2.98 km | Low frequency or secondary terminal |
| **Graz** | Graz Ostbahnhof ↔ Graz Liebenau Murpark | 1/0 | 1.89 km | Low frequency or secondary terminal |
| **Villach** | Villach Hbf ↔ Villach Westbahnhof | 1/0 | 1.19 km | Low frequency or secondary terminal |
| **Villach** | Villach Westbahnhof ↔ Villach Warmbad Bahnhst | 1/0 | 2.52 km | Low frequency or secondary terminal |
| **Zgorzelec** | Zgorzelec ↔ Zgorzelec Miasto | 1/1 | 1.99 km | Low frequency or secondary terminal |
| **S** | Słomniki Miasto ↔ Słomniki | 1/1 | 1.74 km | Low frequency or secondary terminal |
| **Bregenz** | Bregenz ↔ Bregenz Riedenburg Bahnhof | 0/1 | 1.73 km | Low frequency or secondary terminal |
| **Kitzbühel** | Kitzbühel Bahnhof ↔ Kitzbühel Hahnenkamm Bahnhof | 0/1 | 1.18 km | Low frequency or secondary terminal |
| **Chorzów** | Chorzów Miasto ↔ Chorzów Batory | 1/0 | 2.21 km | Low frequency or secondary terminal |
| **Szob** | Szob ↔ Szob(Gr) | 1/1 | 1.36 km | Low frequency or secondary terminal |
| **Bad** | Bad Mitterndorf Bahnhof ↔ Bad Mitterndorf-Heilbrunn Bahnhof | 1/1 | 1.49 km | Low frequency or secondary terminal |

## Benchmark Case Studies

### 1. Paris (NEEDS: Critical Example)
Paris represents the archetypal case of disconnected terminals. Six major terminals handle high-speed and regional rail, but there are **zero** direct trains between any of them. The RAPTOR engine fails to route journeys traversing Paris (e.g. Lille → Forbach via Nord ↔ Est) without synthetic transfer edges.

| Station A | Station B | Direct Trains/Day | Distance | Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Paris Est (677 dests) | Paris Gare du Nord (464 dests) | 0/0 | 0.47 km | NEEDS |
| Paris Est (677 dests) | Paris Montparnasse Hall 1 - 2 (223 dests) | 0/0 | 4.88 km | NEEDS |
| Paris Est (677 dests) | Paris Austerlitz (225 dests) | 0/0 | 3.88 km | NEEDS |
| Paris Est (677 dests) | Paris Gare de Lyon Hall 1 - 2 (709 dests) | 0/0 | 3.71 km | NEEDS |
| Paris Est (677 dests) | Paris Bercy Bourg. Pays d'Auv. (105 dests) | 0/0 | 4.54 km | NEEDS |
| Paris Gare du Nord (464 dests) | Paris Montparnasse Hall 1 - 2 (223 dests) | 0/0 | 5.01 km | NEEDS |
| Paris Gare du Nord (464 dests) | Paris Austerlitz (225 dests) | 0/0 | 4.27 km | NEEDS |
| Paris Gare du Nord (464 dests) | Paris Gare de Lyon Hall 1 - 2 (709 dests) | 0/0 | 4.14 km | NEEDS |
| Paris Gare du Nord (464 dests) | Paris Bercy Bourg. Pays d'Auv. (105 dests) | 0/0 | 4.99 km | NEEDS |
| Paris Montparnasse Hall 1 - 2 (223 dests) | Paris Austerlitz (225 dests) | 0/0 | 3.25 km | NEEDS |
| Paris Montparnasse Hall 1 - 2 (223 dests) | Paris Gare de Lyon Hall 1 - 2 (709 dests) | 0/0 | 3.90 km | NEEDS |
| Paris Montparnasse Hall 1 - 2 (223 dests) | Paris Bercy Bourg. Pays d'Auv. (105 dests) | 0/0 | 4.56 km | NEEDS |
| Paris Austerlitz (225 dests) | Paris Gare de Lyon Hall 1 - 2 (709 dests) | 0/0 | 0.69 km | NEEDS |
| Paris Austerlitz (225 dests) | Paris Bercy Bourg. Pays d'Auv. (105 dests) | 0/0 | 1.35 km | NEEDS |
| Paris Gare de Lyon Hall 1 - 2 (709 dests) | Paris Bercy Bourg. Pays d'Auv. (105 dests) | 0/0 | 0.93 km | NEEDS |

### 2. Warszawa (FINE: Counter-Example)
Warszawa's terminals are perfectly connected via the cross-city railway line (*Linia Średnicowa*). Almost all long-distance trains call at Warszawa West (Zachodnia), Central (Centralna), and East (Wschodnia). **No synthetic transfer edges are needed** because real trains provide ~135–139 connections per day between them.

| Station A | Station B | Direct Trains/Day | Distance | Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Warszawa Centralna (1011 dests) | Warszawa Wschodnia (982 dests) | 136/139 | 4.19 km | FINE |
| Warszawa Centralna (1011 dests) | Warszawa Zachodnia (1011 dests) | 138/136 | 2.77 km | FINE |
| Warszawa Wschodnia (982 dests) | Warszawa Zachodnia (1011 dests) | 137/135 | 6.89 km | FINE |

## Data Caveats
1. **Stations Missing Reach Files (has_reach = False)**:
   - **Milano Centrale** (ID: `x:db_fern:629565`): Appears as a major destination in the data, but has no origin reach file (`n_dest = 0`, `has_reach = False`). This is because Italy (Trenitalia) is not fully ingested as a search origin country. A transfer edge to **Milano Porta Garibaldi** is still highly recommended because of Centrale's real-world status as Milan's primary hub.
   - **Frankfurt(M) Flughafen Regionalbf** (ID: `x:db_fern:429875`): Located adjacent to the Fernbahnhof, but has `has_reach = False`. This is expected as regional/S-Bahn stops are filtered out as routing search origins to keep computation times reasonable.
2. **London Terminals**:
   - **London St. Pancras Int.** is the only London station present in the dataset. Because the UK national GTFS feed is not ingested, other London terminals (King's Cross, Euston, Paddington, etc.) do not appear. Thus, London is categorized as **FINE** inside the dataset, but in a full European rollout it would definitely need transfer edges.
3. **Brussels Terminals**:
   - **Bruxelles Midi** ↔ **Bruxelles-Nord** has 7 direct trains/day in the feeds. While this is lower than the actual real-world frequency (which is hundreds per day), it is sufficient for the routing engine to connect them, making the city **FINE**.

## Detailed Connectivity and Verdicts per City
Below is the complete dataset for all clustered same-city station groups.

### Hamburg (Verdict: NEEDS transfer edges)
**Cluster members:** Hamburg Dammtor, Hamburg-Harburg(S), Hamburg-Altona(S), Hamburg Hbf, Hamburg-Langenfelde Bf, Hamburg-Eidelstedt Bf

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Hamburg Dammtor (1112 dests) | Hamburg-Harburg(S) (832 dests) | 34 / 17 | 11.61 km | FINE |
| Hamburg Dammtor (1112 dests) | Hamburg-Altona(S) (1111 dests) | 26 / 26 | 3.66 km | FINE |
| Hamburg Dammtor (1112 dests) | Hamburg Hbf (1125 dests) | 56 / 34 | 1.51 km | FINE |
| Hamburg Dammtor (1112 dests) | Hamburg-Langenfelde Bf (447 dests) | 5 / 5 | 4.39 km | FINE |
| Hamburg Dammtor (1112 dests) | Hamburg-Eidelstedt Bf (447 dests) | 5 / 5 | 6.71 km | FINE |
| Hamburg-Harburg(S) (832 dests) | Hamburg-Altona(S) (1111 dests) | 19 / 20 | 11.38 km | FINE |
| Hamburg-Harburg(S) (832 dests) | Hamburg Hbf (1125 dests) | 38 / 41 | 10.77 km | FINE |
| Hamburg-Harburg(S) (832 dests) | Hamburg-Langenfelde Bf (447 dests) | 0 / 0 | 14.25 km | NEEDS |
| Hamburg-Harburg(S) (832 dests) | Hamburg-Eidelstedt Bf (447 dests) | 0 / 0 | 16.48 km | NEEDS |
| Hamburg-Altona(S) (1111 dests) | Hamburg Hbf (1125 dests) | 44 / 42 | 4.79 km | FINE |
| Hamburg-Altona(S) (1111 dests) | Hamburg-Langenfelde Bf (447 dests) | 1 / 1 | 2.93 km | BORDERLINE |
| Hamburg-Altona(S) (1111 dests) | Hamburg-Eidelstedt Bf (447 dests) | 1 / 1 | 5.10 km | BORDERLINE |
| Hamburg Hbf (1125 dests) | Hamburg-Langenfelde Bf (447 dests) | 5 / 5 | 5.90 km | FINE |
| Hamburg Hbf (1125 dests) | Hamburg-Eidelstedt Bf (447 dests) | 5 / 5 | 8.22 km | FINE |
| Hamburg-Langenfelde Bf (447 dests) | Hamburg-Eidelstedt Bf (447 dests) | 5 / 5 | 2.42 km | FINE |

### Berlin (Verdict: NEEDS transfer edges)
**Cluster members:** Berlin Ostkreuz, Berlin-Spandau, Berlin Gesundbrunnen, Berlin Südkreuz, Berlin Hbf

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Berlin Ostkreuz (290 dests) | Berlin-Spandau (1091 dests) | 0 / 0 | 18.72 km | NEEDS |
| Berlin Ostkreuz (290 dests) | Berlin Gesundbrunnen (1058 dests) | 0 / 0 | 7.45 km | NEEDS |
| Berlin Ostkreuz (290 dests) | Berlin Südkreuz (1209 dests) | 0 / 0 | 7.66 km | NEEDS |
| Berlin Ostkreuz (290 dests) | Berlin Hbf (1248 dests) | 0 / 0 | 7.22 km | NEEDS |
| Berlin-Spandau (1091 dests) | Berlin Gesundbrunnen (1058 dests) | 2 / 2 | 13.00 km | FINE |
| Berlin-Spandau (1091 dests) | Berlin Südkreuz (1209 dests) | 35 / 30 | 13.15 km | FINE |
| Berlin-Spandau (1091 dests) | Berlin Hbf (1248 dests) | 52 / 49 | 11.65 km | FINE |
| Berlin Gesundbrunnen (1058 dests) | Berlin Südkreuz (1209 dests) | 22 / 33 | 8.28 km | FINE |
| Berlin Gesundbrunnen (1058 dests) | Berlin Hbf (1248 dests) | 22 / 33 | 2.87 km | FINE |
| Berlin Südkreuz (1209 dests) | Berlin Hbf (1248 dests) | 83 / 90 | 5.58 km | FINE |

### Frankfurt (Verdict: NEEDS transfer edges)
**Cluster members:** Frankfurt(M) Flughafen Fernbf, Frankfurt(M) Flughafen Regionalbf, Frankfurt(Main)West, Frankfurt(Main)Süd, Frankfurt(Main)Hbf

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Frankfurt(M) Flughafen Fernbf (935 dests) | Frankfurt(M) Flughafen Regionalbf (0 dests) | 0 / N/A | 0.22 km | FINE (minor station) |
| Frankfurt(M) Flughafen Fernbf (935 dests) | Frankfurt(Main)West (407 dests) | 0 / 0 | 8.87 km | NEEDS |
| Frankfurt(M) Flughafen Fernbf (935 dests) | Frankfurt(Main)Süd (956 dests) | 0 / 4 | 9.76 km | FINE |
| Frankfurt(M) Flughafen Fernbf (935 dests) | Frankfurt(Main)Hbf (1208 dests) | 52 / 8 | 8.90 km | FINE |
| Frankfurt(M) Flughafen Regionalbf (0 dests) | Frankfurt(Main)West (407 dests) | N/A / 0 | 9.00 km | FINE (minor station) |
| Frankfurt(M) Flughafen Regionalbf (0 dests) | Frankfurt(Main)Süd (956 dests) | N/A / 0 | 9.80 km | FINE (minor station) |
| Frankfurt(M) Flughafen Regionalbf (0 dests) | Frankfurt(Main)Hbf (1208 dests) | N/A / 0 | 8.98 km | FINE (minor station) |
| Frankfurt(Main)West (407 dests) | Frankfurt(Main)Süd (956 dests) | 0 / 0 | 3.99 km | NEEDS |
| Frankfurt(Main)West (407 dests) | Frankfurt(Main)Hbf (1208 dests) | 3 / 0 | 2.13 km | FINE |
| Frankfurt(Main)Süd (956 dests) | Frankfurt(Main)Hbf (1208 dests) | 0 / 0 | 1.89 km | NEEDS |

### Wien (Verdict: NEEDS transfer edges)
**Cluster members:** Wien Hbf, Wien Westbahnhof, Wien Meidling, Wien Hütteldorf, Wien Hauptbahnhof Autoreisezug

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Wien Hbf (1051 dests) | Wien Westbahnhof (652 dests) | 25 / 25 | 3.19 km | FINE |
| Wien Hbf (1051 dests) | Wien Meidling (1051 dests) | 142 / 142 | 3.42 km | FINE |
| Wien Hbf (1051 dests) | Wien Hütteldorf (347 dests) | 0 / 0 | 8.71 km | NEEDS |
| Wien Hbf (1051 dests) | Wien Hauptbahnhof Autoreisezug (125 dests) | 1 / 1 | 1.38 km | BORDERLINE |
| Wien Westbahnhof (652 dests) | Wien Meidling (1051 dests) | 25 / 25 | 2.47 km | FINE |
| Wien Westbahnhof (652 dests) | Wien Hütteldorf (347 dests) | 1 / 1 | 5.68 km | BORDERLINE |
| Wien Westbahnhof (652 dests) | Wien Hauptbahnhof Autoreisezug (125 dests) | 0 / 0 | 4.55 km | NEEDS |
| Wien Meidling (1051 dests) | Wien Hütteldorf (347 dests) | 0 / 0 | 5.95 km | NEEDS |
| Wien Meidling (1051 dests) | Wien Hauptbahnhof Autoreisezug (125 dests) | 1 / 1 | 4.32 km | BORDERLINE |
| Wien Hütteldorf (347 dests) | Wien Hauptbahnhof Autoreisezug (125 dests) | 0 / 0 | 9.94 km | NEEDS |

### Amsterdam (Verdict: NEEDS transfer edges)
**Cluster members:** Amsterdam Centraal, Amsterdam Bijlmer ArenA, Amsterdam Sloterdijk, Amsterdam Zuid, Amsterdam Amstel

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Amsterdam Centraal (926 dests) | Amsterdam Bijlmer ArenA (403 dests) | 7 / 7 | 8.12 km | FINE |
| Amsterdam Centraal (926 dests) | Amsterdam Sloterdijk (466 dests) | 172 / 170 | 4.35 km | FINE |
| Amsterdam Centraal (926 dests) | Amsterdam Zuid (475 dests) | 0 / 0 | 4.84 km | NEEDS |
| Amsterdam Centraal (926 dests) | Amsterdam Amstel (461 dests) | 99 / 99 | 3.84 km | FINE |
| Amsterdam Bijlmer ArenA (403 dests) | Amsterdam Sloterdijk (466 dests) | 2 / 3 | 11.31 km | FINE |
| Amsterdam Bijlmer ArenA (403 dests) | Amsterdam Zuid (475 dests) | 97 / 98 | 5.85 km | FINE |
| Amsterdam Bijlmer ArenA (403 dests) | Amsterdam Amstel (461 dests) | 4 / 3 | 4.29 km | FINE |
| Amsterdam Sloterdijk (466 dests) | Amsterdam Zuid (475 dests) | 0 / 0 | 6.04 km | NEEDS |
| Amsterdam Sloterdijk (466 dests) | Amsterdam Amstel (461 dests) | 98 / 96 | 7.24 km | FINE |
| Amsterdam Zuid (475 dests) | Amsterdam Amstel (461 dests) | 0 / 0 | 3.25 km | NEEDS |

### Köln (Verdict: NEEDS transfer edges)
**Cluster members:** Köln/Bonn Flughafen, Köln Hbf, Köln Messe/Deutz

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Köln/Bonn Flughafen (683 dests) | Köln Hbf (1184 dests) | 2 / 0 | 13.33 km | FINE |
| Köln/Bonn Flughafen (683 dests) | Köln Messe/Deutz (695 dests) | 1 / 1 | 12.24 km | BORDERLINE |
| Köln Hbf (1184 dests) | Köln Messe/Deutz (695 dests) | 0 / 0 | 1.16 km | NEEDS |

### Zürich (Verdict: NEEDS transfer edges)
**Cluster members:** Zürich Flughafen, Zürich Oerlikon, Zürich HB, Zürich Enge

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Zürich Flughafen (664 dests) | Zürich Oerlikon (663 dests) | 53 / 54 | 4.53 km | FINE |
| Zürich Flughafen (664 dests) | Zürich HB (736 dests) | 130 / 125 | 8.20 km | FINE |
| Zürich Flughafen (664 dests) | Zürich Enge (398 dests) | 0 / 0 | 9.88 km | NEEDS |
| Zürich Oerlikon (663 dests) | Zürich HB (736 dests) | 53 / 54 | 3.72 km | FINE |
| Zürich Oerlikon (663 dests) | Zürich Enge (398 dests) | 0 / 0 | 5.37 km | NEEDS |
| Zürich HB (736 dests) | Zürich Enge (398 dests) | 2 / 3 | 1.72 km | FINE |

### Paris (Verdict: NEEDS transfer edges)
**Cluster members:** Paris Est, Paris Gare du Nord, Paris Montparnasse Hall 1 - 2, Paris Austerlitz, Paris Gare de Lyon Hall 1 - 2, Paris Bercy Bourg. Pays d'Auv.

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Paris Est (677 dests) | Paris Gare du Nord (464 dests) | 0 / 0 | 0.47 km | NEEDS |
| Paris Est (677 dests) | Paris Montparnasse Hall 1 - 2 (223 dests) | 0 / 0 | 4.88 km | NEEDS |
| Paris Est (677 dests) | Paris Austerlitz (225 dests) | 0 / 0 | 3.88 km | NEEDS |
| Paris Est (677 dests) | Paris Gare de Lyon Hall 1 - 2 (709 dests) | 0 / 0 | 3.71 km | NEEDS |
| Paris Est (677 dests) | Paris Bercy Bourg. Pays d'Auv. (105 dests) | 0 / 0 | 4.54 km | NEEDS |
| Paris Gare du Nord (464 dests) | Paris Montparnasse Hall 1 - 2 (223 dests) | 0 / 0 | 5.01 km | NEEDS |
| Paris Gare du Nord (464 dests) | Paris Austerlitz (225 dests) | 0 / 0 | 4.27 km | NEEDS |
| Paris Gare du Nord (464 dests) | Paris Gare de Lyon Hall 1 - 2 (709 dests) | 0 / 0 | 4.14 km | NEEDS |
| Paris Gare du Nord (464 dests) | Paris Bercy Bourg. Pays d'Auv. (105 dests) | 0 / 0 | 4.99 km | NEEDS |
| Paris Montparnasse Hall 1 - 2 (223 dests) | Paris Austerlitz (225 dests) | 0 / 0 | 3.25 km | NEEDS |
| Paris Montparnasse Hall 1 - 2 (223 dests) | Paris Gare de Lyon Hall 1 - 2 (709 dests) | 0 / 0 | 3.90 km | NEEDS |
| Paris Montparnasse Hall 1 - 2 (223 dests) | Paris Bercy Bourg. Pays d'Auv. (105 dests) | 0 / 0 | 4.56 km | NEEDS |
| Paris Austerlitz (225 dests) | Paris Gare de Lyon Hall 1 - 2 (709 dests) | 0 / 0 | 0.69 km | NEEDS |
| Paris Austerlitz (225 dests) | Paris Bercy Bourg. Pays d'Auv. (105 dests) | 0 / 0 | 1.35 km | NEEDS |
| Paris Gare de Lyon Hall 1 - 2 (709 dests) | Paris Bercy Bourg. Pays d'Auv. (105 dests) | 0 / 0 | 0.93 km | NEEDS |

### Jena (Verdict: NEEDS transfer edges)
**Cluster members:** Jena Paradies, Jena West

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Jena Paradies (664 dests) | Jena West (538 dests) | 0 / 0 | 0.70 km | NEEDS |

### Budapest (Verdict: NEEDS transfer edges)
**Cluster members:** Budapest-Nyugati, Budapest-Keleti

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Budapest-Nyugati (466 dests) | Budapest-Keleti (667 dests) | 0 / 0 | 2.30 km | NEEDS |

### Ústí (Verdict: NEEDS transfer edges)
**Cluster members:** Ústí nad Orlicí, Ústí nad Orlicí město

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Ústí nad Orlicí (445 dests) | Ústí nad Orlicí město (607 dests) | 0 / 0 | 1.25 km | NEEDS |

### Lille (Verdict: NEEDS transfer edges)
**Cluster members:** Lille Europe, Lille Flandres

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Lille Europe (598 dests) | Lille Flandres (364 dests) | 0 / 0 | 0.52 km | NEEDS |

### Grenchen (Verdict: NEEDS transfer edges)
**Cluster members:** Grenchen Nord, Grenchen Süd

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Grenchen Nord (554 dests) | Grenchen Süd (387 dests) | 0 / 0 | 0.72 km | NEEDS |

### Avignon (Verdict: NEEDS transfer edges)
**Cluster members:** Avignon TGV, Avignon Centre

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Avignon TGV (749 dests) | Avignon Centre (48 dests) | 0 / 0 | 2.70 km | NEEDS |

### Massy (Verdict: NEEDS transfer edges)
**Cluster members:** Massy-Palaiseau, Massy TGV

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Massy-Palaiseau (209 dests) | Massy TGV (568 dests) | 0 / 0 | 0.28 km | NEEDS |

### Madrid (Verdict: NEEDS transfer edges)
**Cluster members:** Madrid-Chamartín-Clara Campoamor, Madrid-Puerta de Atocha-Almudena Grandes, Madrid-Atocha Cercanías

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Madrid-Chamartín-Clara Campoamor (156 dests) | Madrid-Puerta de Atocha-Almudena Grandes (184 dests) | 0 / 0 | 7.23 km | NEEDS |
| Madrid-Chamartín-Clara Campoamor (156 dests) | Madrid-Atocha Cercanías (126 dests) | 8 / 8 | 7.20 km | FINE |
| Madrid-Puerta de Atocha-Almudena Grandes (184 dests) | Madrid-Atocha Cercanías (126 dests) | 0 / 0 | 0.12 km | NEEDS |

### Bern (Verdict: NEEDS transfer edges)
**Cluster members:** Bern Brünnen Westside, Bern Bümpliz Nord

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Bern Brünnen Westside (235 dests) | Bern Bümpliz Nord (229 dests) | 0 / 0 | 1.12 km | NEEDS |

### València (Verdict: NEEDS transfer edges)
**Cluster members:** València-Estació del Nord, València-Joaquín Sorolla

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| València-Estació del Nord (158 dests) | València-Joaquín Sorolla (159 dests) | 0 / 0 | 1.00 km | NEEDS |

### Medina (Verdict: NEEDS transfer edges)
**Cluster members:** Medina del Campo, Medina del Campo AV

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Medina del Campo (151 dests) | Medina del Campo AV (120 dests) | 0 / 0 | 0.02 km | NEEDS |

### Graz (Verdict: BORDERLINE)
**Cluster members:** Graz Hbf, Graz Don Bosco Bahnhof, Graz Ostbahnhof, Graz Puntigam Bahnhof, Graz Liebenau Murpark

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Graz Hbf (772 dests) | Graz Don Bosco Bahnhof (437 dests) | 3 / 3 | 1.55 km | FINE |
| Graz Hbf (772 dests) | Graz Ostbahnhof (212 dests) | 2 / 2 | 3.19 km | FINE |
| Graz Hbf (772 dests) | Graz Puntigam Bahnhof (459 dests) | 3 / 3 | 4.76 km | FINE |
| Graz Hbf (772 dests) | Graz Liebenau Murpark (80 dests) | 1 / 0 | 5.06 km | BORDERLINE |
| Graz Don Bosco Bahnhof (437 dests) | Graz Ostbahnhof (212 dests) | 1 / 1 | 2.28 km | BORDERLINE |
| Graz Don Bosco Bahnhof (437 dests) | Graz Puntigam Bahnhof (459 dests) | 2 / 2 | 3.22 km | FINE |
| Graz Don Bosco Bahnhof (437 dests) | Graz Liebenau Murpark (80 dests) | 1 / 0 | 3.97 km | BORDERLINE |
| Graz Ostbahnhof (212 dests) | Graz Puntigam Bahnhof (459 dests) | 1 / 1 | 2.98 km | BORDERLINE |
| Graz Ostbahnhof (212 dests) | Graz Liebenau Murpark (80 dests) | 1 / 0 | 1.89 km | BORDERLINE |
| Graz Puntigam Bahnhof (459 dests) | Graz Liebenau Murpark (80 dests) | 0 / 0 | 2.94 km | FINE (connected via hub) |

### Villach (Verdict: BORDERLINE)
**Cluster members:** Villach Hbf, Villach Westbahnhof, Villach Warmbad Bahnhst

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Villach Hbf (882 dests) | Villach Westbahnhof (194 dests) | 1 / 0 | 1.19 km | BORDERLINE |
| Villach Hbf (882 dests) | Villach Warmbad Bahnhst (292 dests) | 2 / 2 | 3.70 km | FINE |
| Villach Westbahnhof (194 dests) | Villach Warmbad Bahnhst (292 dests) | 1 / 0 | 2.52 km | BORDERLINE |

### Zgorzelec (Verdict: BORDERLINE)
**Cluster members:** Zgorzelec, Zgorzelec Miasto

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Zgorzelec (655 dests) | Zgorzelec Miasto (655 dests) | 1 / 1 | 1.99 km | BORDERLINE |

### S (Verdict: BORDERLINE)
**Cluster members:** Słomniki Miasto, Słomniki

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Słomniki Miasto (572 dests) | Słomniki (572 dests) | 1 / 1 | 1.74 km | BORDERLINE |

### Bregenz (Verdict: BORDERLINE)
**Cluster members:** Bregenz, Bregenz Riedenburg Bahnhof

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Bregenz (800 dests) | Bregenz Riedenburg Bahnhof (340 dests) | 0 / 1 | 1.73 km | BORDERLINE |

### Kitzbühel (Verdict: BORDERLINE)
**Cluster members:** Kitzbühel Bahnhof, Kitzbühel Hahnenkamm Bahnhof

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Kitzbühel Bahnhof (422 dests) | Kitzbühel Hahnenkamm Bahnhof (422 dests) | 0 / 1 | 1.18 km | BORDERLINE |

### Chorzów (Verdict: BORDERLINE)
**Cluster members:** Chorzów Miasto, Chorzów Batory

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Chorzów Miasto (557 dests) | Chorzów Batory (253 dests) | 1 / 0 | 2.21 km | BORDERLINE |

### Szob (Verdict: BORDERLINE)
**Cluster members:** Szob, Szob(Gr)

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Szob (466 dests) | Szob(Gr) (311 dests) | 1 / 1 | 1.36 km | BORDERLINE |

### Bad (Verdict: BORDERLINE)
**Cluster members:** Bad Mitterndorf Bahnhof, Bad Mitterndorf-Heilbrunn Bahnhof

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Bad Mitterndorf Bahnhof (241 dests) | Bad Mitterndorf-Heilbrunn Bahnhof (241 dests) | 1 / 1 | 1.49 km | BORDERLINE |

### Warszawa (Verdict: FINE)
**Cluster members:** Warszawa Centralna, Warszawa Wschodnia, Warszawa Zachodnia

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Warszawa Centralna (1011 dests) | Warszawa Wschodnia (982 dests) | 136 / 139 | 4.19 km | FINE |
| Warszawa Centralna (1011 dests) | Warszawa Zachodnia (1011 dests) | 138 / 136 | 2.77 km | FINE |
| Warszawa Wschodnia (982 dests) | Warszawa Zachodnia (1011 dests) | 137 / 135 | 6.89 km | FINE |

### Basel (Verdict: FINE)
**Cluster members:** Basel Bad Bf, Basel SBB

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Basel Bad Bf (1029 dests) | Basel SBB (1048 dests) | 58 / 55 | 2.60 km | FINE |

### Toru (Verdict: FINE)
**Cluster members:** Toruń Główny, Toruń Miasto, Toruń Wschodni

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Toruń Główny (659 dests) | Toruń Miasto (636 dests) | 7 / 7 | 1.40 km | FINE |
| Toruń Główny (659 dests) | Toruń Wschodni (636 dests) | 8 / 8 | 3.13 km | FINE |
| Toruń Miasto (636 dests) | Toruń Wschodni (636 dests) | 7 / 7 | 1.78 km | FINE |

### Praha (Verdict: FINE)
**Cluster members:** Praha hl.n., Praha-Holesovice, Praha-Libeň

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Praha hl.n. (690 dests) | Praha-Holesovice (464 dests) | 8 / 8 | 3.03 km | FINE |
| Praha hl.n. (690 dests) | Praha-Libeň (690 dests) | 10 / 11 | 5.13 km | FINE |
| Praha-Holesovice (464 dests) | Praha-Libeň (690 dests) | 0 / 0 | 4.57 km | FINE (connected via hub) |

### Zamo (Verdict: FINE)
**Cluster members:** Zamość Starówka, Zamość Wschód, Zamość

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Zamość Starówka (558 dests) | Zamość Wschód (558 dests) | 3 / 3 | 1.12 km | FINE |
| Zamość Starówka (558 dests) | Zamość (558 dests) | 3 / 3 | 1.70 km | FINE |
| Zamość Wschód (558 dests) | Zamość (558 dests) | 3 / 3 | 2.77 km | FINE |

### Frankfurt (Verdict: FINE)
**Cluster members:** Frankfurt(Oder), Frankfurt(Oder)(Gr)

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Frankfurt(Oder) (897 dests) | Frankfurt(Oder)(Gr) (635 dests) | 12 / 12 | 2.63 km | FINE |

### Przemysl (Verdict: FINE)
**Cluster members:** Przemysl Glowny, Przemysl Zasanie

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Przemysl Glowny (742 dests) | Przemysl Zasanie (740 dests) | 22 / 22 | 1.12 km | FINE |

### Dresden (Verdict: FINE)
**Cluster members:** Dresden-Neustadt, Dresden Hbf

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Dresden-Neustadt (729 dests) | Dresden Hbf (729 dests) | 21 / 21 | 2.89 km | FINE |

### Bydgoszcz (Verdict: FINE)
**Cluster members:** Bydgoszcz Glowna, Bydgoszcz Leśna

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Bydgoszcz Glowna (828 dests) | Bydgoszcz Leśna (629 dests) | 16 / 16 | 2.86 km | FINE |

### Bruxelles (Verdict: FINE)
**Cluster members:** Bruxelles Midi, Bruxelles-Nord

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Bruxelles Midi (792 dests) | Bruxelles-Nord (646 dests) | 7 / 7 | 3.30 km | FINE |

### Rotterdam (Verdict: FINE)
**Cluster members:** Rotterdam Blaak, Rotterdam Alexander, Rotterdam Centraal

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Rotterdam Blaak (461 dests) | Rotterdam Alexander (403 dests) | 0 / 0 | 5.56 km | FINE (connected via hub) |
| Rotterdam Blaak (461 dests) | Rotterdam Centraal (531 dests) | 71 / 70 | 1.39 km | FINE |
| Rotterdam Alexander (403 dests) | Rotterdam Centraal (531 dests) | 67 / 67 | 6.40 km | FINE |

### Wroc (Verdict: FINE)
**Cluster members:** Wrocław Mikołajów, Wrocław Nadodrze

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Wrocław Mikołajów (725 dests) | Wrocław Nadodrze (662 dests) | 8 / 8 | 2.63 km | FINE |

### Den Haag (Verdict: FINE)
**Cluster members:** Den Haag Laan v NOI, Den Haag HS, Den Haag Centraal

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Den Haag Laan v NOI (461 dests) | Den Haag HS (461 dests) | 98 / 98 | 1.74 km | FINE |
| Den Haag Laan v NOI (461 dests) | Den Haag Centraal (461 dests) | 0 / 0 | 1.32 km | FINE (connected via hub) |
| Den Haag HS (461 dests) | Den Haag Centraal (461 dests) | 37 / 37 | 1.23 km | FINE |

### Cz (Verdict: FINE)
**Cluster members:** Częstochowa, Częstochowa Stradom

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Częstochowa (700 dests) | Częstochowa Stradom (654 dests) | 7 / 7 | 1.58 km | FINE |

### Olsztyn (Verdict: FINE)
**Cluster members:** Olsztyn Główny, Olsztyn Zachodni

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Olsztyn Główny (659 dests) | Olsztyn Zachodni (659 dests) | 20 / 20 | 2.06 km | FINE |

### Szklarska (Verdict: FINE)
**Cluster members:** Szklarska Poręba Dolna, Szklarska Poręba Średnia, Szklarska Poręba Górna

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Szklarska Poręba Dolna (438 dests) | Szklarska Poręba Średnia (438 dests) | 2 / 2 | 1.62 km | FINE |
| Szklarska Poręba Dolna (438 dests) | Szklarska Poręba Górna (438 dests) | 2 / 2 | 3.20 km | FINE |
| Szklarska Poręba Średnia (438 dests) | Szklarska Poręba Górna (438 dests) | 2 / 2 | 1.63 km | FINE |

### Bia (Verdict: FINE)
**Cluster members:** Białystok, Białystok Zielone Wzgórza

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Białystok (654 dests) | Białystok Zielone Wzgórza (654 dests) | 25 / 25 | 2.73 km | FINE |

### Stalowa (Verdict: FINE)
**Cluster members:** Stalowa Wola Rozwadów, Stalowa Wola Centrum

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Stalowa Wola Rozwadów (643 dests) | Stalowa Wola Centrum (643 dests) | 9 / 9 | 2.47 km | FINE |

### Lyon (Verdict: FINE)
**Cluster members:** Lyon Perrache, Lyon Part Dieu

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Lyon Perrache (508 dests) | Lyon Part Dieu (760 dests) | 26 / 13 | 2.94 km | FINE |

### Norddeich (Verdict: FINE)
**Cluster members:** Norddeich, Norddeich Mole

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Norddeich (632 dests) | Norddeich Mole (623 dests) | 7 / 6 | 0.34 km | FINE |

### Interlaken (Verdict: FINE)
**Cluster members:** Interlaken Ost, Interlaken West

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Interlaken Ost (603 dests) | Interlaken West (604 dests) | 29 / 29 | 1.60 km | FINE |

### Gorzów (Verdict: FINE)
**Cluster members:** Gorzów Wielkopolski, Gorzów Wielkopolski Wschodni

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Gorzów Wielkopolski (562 dests) | Gorzów Wielkopolski Wschodni (562 dests) | 7 / 7 | 1.47 km | FINE |

### Chelm (Verdict: FINE)
**Cluster members:** Chelm, Chelm Miasto

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Chelm (533 dests) | Chelm Miasto (533 dests) | 6 / 6 | 2.45 km | FINE |

### Emden (Verdict: FINE)
**Cluster members:** Emden Außenhafen, Emden Hbf

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Emden Außenhafen (369 dests) | Emden Hbf (643 dests) | 2 / 2 | 2.89 km | FINE |

### K (Verdict: FINE)
**Cluster members:** Kłodzko Główne, Kłodzko Miasto

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Kłodzko Główne (342 dests) | Kłodzko Miasto (606 dests) | 2 / 2 | 1.72 km | FINE |

### Den (Verdict: FINE)
**Cluster members:** Den Helder, Den Helder Zuid

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Den Helder (461 dests) | Den Helder Zuid (461 dests) | 41 / 39 | 2.67 km | FINE |

### Alkmaar (Verdict: FINE)
**Cluster members:** Alkmaar, Alkmaar Noord

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Alkmaar (461 dests) | Alkmaar Noord (461 dests) | 39 / 41 | 1.69 km | FINE |

### Hoorn (Verdict: FINE)
**Cluster members:** Hoorn Kersenboogerd, Hoorn

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Hoorn Kersenboogerd (461 dests) | Hoorn (461 dests) | 39 / 39 | 2.25 km | FINE |

### Bovenkarspel (Verdict: FINE)
**Cluster members:** Bovenkarspel-Grootebroek, Bovenkarspel Flora

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Bovenkarspel-Grootebroek (461 dests) | Bovenkarspel Flora (461 dests) | 39 / 39 | 1.10 km | FINE |

### Vlissingen (Verdict: FINE)
**Cluster members:** Vlissingen, Vlissingen Souburg

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Vlissingen (461 dests) | Vlissingen Souburg (461 dests) | 37 / 37 | 2.31 km | FINE |

### Spielfeld (Verdict: FINE)
**Cluster members:** Spielfeld-Straß Bahnhof, Spielfeld Tarifpunkt Grenze (Bahn)

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Spielfeld-Straß Bahnhof (459 dests) | Spielfeld Tarifpunkt Grenze (Bahn) (459 dests) | 3 / 3 | 2.15 km | FINE |

### Bern (Verdict: FINE)
**Cluster members:** Bern, Bern Wankdorf

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Bern (639 dests) | Bern Wankdorf (273 dests) | 2 / 1 | 2.91 km | FINE |

### Padborg (Verdict: FINE)
**Cluster members:** Padborg st, Padborg Grænse St.

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Padborg st (456 dests) | Padborg Grænse St. (447 dests) | 14 / 14 | 0.87 km | FINE |

### Muszyna (Verdict: FINE)
**Cluster members:** Muszyna, Muszyna Zdrój

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Muszyna (393 dests) | Muszyna Zdrój (393 dests) | 3 / 3 | 1.35 km | FINE |

### Marseille (Verdict: FINE)
**Cluster members:** Marseille Saint-Charles, Marseille Blancarde

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Marseille Saint-Charles (750 dests) | Marseille Blancarde (7 dests) | 0 / 0 | 2.24 km | FINE (minor station) |

### Purmerend (Verdict: FINE)
**Cluster members:** Purmerend Overwhere, Purmerend, Purmerend Weidevenne

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Purmerend Overwhere (13 dests) | Purmerend (454 dests) | 1 / 0 | 1.23 km | FINE |
| Purmerend Overwhere (13 dests) | Purmerend Weidevenne (11 dests) | 1 / 0 | 2.75 km | FINE |
| Purmerend (454 dests) | Purmerend Weidevenne (11 dests) | 1 / 0 | 1.53 km | FINE |

### Zaandam (Verdict: FINE)
**Cluster members:** Zaandam Kogerveld, Zaandam

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Zaandam Kogerveld (10 dests) | Zaandam (466 dests) | 1 / 0 | 2.07 km | FINE |

### Dordrecht (Verdict: FINE)
**Cluster members:** Dordrecht Zuid, Dordrecht

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Dordrecht Zuid (4 dests) | Dordrecht (461 dests) | 0 / 1 | 1.90 km | FINE |

### Vejle (Verdict: FINE)
**Cluster members:** Vejle St., Vejle Sygehus St.

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Vejle St. (175 dests) | Vejle Sygehus St. (173 dests) | 4 / 4 | 0.90 km | FINE |

### Milano (Verdict: FINE)
**Cluster members:** Milano Centrale, MILANO PORTA GARIBALDI

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Milano Centrale (0 dests) | MILANO PORTA GARIBALDI (199 dests) | N/A / 0 | 1.36 km | FINE (minor station) |

### Aalborg (Verdict: FINE)
**Cluster members:** Aalborg Vestby St., Aalborg St.

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Aalborg Vestby St. (65 dests) | Aalborg St. (66 dests) | 31 / 29 | 1.25 km | FINE |

### Vigo (Verdict: FINE)
**Cluster members:** Vigo-Guixar, Vigo Urzaiz

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Vigo-Guixar (5 dests) | Vigo Urzaiz (116 dests) | 0 / 0 | 0.57 km | FINE (minor station) |

### Dobova (Verdict: FINE)
**Cluster members:** Dobova, Dobova(Gr)

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| Dobova (1 dests) | Dobova(Gr) (96 dests) | 1 / 0 | 2.12 km | FINE |

### København (Verdict: FINE)
**Cluster members:** København H, København Syd St.

| Station A | Station B | Direct/Day (A→B / B→A) | Distance | Pair Verdict |
| :--- | :--- | :---: | :---: | :--- |
| København H (16 dests) | København Syd St. (16 dests) | 34 / 34 | 3.81 km | FINE |
