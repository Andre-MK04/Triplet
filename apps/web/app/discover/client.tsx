"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { Autocomplete } from "../../components/Autocomplete";
import { useAuth } from "../../components/AuthContext";
import { TripRow } from "../../components/TripRow";
import { Button } from "../../components/ui/Button";
import { Chip } from "../../components/ui/Chip";
import { Field, Input, Select, Textarea } from "../../components/ui/Input";
import { EmptyState, Notice } from "../../components/ui/Misc";
import { ApiError, apiPost, apiGet } from "../../lib/api";
import { AIRPORTS_BY_CODE, ORIGIN_AIRPORT_CODES } from "../../lib/airports";
import { formatPrice } from "../../lib/format";
import type {
  AISearchResponse,
  AirportResult,
  FlightPlaceResult,
  ProviderMetadata,
  SavedSearch,
  TravelProfile,
  TripOption,
  TripSearchPayload,
  TripSearchResponse,
  TripStyle,
} from "../../lib/types";

const EXAMPLE_PROMPTS = [
  "Find me an 8-12 day trip from Vienna to Japan this October under €900.",
  "Show me somewhere new outside Europe from Zagreb for 7-10 days under €700.",
  "Find a warm Southeast Asia trip from Venice or Vienna with at most one stop.",
];

const BUDGET_TO_AMOUNT: Record<TravelProfile["budgetComfortZone"], number> = {
  under_100: 100,
  under_200: 200,
  under_400: 400,
  flexible: 400,
};

type AdvancedForm = {
  originAirports: string[];
  destinationAirports: string[];
  destinationCountries: string[];
  destinationRegions: string[];
  destinationContinents: string[];
  excludeEurope: boolean;
  unvisitedOnly: boolean;
  returnOriginAirports: string[];
  startDate: string;
  endDate: string;
  minTripLengthDays: number;
  maxTripLengthDays: number;
  maxBudget: number;
  maxGroundTransferHours: number;
  tripStyle: TripStyle;
  directOnly: boolean;
};

function inputDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

const today = new Date();
const defaultStart = new Date(today);
defaultStart.setDate(defaultStart.getDate() + 14);
const defaultEnd = new Date(today);
defaultEnd.setDate(defaultEnd.getDate() + 90);
const placesEndpoint = (query: string) => `/places/search?q=${query}&limit=12`;
const originsEndpoint = (query: string) => `/airports/search?q=${query}&limit=8&originsOnly=true`;

const defaultForm: AdvancedForm = {
  originAirports: ["VIE", "ZAG", "TRS", "VCE", "BUD", "LJU"],
  destinationAirports: [],
  destinationCountries: [],
  destinationRegions: [],
  destinationContinents: [],
  excludeEurope: false,
  unvisitedOnly: false,
  returnOriginAirports: [],
  startDate: inputDate(defaultStart),
  endDate: inputDate(defaultEnd),
  minTripLengthDays: 4,
  maxTripLengthDays: 8,
  maxBudget: 600,
  maxGroundTransferHours: 4,
  tripStyle: "surprise me",
  directOnly: false,
};

function providerNotice(metadata?: ProviderMetadata | null, tripCount = 0): { text: string; tone: "info" | "warning" } | null {
  if (!metadata) return null;
  const warnings = metadata.providerWarnings ?? [];
  if (metadata.liveProviderAttempted && !metadata.liveProviderSucceeded) {
    return {
      tone: "warning",
      text:
        warnings[0] ??
        "Live fares were unavailable — showing cached/demo fares instead. Prices may be out of date.",
    };
  }
  if (metadata.cachedResultsUsed && !metadata.liveProviderSucceeded) {
    return {
      tone: "info",
      text: "Showing demo/cached fares from the development dataset. Prices are illustrative, not live.",
    };
  }
  if (warnings.length > 0 && tripCount > 0) {
    return { tone: "info", text: warnings[0] };
  }
  return null;
}

