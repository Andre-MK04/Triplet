"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { useAuth } from "../../components/AuthContext";
import { TripCard } from "../../components/TripCard";
import { Button } from "../../components/ui/Button";
import { Chip } from "../../components/ui/Chip";
import { Field, Input, Select, Textarea } from "../../components/ui/Input";
import { EmptyState, Notice } from "../../components/ui/Misc";
import { ApiError, apiPost, apiGet } from "../../lib/api";
import { AIRPORTS_BY_CODE, DESTINATION_REGIONS, ORIGIN_AIRPORT_CODES } from "../../lib/airports";
import { formatPrice } from "../../lib/format";
import type {
  AISearchResponse,
  ProviderMetadata,
  SavedSearch,
  TravelProfile,
  TripOption,
  TripSearchPayload,
  TripSearchResponse,
  TripStyle,
} from "../../lib/types";

const EXAMPLE_PROMPTS = [
  "Find me a 5-7 day trip in August from Vienna or Zagreb under €180.",
  "Show me warm two-city trips from airports near Slovenia.",
  "Find cheap weekend trips from Venice, Trieste, or Ljubljana.",
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
  startDate: string;
  endDate: string;
  minTripLengthDays: number;
  maxTripLengthDays: number;
  maxBudget: number;
  maxGroundTransferHours: number;
  tripStyle: TripStyle;
  directOnly: boolean;
};

const defaultForm: AdvancedForm = {
  originAirports: ["VIE", "ZAG", "TRS", "VCE", "BUD", "LJU"],
  destinationAirports: [],
  startDate: "2026-07-15",
  endDate: "2026-08-31",
  minTripLengthDays: 4,
  maxTripLengthDays: 8,
  maxBudget: 180,
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

function limitAwareError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 402) return `${error.message} — upgrade to Pro for higher limits.`;
    if (error.status === 429) return "You're searching fast! Give it a few seconds and try again.";
    return error.message;
  }
  return error instanceof Error ? error.message : "Something went wrong.";
}

function ScanningRoutes() {
  return (
    <div className="glass rounded-card flex flex-col items-center gap-4 px-6 py-16 text-center" role="status">
      <svg viewBox="0 0 200 60" className="h-14 w-56" aria-hidden>
        <path d="M10 45 Q 100 -10 190 40" fill="none" stroke="rgba(148,184,210,0.25)" strokeWidth="2" />
        <path d="M10 45 Q 100 -10 190 40" fill="none" stroke="#7ddfc3" strokeWidth="2" className="route-line" />
        <circle cx="10" cy="45" r="4" fill="#7ddfc3" />
        <circle cx="190" cy="40" r="4" fill="#ff9a78" />
        <text x="100" y="52" textAnchor="middle" fill="#93a6b4" fontSize="9">scanning routes…</text>
      </svg>
      <p className="text-sm text-mist">Pairing outbound and return fares from your airports…</p>
    </div>
  );
}

