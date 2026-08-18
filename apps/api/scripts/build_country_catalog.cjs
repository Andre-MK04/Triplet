/**
 * Regenerate app/data/country_catalog.json from MIT-licensed ISO sources.
 *
 * Run from apps/api after installing the two temporary build dependencies:
 *   npm install --no-save --prefix /tmp/triplet-country-build \
 *     countries-list@3.4.1 i18n-iso-countries@7.14.0
 *   NODE_PATH=/tmp/triplet-country-build/node_modules node scripts/build_country_catalog.cjs
 *
 * The 195-country travel definition is centralized below: 193 UN members plus
 * Vatican City and Palestine, grouped using Triplet's adjustable seven-
 * continent classification. Antarctica intentionally has no counted states.
 */

const fs = require("node:fs");
const path = require("node:path");
const { countries } = require("countries-list");
const iso = require("i18n-iso-countries");

const countedByContinent = {
  Africa: `DZ AO BJ BW BF BI CV CM CF TD KM CG CD CI DJ EG GQ ER SZ ET GA GM GH GN GW KE LS LR LY MG MW ML MR MU MA MZ NA NE NG RW ST SN SC SL SO ZA SS SD TZ TG TN UG ZM ZW`,
  Antarctica: ``,
  Asia: `AF AM AZ BH BD BT BN KH CN CY GE IN ID IR IQ IL JP JO KZ KW KG LA LB MY MV MN MM NP KP OM PK PS PH QA SA SG KR LK SY TJ TH TL TR TM AE UZ VN YE`,
  Europe: `AL AD AT BY BE BA BG HR CZ DK EE FI FR DE GR VA HU IS IE IT LV LI LT LU MT MD MC ME NL MK NO PL PT RO RU SM RS SK SI ES SE CH UA GB`,
  "North America": `AG BS BB BZ CA CR CU DM DO SV GD GT HT HN JM MX NI PA KN LC VC TT US`,
  "South America": `AR BO BR CL CO EC GY PY PE SR UY VE`,
  Oceania: `AU FJ KI MH FM NR NZ PW PG WS SB TO TV VU`,
};

const aliases = {
  BO: ["Bolivia"],
  BN: ["Brunei"],
  CD: ["Democratic Republic of the Congo", "DR Congo"],
  CI: ["Ivory Coast"],
  CZ: ["Czech Republic"],
  GB: ["Great Britain", "UK"],
  IR: ["Iran"],
  KR: ["South Korea", "Republic of Korea"],
  LA: ["Laos"],
  MD: ["Moldova"],
  MK: ["Macedonia"],
  PS: ["Palestine"],
  RU: ["Russia"],
  SY: ["Syria"],
  TR: ["Turkey"],
  TZ: ["Tanzania"],
  US: ["United States of America", "USA"],
  VA: ["Vatican City"],
  VE: ["Venezuela"],
  VN: ["Vietnam"],
};

const entries = [];
const seen = new Set();
for (const [continent, rawCodes] of Object.entries(countedByContinent)) {
  for (const code of rawCodes.split(/\s+/).filter(Boolean)) {
    if (seen.has(code)) throw new Error(`Duplicate country code: ${code}`);
    seen.add(code);
    const source = countries[code];
    if (!source) throw new Error(`countries-list is missing ${code}`);
    const alpha3 = iso.alpha2ToAlpha3(code);
    const numericCode = iso.alpha2ToNumeric(code);
    if (!alpha3 || !numericCode) throw new Error(`ISO mapping is missing ${code}`);
    entries.push({
      code,
      alpha3,
      numericCode: String(numericCode).padStart(3, "0"),
      name: source.name,
      continent,
      countsTowardWorldTotal: true,
      aliases: aliases[code] || [],
    });
  }
}

if (entries.length !== 195) throw new Error(`Expected 195 counted countries, got ${entries.length}`);
entries.sort((a, b) => a.name.localeCompare(b.name));

const output = {
  definition: "193 UN member states plus Vatican City and Palestine",
  source: "countries-list 3.4.1 and i18n-iso-countries 7.14.0 (MIT)",
  continents: Object.keys(countedByContinent),
  countries: entries,
};

const target = path.join(__dirname, "..", "app", "data", "country_catalog.json");
fs.writeFileSync(target, `${JSON.stringify(output, null, 2)}\n`, "utf8");
console.log(`Wrote ${entries.length} countries to ${target}`);
