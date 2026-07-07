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
];

// Quick-select regions for the destination picker; codes match the backend's region map.
export const DESTINATION_REGIONS: Array<{ label: string; codes: string[] }> = [
  { label: "🌊 Spain", codes: ["BCN", "MAD", "VLC", "ALC", "AGP", "SVQ", "PMI"] },
  { label: "🌅 Portugal", codes: ["LIS", "OPO"] },
  { label: "🏛 Greece", codes: ["ATH"] },
  { label: "🍝 Italy", codes: ["VCE", "TSF", "TRS", "CTA"] },
  { label: "❄️ Scandinavia", codes: ["CPH", "OSL", "BGO", "ARN", "GOT"] },
  { label: "🧭 Nordics", codes: ["CPH", "OSL", "BGO", "ARN", "GOT", "HEL"] },
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