function emptyStateMessage(payload: TripSearchPayload | null): string {
  const namedPlace = (payload?.destinationAirports?.length ?? 0) > 0;
  const namedScope =
    (payload?.destinationCountries?.length ?? 0) > 0 ||
    (payload?.destinationRegions?.length ?? 0) > 0 ||
    (payload?.destinationContinents?.length ?? 0) > 0;

  if (namedPlace || namedScope) {
    // We did ask the fare data about this place — there simply wasn't anything
    // for these dates and lengths. Say so instead of implying a Triplet limit.
    return `We checked ${
      namedPlace ? "that destination" : "those countries"
    } directly and found no round trips in your dates and trip length. Long-haul fares are often thin outside a few months — try a wider date window, a longer trip, or a higher budget.`;
  }
  if (payload?.excludeEurope) {
    return "No long-haul fares outside Europe matched these dates and budget. Long-haul rarely fits short windows — try a wider date range and a longer trip.";
  }
  return "Try widening the budget, adding more origin airports, or allowing longer ground transfers.";
}

function limitAwareError(error: unknown): string {
  if (error instanceof ApiError) {
    // 402 details are already specific and actionable (mention trial/Pro).
    if (error.status === 402) return error.message;
    if (error.status === 429) return "You're searching fast! Give it a few seconds and try again.";
    return error.message;
  }
  return error instanceof Error ? error.message : "Something went wrong.";
}

function ScanningRoutes() {
  return (
    <div className="flex flex-col items-center gap-4 border-y border-line px-6 py-16 text-center" role="status">
      <svg viewBox="0 0 200 60" className="h-14 w-56" aria-hidden>
        <path d="M10 45 Q 100 -10 190 40" fill="none" stroke="rgba(232,240,244,0.15)" strokeWidth="2" />
        <path d="M10 45 Q 100 -10 190 40" fill="none" stroke="#7ddfc3" strokeWidth="2" className="route-line" />
        <circle cx="10" cy="45" r="4" fill="#7ddfc3" />
        <circle cx="190" cy="40" r="4" fill="#ff9a78" />
      </svg>
      <p className="font-mono text-[11px] uppercase tracking-label text-mist">
        Scanning fares · pairing outbound and return legs
      </p>
    </div>
  );
}

