// Hand-kept in sync with docs/data-sources.md (backlog BA).
export const DATA_SOURCES_URL =
  "https://github.com/zitr0y/one-rail-away/blob/main/docs/data-sources.md";

export const IN_USE: { operator: string; country: string }[] = [
  { operator: "DB", country: "Germany" },
  { operator: "FlixTrain", country: "Germany" },
  { operator: "SNCF", country: "France" },
  { operator: "ÖBB", country: "Austria" },
  { operator: "SBB", country: "Switzerland" },
  { operator: "NS", country: "Netherlands" },
  { operator: "Rejseplanen", country: "Denmark" },
  { operator: "CP", country: "Portugal" },
  { operator: "Trenitalia", country: "Italy" },
  { operator: "Renfe", country: "Spain" },
  { operator: "PKP", country: "Poland" },
];

export const WANTED_COUNTRIES: string[] = [
  "Czechia", "Slovakia", "Hungary", "Slovenia", "Croatia", "Belgium",
  "Luxembourg", "Great Britain", "Ukraine", "Romania", "Lithuania",
];

export const WANTED_OPERATORS: { operator: string; where: string }[] = [
  { operator: "Italo", where: "Italy" },
  { operator: "Ouigo España", where: "Spain" },
  { operator: "iryo", where: "Spain" },
  { operator: "WESTbahn", where: "Austria" },
  { operator: "RegioJet", where: "Czechia/Slovakia" },
  { operator: "Leo Express", where: "Czechia/Slovakia" },
];
