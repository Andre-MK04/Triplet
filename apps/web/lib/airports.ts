export type AirportInfo = {
  code: string;
  city: string;
  country: string;
  lat: number;
  lon: number;
};

// Airports seeded in the backend demo data, plus coordinates for the globe/route art.
export const AIRPORTS: AirportInfo[] = [
  { code: "LJU", city: "Ljubljana", country: "Slovenia", lat: 46.22, lon: 14.46 },
  { code: "ZAG", city: "Zagreb", country: "Croatia", lat: 45.74, lon: 16.07 },
  { code: "VIE", city: "Vienna", country: "Austria", lat: 48.11, lon: 16.57 },
  { code: "GRZ", city: "Graz", country: "Austria", lat: 46.99, lon: 15.44 },
  { code: "BUD", city: "Budapest", country: "Hungary", lat: 47.44, lon: 19.26 },
  { code: "TRS", city: "Trieste", country: "Italy", lat: 45.83, lon: 13.47 },
  { code: "VCE", city: "Venice", country: "Italy", lat: 45.51, lon: 12.35 },
  { code: "TSF", city: "Venice Treviso", country: "Italy", lat: 45.65, lon: 12.19 },
  { code: "ALC", city: "Alicante", country: "Spain", lat: 38.28, lon: -0.56 },
  { code: "VLC", city: "Valencia", country: "Spain", lat: 39.49, lon: -0.48 },
  { code: "BCN", city: "Barcelona", country: "Spain", lat: 41.3, lon: 2.08 },
  { code: "MAD", city: "Madrid", country: "Spain", lat: 40.47, lon: -3.56 },
  { code: "AGP", city: "Malaga", country: "Spain", lat: 36.67, lon: -4.5 },
  { code: "SVQ", city: "Seville", country: "Spain", lat: 37.42, lon: -5.9 },
  { code: "LIS", city: "Lisbon", country: "Portugal", lat: 38.77, lon: -9.13 },
  { code: "OPO", city: "Porto", country: "Portugal", lat: 41.24, lon: -8.68 },
  { code: "ATH", city: "Athens", country: "Greece", lat: 37.94, lon: 23.94 },
  { code: "CTA", city: "Catania", country: "Italy", lat: 37.47, lon: 15.07 },
  { code: "PMI", city: "Palma de Mallorca", country: "Spain", lat: 39.55, lon: 2.74 },
  { code: "CPH", city: "Copenhagen", country: "Denmark", lat: 55.62, lon: 12.65 },
  { code: "ARN", city: "Stockholm", country: "Sweden", lat: 59.65, lon: 17.93 },
  { code: "GOT", city: "Gothenburg", country: "Sweden", lat: 57.66, lon: 12.28 },
  { code: "OSL", city: "Oslo", country: "Norway", lat: 60.19, lon: 11.1 },
  { code: "BGO", city: "Bergen", country: "Norway", lat: 60.29, lon: 5.22 },
  { code: "HEL", city: "Helsinki", country: "Finland", lat: 60.32, lon: 24.96 },
  // Wider Europe (display names for provider-discovered destinations).
  { code: "CDG", city: "Paris", country: "France", lat: 49.01, lon: 2.55 },
  { code: "NCE", city: "Nice", country: "France", lat: 43.66, lon: 7.22 },
  { code: "LYS", city: "Lyon", country: "France", lat: 45.73, lon: 5.08 },
  { code: "BER", city: "Berlin", country: "Germany", lat: 52.37, lon: 13.5 },
  { code: "MUC", city: "Munich", country: "Germany", lat: 48.35, lon: 11.79 },
  { code: "FRA", city: "Frankfurt", country: "Germany", lat: 50.03, lon: 8.56 },
  { code: "HAM", city: "Hamburg", country: "Germany", lat: 53.63, lon: 10.0 },
  { code: "CGN", city: "Cologne", country: "Germany", lat: 50.87, lon: 7.14 },
  { code: "AMS", city: "Amsterdam", country: "Netherlands", lat: 52.31, lon: 4.76 },
  { code: "BRU", city: "Brussels", country: "Belgium", lat: 50.9, lon: 4.48 },
  { code: "LON", city: "London", country: "United Kingdom", lat: 51.51, lon: -0.13 },
  { code: "MAN", city: "Manchester", country: "United Kingdom", lat: 53.35, lon: -2.27 },
  { code: "DUB", city: "Dublin", country: "Ireland", lat: 53.42, lon: -6.27 },
  { code: "FCO", city: "Rome", country: "Italy", lat: 41.8, lon: 12.24 },
  { code: "MXP", city: "Milan", country: "Italy", lat: 45.63, lon: 8.72 },
  { code: "NAP", city: "Naples", country: "Italy", lat: 40.89, lon: 14.29 },
  { code: "PRG", city: "Prague", country: "Czechia", lat: 50.1, lon: 14.26 },
  { code: "WAW", city: "Warsaw", country: "Poland", lat: 52.17, lon: 20.97 },
  { code: "KRK", city: "Krakow", country: "Poland", lat: 50.08, lon: 19.8 },
  { code: "OTP", city: "Bucharest", country: "Romania", lat: 44.57, lon: 26.1 },
  { code: "ZRH", city: "Zurich", country: "Switzerland", lat: 47.46, lon: 8.55 },
  { code: "STO", city: "Stockholm", country: "Sweden", lat: 59.33, lon: 18.06 },
  { code: "KEF", city: "Reykjavik", country: "Iceland", lat: 63.99, lon: -22.61 },
  { code: "TLL", city: "Tallinn", country: "Estonia", lat: 59.41, lon: 24.83 },
  { code: "RIX", city: "Riga", country: "Latvia", lat: 56.92, lon: 23.97 },
];