export function DiscoverClient() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const reducedMotion = useReducedMotion();
  const showWelcome = searchParams.get("welcome") === "1";
  const autoSearchedQuery = useRef<string | null>(null);

  const [mode, setMode] = useState<"ai" | "advanced">("ai");
  const [aiMessage, setAiMessage] = useState(EXAMPLE_PROMPTS[0]);
  const [form, setForm] = useState<AdvancedForm>(defaultForm);
  const [returnOriginRaw, setReturnOriginRaw] = useState("");
  const [destinationQuery, setDestinationQuery] = useState("");
  const [destinationSelections, setDestinationSelections] = useState<FlightPlaceResult[]>([]);
  const [originQuery, setOriginQuery] = useState("");
  // City names for origins picked via search, so chips don't read as bare codes.
  const [originLabels, setOriginLabels] = useState<Record<string, string>>({});

  const [trips, setTrips] = useState<TripOption[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{ text: string; tone: "info" | "warning" } | null>(null);
  const [aiSummary, setAiSummary] = useState("");
  const [aiMissingFields, setAiMissingFields] = useState<string[]>([]);
  const [lastPayload, setLastPayload] = useState<TripSearchPayload | null>(null);

  const [alertOpen, setAlertOpen] = useState(false);
  const [alertName, setAlertName] = useState("");
  const [alertEmail, setAlertEmail] = useState("");
  const [alertFrequency, setAlertFrequency] = useState<"daily" | "weekly">("daily");
  const [alertStatus, setAlertStatus] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [isSavingAlert, setIsSavingAlert] = useState(false);
  const [savedAlert, setSavedAlert] = useState<SavedSearch | null>(null);

  // Landing-page hand-off: /discover?q=… prefills the prompt and searches immediately.
  const incomingQuery = searchParams.get("q");
  useEffect(() => {
    if (!incomingQuery || autoSearchedQuery.current === incomingQuery) return;
    autoSearchedQuery.current = incomingQuery;
    setMode("ai");
    setAiMessage(incomingQuery);
    void performAiSearch(incomingQuery);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once per incoming query
  }, [incomingQuery]);

  // Prefill from the user's travel profile once they're logged in.
  useEffect(() => {
    if (!user) return;
    setAlertEmail(user.email);
    apiGet<TravelProfile>("/me/travel-profile")
      .then((profile) => {
        if (!profile.isComplete) return;
        setForm((current) => ({
          ...current,
          originAirports: profile.originAirports,
          minTripLengthDays: profile.preferredTripLengthMin,
          maxTripLengthDays: profile.preferredTripLengthMax,
          maxBudget: BUDGET_TO_AMOUNT[profile.budgetComfortZone],
          directOnly: profile.comfortRules.includes("direct_only"),
          tripStyle:
            profile.openJawWillingness === "simple_returns_only" ? "one city" : current.tripStyle,
        }));
      })
      .catch(() => undefined);
  }, [user]);

  const payload = useMemo<TripSearchPayload>(
    () => ({
      originAirports: form.originAirports,
      destinationAirports: form.destinationAirports.length > 0 ? form.destinationAirports : null,
      destinationCountries: form.destinationCountries,
      destinationRegions: form.destinationRegions,
      destinationContinents: form.destinationContinents,
      excludeEurope: form.excludeEurope,
      unvisitedOnly: form.unvisitedOnly,
      returnOriginAirports: form.returnOriginAirports.length > 0 ? form.returnOriginAirports : null,
      startDate: form.startDate,
      endDate: form.endDate,
      minTripLengthDays: form.minTripLengthDays,
      maxTripLengthDays: form.maxTripLengthDays,
      maxBudget: form.maxBudget,
      maxGroundTransferHours: form.maxGroundTransferHours,
      tripStyle: form.tripStyle,
      directOnly: form.directOnly,
    }),
    [form],
  );

  function resetResultState() {
    setError("");
    setNotice(null);
    setAiSummary("");
    setAiMissingFields([]);
    setAlertStatus(null);
    setSavedAlert(null);
    setHasSearched(true);
    setIsLoading(true);
  }

  async function runAdvancedSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    resetResultState();
    try {
      const data = await apiPost<TripSearchResponse>("/trips/search", payload);
      setTrips(data.trips);
      setLastPayload(payload);
      setNotice(providerNotice(data.providerMetadata, data.trips.length));
    } catch (searchError) {
      setTrips([]);
      setError(limitAwareError(searchError));
    } finally {
      setIsLoading(false);
    }
  }

  async function performAiSearch(message: string) {
    resetResultState();
    try {
      const data = await apiPost<AISearchResponse>("/ai/search", { message });
      setTrips(data.trips);
      setAiSummary(data.message);
      setAiMissingFields(data.missingFields ?? []);
      setLastPayload(data.parsedRequest);
      setNotice(providerNotice(data.providerMetadata, data.trips.length));
    } catch (searchError) {
      setTrips([]);
      setError(limitAwareError(searchError));
    } finally {
      setIsLoading(false);
    }
  }

  function runAiSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void performAiSearch(aiMessage);
  }

  async function saveAlert(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!lastPayload) {
      setAlertStatus({ tone: "error", text: "Run a search first so we know what to watch." });
      return;
    }
    if (
      lastPayload.destinationCountries?.length ||
      lastPayload.destinationRegions?.length ||
      lastPayload.destinationContinents?.length ||
      lastPayload.excludeEurope ||
      lastPayload.unvisitedOnly
    ) {
      setAlertStatus({
        tone: "error",
        text: "Country and region watches are not available yet. Choose a city or airport, or use an anywhere search.",
      });
      return;
    }
    setIsSavingAlert(true);
    setAlertStatus(null);
    try {
      const body = {
        ...lastPayload,
        email: user?.email ?? alertEmail,
        name:
          alertName ||
          `${lastPayload.originAirports.slice(0, 3).join("/")} under ${formatPrice(lastPayload.maxBudget)}`,
        frequency: alertFrequency,
      };
      const data = await apiPost<SavedSearch>(user ? "/me/saved-searches" : "/alerts", body);
      setSavedAlert(data);
      setAlertStatus({
        tone: "success",
        text: user
          ? "Saved! Triplet is now watching this search — see it on your dashboard."
          : "Alert saved. Check the manage link to edit or unsubscribe anytime.",
      });
    } catch (saveError) {
      setAlertStatus({ tone: "error", text: limitAwareError(saveError) });
    } finally {
      setIsSavingAlert(false);
    }
  }

  function toggleAirport(code: string) {
    setForm((current) => ({
      ...current,
      originAirports: current.originAirports.includes(code)
        ? current.originAirports.filter((airport) => airport !== code)
        : [...current.originAirports, code],
    }));
  }

  function addOrigin(airport: AirportResult) {
    setOriginQuery("");
    setOriginLabels((current) => ({ ...current, [airport.iataCode]: airport.city ?? airport.name }));
    setForm((current) =>
      current.originAirports.includes(airport.iataCode)
        ? current
        : { ...current, originAirports: [...current.originAirports, airport.iataCode] },
    );
  }

  function addDestination(place: FlightPlaceResult) {
    if (destinationSelections.some((selection) => selection.kind === place.kind && selection.code === place.code)) return;
    setDestinationSelections((current) => [...current, place]);
    setDestinationQuery("");
    setForm((current) => {
      if (place.kind === "airport" || place.kind === "city") {
        return { ...current, destinationAirports: [...new Set([...current.destinationAirports, place.code])] };
      }
      if (place.kind === "country") {
        return { ...current, destinationCountries: [...new Set([...current.destinationCountries, place.code])] };
      }
      if (place.kind === "region") {
        return { ...current, destinationRegions: [...new Set([...current.destinationRegions, place.code])] };
      }
      return { ...current, destinationContinents: [...new Set([...current.destinationContinents, place.code])] };
    });
  }

  function removeDestination(place: FlightPlaceResult) {
    setDestinationSelections((current) => current.filter((selection) => selection !== place));
    setForm((current) => ({
      ...current,
      destinationAirports: current.destinationAirports.filter((code) => code !== place.code),
      destinationCountries: current.destinationCountries.filter((code) => code !== place.code),
      destinationRegions: current.destinationRegions.filter((code) => code !== place.code),
      destinationContinents: current.destinationContinents.filter((code) => code !== place.code),
    }));
  }

  function clearDestinations() {
    setDestinationSelections([]);
    setDestinationQuery("");
    setForm((current) => ({
      ...current,
      destinationAirports: [],
      destinationCountries: [],
      destinationRegions: [],
      destinationContinents: [],
      excludeEurope: false,
    }));
  }

  return (
    <AppShell>
      <div className="pb-10">
        <header className="mb-8 max-w-2xl">
          <h1 className="font-display text-3xl font-bold text-cloud sm:text-4xl">Discover trips</h1>
          <p className="mt-2 text-mist">
            Search worldwide from supported European airports. Triplet builds complete trip ideas from real
            observed fares.
          </p>
        </header>

        {showWelcome ? (
          <div className="mb-6">
            <Notice tone="success">
              Travel profile saved — your searches are prefilled with your airports and preferences.
            </Notice>
          </div>
        ) : null}

        {/* Search panel */}
        <section className="border-y border-line py-6">
          <div className="mb-6 flex gap-7 border-b border-line" role="tablist" aria-label="Search mode">
            {(["ai", "advanced"] as const).map((tab) => (
              <button
                key={tab}
                role="tab"
                aria-selected={mode === tab}
                onClick={() => setMode(tab)}
                className={
                  "-mb-px border-b-2 pb-2.5 font-mono text-[11px] font-semibold uppercase tracking-label transition-colors " +
                  (mode === tab ? "border-mint text-mint" : "border-transparent text-mist hover:text-cloud")
                }
              >
                {tab === "ai" ? "Ask for it" : "Advanced"}
              </button>
            ))}
          </div>

          {mode === "ai" ? (
            <form onSubmit={runAiSearch} className="space-y-5">
              <div className="flex items-start gap-3">
                <span aria-hidden className="pt-2.5 font-mono text-lg leading-none text-mint">
                  →
                </span>
                <Textarea
                  value={aiMessage}
                  onChange={(event) => setAiMessage(event.target.value)}
                  rows={2}
                  aria-label="Describe your trip"
                  className="min-h-0 font-mono"
                  placeholder="e.g. Japan from Vienna in October for 8–12 days under €900"
                />
              </div>
              <div className="flex flex-wrap gap-x-6 gap-y-2">
                {EXAMPLE_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => setAiMessage(prompt)}
                    className="font-mono text-xs text-mist/80 transition-colors hover:text-mint"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
              <div className="flex justify-end">
                <Button type="submit" size="lg" disabled={isLoading || aiMessage.trim().length < 8}>
                  {isLoading ? "Searching…" : "Find trips"}
                </Button>
              </div>
            </form>
          ) : (
            <form onSubmit={runAdvancedSearch} className="space-y-5">
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wide text-mist">From airports</p>
                  <span className="text-xs text-mist/70">Any European airport</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {ORIGIN_AIRPORT_CODES.map((code) => (
                    <Chip key={code} selected={form.originAirports.includes(code)} onClick={() => toggleAirport(code)}>
                      {AIRPORTS_BY_CODE[code]?.city ?? code} {code}
                    </Chip>
                  ))}
                  {form.originAirports
                    .filter((code) => !ORIGIN_AIRPORT_CODES.includes(code))
                    .map((code) => (
                      <Chip key={code} selected onClick={() => toggleAirport(code)}>
                        {originLabels[code] ?? code} {code} ✕
                      </Chip>
                    ))}
                </div>
                <div className="mt-3 max-w-md">
                  <Autocomplete<AirportResult>
                    endpoint={originsEndpoint}
                    value={originQuery}
                    placeholder="Add another departure airport"
                    ariaLabel="Add a departure airport"
                    optionKey={(airport) => airport.iataCode}
                    onSelect={addOrigin}
                    renderOption={(airport) => (
                      <span className="flex items-baseline justify-between gap-4">
                        <span className="font-medium text-cloud">
                          {airport.city ?? airport.name} ({airport.iataCode})
                        </span>
                        <span className="font-mono text-[10px] uppercase text-mist">{airport.countryName}</span>
                      </span>
                    )}
                  />
                </div>
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wide text-mist">Worldwide destination</p>
                  {destinationSelections.length > 0 || form.excludeEurope ? (
                    <button
                      type="button"
                      onClick={clearDestinations}
                      className="text-xs text-mist underline hover:text-cloud"
                    >
                      Clear · anywhere
                    </button>
                  ) : (
                    <span className="text-xs text-mist/70">Leave empty for anywhere</span>
                  )}
                </div>
                <div className="max-w-2xl">
                  <Autocomplete<FlightPlaceResult>
                    endpoint={placesEndpoint}
                    value={destinationQuery}
                    placeholder="Search a city, airport, country, region, or continent"
                    ariaLabel="Search worldwide destinations"
                    optionKey={(place) => `${place.kind}-${place.code}`}
                    onSelect={addDestination}
                    renderOption={(place) => (
                      <span className="flex items-baseline justify-between gap-4">
                        <span className="font-medium text-cloud">{place.name}</span>
                        <span className="font-mono text-[10px] uppercase text-mist">{place.subtitle}</span>
                      </span>
                    )}
                  />
                </div>
                {destinationSelections.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {destinationSelections.map((place) => (
                      <Chip key={`${place.kind}-${place.code}`} selected onClick={() => removeDestination(place)}>
                        {place.name} · {place.kind} ×
                      </Chip>
                    ))}
                  </div>
                ) : null}
                <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
                  <label className="flex cursor-pointer items-center gap-2 text-sm text-mist">
                    <input
                      type="checkbox"
                      checked={form.excludeEurope}
                      onChange={(event) => setForm({ ...form, excludeEurope: event.target.checked })}
                      className="h-4 w-4 accent-[#7ddfc3]"
                    />
                    Outside Europe
                  </label>
                  <label className="flex cursor-pointer items-center gap-2 text-sm text-mist">
                    <input
                      type="checkbox"
                      checked={form.unvisitedOnly}
                      onChange={(event) => setForm({ ...form, unvisitedOnly: event.target.checked })}
                      className="h-4 w-4 accent-[#7ddfc3]"
                    />
                    Countries new to me
                  </label>
                </div>
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between">
                  <p className="font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
                    Fly home from (optional, multi-city)
                  </p>
                  <span className="text-xs text-mist/70">
                    e.g. out to Stockholm, home from Helsinki
                  </span>
                </div>
                <Input
                  value={returnOriginRaw}
                  onChange={(event) => {
                    const raw = event.target.value.toUpperCase();
                    setReturnOriginRaw(raw);
                    setForm({
                      ...form,
                      returnOriginAirports: raw
                        .split(",")
                        .map((code) => code.trim())
                        .filter((code) => /^[A-Z]{3}$/.test(code)),
                    });
                  }}
                  placeholder="IATA codes, e.g. HEL"
                  className="max-w-sm font-mono"
                  aria-label="Airports to fly home from (multi-city)"
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Field label="Earliest departure">
                  <Input
                    type="date"
                    value={form.startDate}
                    onChange={(event) => setForm({ ...form, startDate: event.target.value })}
                    required
                  />
                </Field>
                <Field label="Latest departure">
                  <Input
                    type="date"
                    value={form.endDate}
                    onChange={(event) => setForm({ ...form, endDate: event.target.value })}
                    required
                  />
                </Field>
                <Field label={`Trip length: ${form.minTripLengthDays}–${form.maxTripLengthDays} days`}>
                  <div className="space-y-2 pt-1">
                    <input
                      type="range"
                      min={1}
                      max={21}
                      value={form.minTripLengthDays}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          minTripLengthDays: Math.min(Number(event.target.value), form.maxTripLengthDays),
                        })
                      }
                      className="w-full"
                      aria-label="Minimum trip length"
                    />
                    <input
                      type="range"
                      min={1}
                      max={30}
                      value={form.maxTripLengthDays}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          maxTripLengthDays: Math.max(Number(event.target.value), form.minTripLengthDays),
                        })
                      }
                      className="w-full"
                      aria-label="Maximum trip length"
                    />
                  </div>
                </Field>
                <Field label="Max budget (€)">
                  <Input
                    type="number"
                    min={30}
                    max={5000}
                    value={form.maxBudget}
                    onChange={(event) => setForm({ ...form, maxBudget: Number(event.target.value) })}
                    required
                  />
                </Field>
              </div>

              <div className="flex flex-wrap items-end gap-4">
                <Field label="Trip style">
                  <Select
                    value={form.tripStyle}
                    onChange={(event) => setForm({ ...form, tripStyle: event.target.value as TripStyle })}
                    className="w-52"
                  >
                    <option value="one city">One city</option>
                    <option value="two nearby cities">Two nearby cities (open-jaw)</option>
                    <option value="surprise me">Surprise me</option>
                  </Select>
                </Field>
                <Field label="Max ground transfer (hours)">
                  <Input
                    type="number"
                    min={0}
                    max={12}
                    step={0.5}
                    value={form.maxGroundTransferHours}
                    onChange={(event) => setForm({ ...form, maxGroundTransferHours: Number(event.target.value) })}
                    className="w-36"
                  />
                </Field>
                <label className="flex cursor-pointer items-center gap-2 pb-2.5 text-sm text-mist">
                  <input
                    type="checkbox"
                    checked={form.directOnly}
                    onChange={(event) => setForm({ ...form, directOnly: event.target.checked })}
                    className="h-4 w-4 accent-[#7ddfc3]"
                  />
                  Direct flights only
                </label>
                <div className="ml-auto">
                  <Button type="submit" size="lg" disabled={isLoading || form.originAirports.length === 0}>
                    {isLoading ? "Searching…" : "Search trips"}
                  </Button>
                </div>
              </div>
            </form>
          )}
        </section>

        {/* Results */}
        <section className="mt-8 space-y-4" aria-live="polite">
          {isLoading ? <ScanningRoutes /> : null}

          {!isLoading && error ? <Notice tone="error">{error}</Notice> : null}

          {!isLoading && aiSummary ? (
            <div className="border-l-2 border-mint pl-4">
              <p className="font-mono text-[10px] font-semibold uppercase tracking-label text-mint">Triplet</p>
              <p className="mt-1 max-w-3xl text-sm leading-relaxed text-cloud">{aiSummary}</p>
              {aiMissingFields.length > 0 ? (
                <p className="mt-1.5 font-mono text-xs text-gold">
                  Assumed defaults for: {aiMissingFields.join(", ")} — switch to Advanced to adjust.
                </p>
              ) : null}
            </div>
          ) : null}

          {!isLoading && notice ? <Notice tone={notice.tone}>{notice.text}</Notice> : null}

          {!isLoading && hasSearched && trips.length > 0 ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
                <p className="font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
                  Results · {trips.length} trip{trips.length === 1 ? "" : "s"} identified · best first
                </p>
                <Button variant="secondary" size="sm" onClick={() => setAlertOpen((open) => !open)}>
                  {alertOpen ? "Hide alert form" : "Watch this search"}
                </Button>
              </div>

              <AnimatePresence>
                {alertOpen ? (
                  <motion.form
                    initial={reducedMotion ? false : { opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={reducedMotion ? undefined : { opacity: 0, height: 0 }}
                    onSubmit={saveAlert}
                    className="overflow-hidden border border-line bg-ink-raised"
                  >
                    <div className="flex flex-wrap items-end gap-4 p-5">
                      <Field label="Alert name">
                        <Input
                          value={alertName}
                          onChange={(event) => setAlertName(event.target.value)}
                          placeholder="e.g. Summer beach watch"
                          className="w-56"
                        />
                      </Field>
                      {!user ? (
                        <Field label="Email">
                          <Input
                            type="email"
                            required
                            value={alertEmail}
                            onChange={(event) => setAlertEmail(event.target.value)}
                            placeholder="you@example.com"
                            className="w-64"
                          />
                        </Field>
                      ) : null}
                      <Field label="Frequency">
                        <Select
                          value={alertFrequency}
                          onChange={(event) => setAlertFrequency(event.target.value as "daily" | "weekly")}
                          className="w-36"
                        >
                          <option value="daily">Daily</option>
                          <option value="weekly">Weekly</option>
                        </Select>
                      </Field>
                      <Button type="submit" disabled={isSavingAlert}>
                        {isSavingAlert ? "Saving…" : "Save alert"}
                      </Button>
                    </div>
                    {alertStatus ? (
                      <div className="px-5 pb-5">
                        <Notice tone={alertStatus.tone === "success" ? "success" : "error"}>
                          {alertStatus.text}
                          {savedAlert?.manageUrl ? (
                            <>
                              {" "}
                              <a href={savedAlert.manageUrl} className="underline" target="_blank" rel="noopener noreferrer">
                                Manage link
                              </a>
                            </>
                          ) : null}
                        </Notice>
                      </div>
                    ) : null}
                  </motion.form>
                ) : null}
              </AnimatePresence>

              <div>
                {trips.map((trip) => (
                  <TripRow
                    key={trip.id}
                    trip={trip}
                    onSaveAlert={() => {
                      setAlertOpen(true);
                      window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
                    }}
                  />
                ))}
              </div>
              <p className="pt-3 text-center font-mono text-[10px] uppercase tracking-label text-mist/60">
                Prices observed at check time and may change · always confirm with the provider
              </p>
            </>
          ) : null}

          {!isLoading && hasSearched && trips.length === 0 && !error ? (
            <EmptyState icon="🛫" title="No trips matched this search">
              {emptyStateMessage(lastPayload)}
            </EmptyState>
          ) : null}

          {!isLoading && !hasSearched ? (
            <EmptyState title="Where could you go?">
              <span className="block">
                Triplet pairs outbound and return fares into complete trips, including open-jaw two-city
                routes. Try one of these:
              </span>
              <span className="mt-4 flex flex-col items-center gap-2">
                {EXAMPLE_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => {
                      setMode("ai");
                      setAiMessage(prompt);
                      void performAiSearch(prompt);
                    }}
                    className="font-mono text-xs text-mint transition-colors hover:text-cloud"
                  >
                    → {prompt}
                  </button>
                ))}
              </span>
            </EmptyState>
          ) : null}
        </section>
      </div>
    </AppShell>
  );
}