export function DiscoverClient() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const reducedMotion = useReducedMotion();
  const showWelcome = searchParams.get("welcome") === "1";

  const [mode, setMode] = useState<"ai" | "advanced">("ai");
  const [aiMessage, setAiMessage] = useState(EXAMPLE_PROMPTS[0]);
  const [form, setForm] = useState<AdvancedForm>(defaultForm);
  const [customAirport, setCustomAirport] = useState("");

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
    if (!incomingQuery) return;
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

  function toggleDestinationRegion(codes: string[]) {
    setForm((current) => {
      const allSelected = codes.every((code) => current.destinationAirports.includes(code));
      const next = allSelected
        ? current.destinationAirports.filter((code) => !codes.includes(code))
        : [...new Set([...current.destinationAirports, ...codes])];
      return { ...current, destinationAirports: next };
    });
  }

  return (
    <AppShell>
      <div className="pb-10">
        <header className="mb-8 max-w-2xl">
          <h1 className="font-display text-3xl font-bold text-cloud sm:text-4xl">Discover trips</h1>
          <p className="mt-2 text-mist">
            Describe the trip you want, or fine-tune every knob. Triplet builds complete trip ideas from
            real observed fares.
          </p>
        </header>

        {showWelcome ? (
          <div className="mb-6">
            <Notice tone="success">
              🎉 Travel profile saved! Your searches are prefilled with your airports and preferences.
            </Notice>
          </div>
        ) : null}

        {/* Search panel */}
        <section className="glass rounded-card p-5 shadow-deal sm:p-6">
          <div className="mb-5 flex gap-1 rounded-full bg-ink-soft/80 p-1" role="tablist" aria-label="Search mode">
            {(["ai", "advanced"] as const).map((tab) => (
              <button
                key={tab}
                role="tab"
                aria-selected={mode === tab}
                onClick={() => setMode(tab)}
                className={
                  "flex-1 rounded-full px-4 py-2 text-sm font-semibold transition " +
                  (mode === tab ? "bg-mint text-ink" : "text-mist hover:text-cloud")
                }
              >
                {tab === "ai" ? "✨ AI search" : "🎛 Advanced"}
              </button>
            ))}
          </div>

          {mode === "ai" ? (
            <form onSubmit={runAiSearch} className="space-y-4">
              <Textarea
                value={aiMessage}
                onChange={(event) => setAiMessage(event.target.value)}
                rows={3}
                aria-label="Describe your trip"
                placeholder="e.g. Find me a cheap 5–7 day trip in August from Vienna, Venice, or Zagreb. I like food and warm places."
              />
              <div className="flex flex-wrap gap-2">
                {EXAMPLE_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => setAiMessage(prompt)}
                    className="rounded-full border border-line bg-white/5 px-3 py-1.5 text-xs text-mist transition hover:border-mint/40 hover:text-cloud"
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
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-mist">From airports</p>
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
                        {code} ✕
                      </Chip>
                    ))}
                  <span className="inline-flex items-center gap-1">
                    <Input
                      value={customAirport}
                      onChange={(event) => setCustomAirport(event.target.value.toUpperCase())}
                      placeholder="+ IATA"
                      maxLength={3}
                      className="w-24 rounded-full py-2 text-center"
                      aria-label="Add another origin airport"
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          const code = customAirport.trim();
                          if (/^[A-Z]{3}$/.test(code) && !form.originAirports.includes(code)) toggleAirport(code);
                          setCustomAirport("");
                        }
                      }}
                    />
                  </span>
                </div>
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wide text-mist">To (optional)</p>
                  {form.destinationAirports.length > 0 ? (
                    <button
                      type="button"
                      onClick={() => setForm({ ...form, destinationAirports: [] })}
                      className="text-xs text-mist underline hover:text-cloud"
                    >
                      Clear — surprise me
                    </button>
                  ) : (
                    <span className="text-xs text-mist/70">Leave empty for anywhere</span>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {DESTINATION_REGIONS.map((region) => {
                    const active = region.codes.every((code) => form.destinationAirports.includes(code));
                    return (
                      <Chip key={region.label} selected={active} onClick={() => toggleDestinationRegion(region.codes)}>
                        {region.label}
                      </Chip>
                    );
                  })}
                </div>
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
            <div className="glass rounded-card flex gap-3 p-5">
              <span className="animate-ai-bounce text-2xl" aria-hidden>🤖</span>
              <div>
                <p className="text-sm text-cloud">{aiSummary}</p>
                {aiMissingFields.length > 0 ? (
                  <p className="mt-1 text-xs text-gold">
                    Assumed defaults for: {aiMissingFields.join(", ")}. Switch to Advanced to adjust.
                  </p>
                ) : null}
              </div>
            </div>
          ) : null}

          {!isLoading && notice ? <Notice tone={notice.tone}>{notice.text}</Notice> : null}

          {!isLoading && hasSearched && trips.length > 0 ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-mist">
                  {trips.length} trip idea{trips.length === 1 ? "" : "s"}, best first
                </p>
                <Button variant="secondary" size="sm" onClick={() => setAlertOpen((open) => !open)}>
                  🔔 {alertOpen ? "Hide alert form" : "Watch this search"}
                </Button>
              </div>

              <AnimatePresence>
                {alertOpen ? (
                  <motion.form
                    initial={reducedMotion ? false : { opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={reducedMotion ? undefined : { opacity: 0, height: 0 }}
                    onSubmit={saveAlert}
                    className="glass rounded-card overflow-hidden"
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

              <div className="grid gap-5 lg:grid-cols-2">
                {trips.map((trip) => (
                  <TripCard
                    key={trip.id}
                    trip={trip}
                    onSaveAlert={() => {
                      setAlertOpen(true);
                      window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
                    }}
                  />
                ))}
              </div>
              <p className="pt-2 text-center text-xs text-mist/60">
                Prices are observed at check time and may change. Always check the final price with the provider.
              </p>
            </>
          ) : null}

          {!isLoading && hasSearched && trips.length === 0 && !error ? (
            <EmptyState icon="🛫" title="No trips matched this search">
              {lastPayload?.destinationAirports?.length
                ? "We couldn't find fares to that destination in your budget and dates. Try widening the dates or budget, or clear the destination to see anywhere."
                : "Try widening the budget, adding more origin airports, or allowing longer ground transfers."}
            </EmptyState>
          ) : null}

          {!isLoading && !hasSearched ? (
            <EmptyState icon="🗺" title="Where could you go?">
              Run an AI search or fine-tune the advanced filters — Triplet pairs outbound and return fares
              into complete trips, including open-jaw two-city routes.
            </EmptyState>
          ) : null}
        </section>
      </div>
    </AppShell>
  );
}