// Quick-select destination scopes; codes are sent to the backend which scopes the
// search. The backend geography knows the full country lists — these cover the
// common picks and the values match its resolution.
export const DESTINATION_REGIONS: Array<{ label: string; codes: string[] }> = [
  { label: "🇪🇸 Spain", codes: ["BCN", "MAD", "VLC", "ALC", "AGP", "SVQ", "PMI", "IBZ", "BIO"] },
  { label: "🇵🇹 Portugal", codes: ["LIS", "OPO", "FAO"] },
  { label: "🇮🇹 Italy", codes: ["FCO", "MXP", "NAP", "VCE", "CTA", "BLQ", "PMO"] },
  { label: "🇫🇷 France", codes: ["CDG", "ORY", "NCE", "LYS", "MRS", "TLS", "BOD"] },
  { label: "🇩🇪 Germany", codes: ["BER", "MUC", "FRA", "DUS", "HAM", "CGN", "STR"] },
  { label: "🇬🇧 UK & Ireland", codes: ["LHR", "LGW", "STN", "LTN", "MAN", "EDI", "DUB"] },
  { label: "🇬🇷 Greece", codes: ["ATH", "SKG", "HER", "JMK", "JTR"] },
  { label: "❄️ Scandinavia", codes: ["CPH", "BLL", "OSL", "BGO", "TRD", "ARN", "STO", "GOT"] },
  { label: "🧭 Nordics", codes: ["CPH", "BLL", "OSL", "BGO", "TRD", "ARN", "STO", "GOT", "HEL", "KEF"] },
  { label: "🏰 Central Europe", codes: ["PRG", "WAW", "KRK", "BUD", "VIE", "BTS"] },
];

export const AIRPORTS_BY_CODE: Record<string, AirportInfo> = Object.fromEntries(
  AIRPORTS.map((airport) => [airport.code, airport]),
);

// Airports users are likely to fly out of in the demo region.
export const ORIGIN_AIRPORT_CODES = ["VIE", "GRZ", "LJU", "ZAG", "TRS", "VCE", "TSF", "BUD"];

export function airportCity(code: string): string {
  return AIRPORTS_BY_CODE[code]?.city ?? code;
}

export function airportLabel(code: string): string {
  const info = AIRPORTS_BY_CODE[code];
  return info ? `${info.city} (${info.code})` : code;
}
