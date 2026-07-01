"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type Flight = {
  id: string;
  origin: string;
  destination: string;
  departureDateTime: string;
  arrivalDateTime: string;
  airline: string;
  price: number;
  currency: string;
};

type GroundTransfer = {
  fromAirport: string;
  toAirport: string;
  fromCity: string;
  toCity: string;
  durationHours: number;
  estimatedCost: number;
  mode: "train/bus" | "train" | "bus" | "car";
};

type TripOption = {
  id: string;
  tripType: "same_city" | "open_jaw";
  outboundFlight: Flight;
  returnFlight: Flight;
  groundTransfer: GroundTransfer | null;
  totalPrice: number;
  tripLengthDays: number;
  nights: number;
  score: number;
  explanation: string;
  warnings: string[];
  tags: string[];
};

type TripSearchPayload = {
  originAirports: string[];
  startDate: string;
  endDate: string;
  minTripLengthDays: number;
  maxTripLengthDays: number;
  maxBudget: number;
  maxGroundTransferHours: number;
  tripStyle: "one city" | "two nearby cities" | "surprise me";
};

type TripSearchResponse = {
  trips: TripOption[];
  providerUsed?: string | null;
  providerWarnings?: string[];
  cachedResultsUsed?: boolean;
  providerMetadata?: {
    providerUsed?: string | null;
    liveProviderAttempted?: boolean;
    liveProviderSucceeded?: boolean;
    cachedResultsUsed?: boolean;
    amadeusRequestsAttempted?: number | null;
    amadeusRequestsLimit?: number | null;
    rawOffersCount?: number | null;
    mappedFlightsCount?: number | null;
    providerWarnings?: string[];
  } | null;
};

type AISearchResponse = {
  message: string;
  parsedRequest: TripSearchPayload | null;
  trips: TripOption[];
  missingFields: string[];
  confidence?: number | null;
  providerMetadata?: TripSearchResponse["providerMetadata"];
  aiMetadata: {
    aiProvider: string;
    model: string;
    toolCallsUsed: number;
    fallbackUsed: boolean;
    warnings: string[];
  };
};

type AuthUser = {
  id: string;
  email: string;
  displayName?: string | null;
  isVerified: boolean;
  createdAt: string;
};

type AuthResponse = {
  user: AuthUser;
  message: string;
};

type SavedSearchResponse = {
  id: string;
  email: string;
  name?: string | null;
  originAirports?: string[];
  startDate?: string;
  endDate?: string;
  maxBudget?: number;
  frequency?: string;
  isActive?: boolean;
  manageUrl?: string | null;
  unsubscribeUrl?: string | null;
};

const defaultForm = {
  originAirports: "VIE, ZAG, TRS, VCE, BUD, LJU",
  startDate: "2026-07-01",
  endDate: "2026-08-31",
  minTripLengthDays: 4,
  maxTripLengthDays: 8,
  maxBudget: 180,
  maxGroundTransferHours: 4,
  tripStyle: "surprise me" as TripSearchPayload["tripStyle"],
};

const airportNames: Record<string, string> = {
  LJU: "Ljubljana",
  ZAG: "Zagreb",
  VIE: "Vienna",
  GRZ: "Graz",
  BUD: "Budapest",
  TRS: "Trieste",
  VCE: "Venice",
  TSF: "Venice Treviso",
  ALC: "Alicante",
  VLC: "Valencia",
  BCN: "Barcelona",
  MAD: "Madrid",
  AGP: "Malaga",
  SVQ: "Seville",
  LIS: "Lisbon",
  OPO: "Porto",
  ATH: "Athens",
  CTA: "Catania",
  PMI: "Palma de Mallorca",
};

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

export default function Home() {
  const [form, setForm] = useState(defaultForm);
  const [aiMessage, setAiMessage] = useState(
    "Find me a cheap 5 to 7 day trip in August from Vienna or Zagreb under €180. I like two-city trips.",
  );
  const [aiResponseMessage, setAiResponseMessage] = useState("");
  const [aiParsedRequest, setAiParsedRequest] = useState<TripSearchPayload | null>(null);
  const [aiMissingFields, setAiMissingFields] = useState<string[]>([]);
  const [aiFallbackNotice, setAiFallbackNotice] = useState("");
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [trips, setTrips] = useState<TripOption[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [hasSearched, setHasSearched] = useState(false);
  const [providerNotice, setProviderNotice] = useState("");
  const [lastSearchPayload, setLastSearchPayload] = useState<TripSearchPayload | null>(null);
  const [alertEmail, setAlertEmail] = useState("");
  const [alertName, setAlertName] = useState("");
  const [alertFrequency, setAlertFrequency] = useState<"daily" | "weekly">("daily");
  const [isSavingAlert, setIsSavingAlert] = useState(false);
  const [alertStatus, setAlertStatus] = useState("");
  const [savedAlert, setSavedAlert] = useState<SavedSearchResponse | null>(null);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "signup" | null>(null);
  const [authForm, setAuthForm] = useState({ email: "", password: "", displayName: "" });
  const [authStatus, setAuthStatus] = useState("");
  const [isAuthSubmitting, setIsAuthSubmitting] = useState(false);

  useEffect(() => {
    fetch(`${apiBaseUrl}/auth/me`, { credentials: "include" })
      .then((response) => (response.ok ? response.json() : null))
      .then((data: AuthResponse | null) => {
        if (data?.user) {
          setAuthUser(data.user);
          setAlertEmail(data.user.email);
        }
      })
      .catch(() => undefined);
  }, []);

  const payload = useMemo<TripSearchPayload>(() => {
    return {
      ...form,
      originAirports: form.originAirports
        .split(",")
        .map((code) => code.trim().toUpperCase())
        .filter(Boolean),
    };
  }, [form]);

  async function searchTrips(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setError("");
    setProviderNotice("");
    setHasSearched(true);

    try {
      const response = await fetch(`${apiBaseUrl}/trips/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || "Trip search failed.");
      }

      const data: TripSearchResponse = await response.json();
      setTrips(data.trips);
      setLastSearchPayload(payload);
      setProviderNotice(buildProviderNotice(data));
    } catch (searchError) {
      setTrips([]);
      setProviderNotice("");
      setError(searchError instanceof Error ? searchError.message : "Trip search failed.");
    } finally {
      setIsLoading(false);
    }
  }

  async function searchWithAi(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsAiLoading(true);
    setError("");
    setProviderNotice("");
    setAiResponseMessage("");
    setAiParsedRequest(null);
    setAiMissingFields([]);
    setAiFallbackNotice("");
    setHasSearched(true);

    try {
      const response = await fetch(`${apiBaseUrl}/ai/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ message: aiMessage }),
      });

      if (!response.ok) {
        const message = await response.text();
        throw new Error(limitAwareError(message || "AI search failed."));
      }

      const data: AISearchResponse = await response.json();
      setTrips(data.trips);
      setAiResponseMessage(sanitizeAiText(data.message));
      setAiParsedRequest(data.parsedRequest);
      setLastSearchPayload(data.parsedRequest);
      setAiMissingFields(data.missingFields ?? []);
      setProviderNotice(buildProviderNotice({ trips: data.trips, providerMetadata: data.providerMetadata }));
      setAiFallbackNotice(data.aiMetadata.fallbackUsed ? "AI unavailable - used rule-based parsing." : "");
    } catch (searchError) {
      setTrips([]);
      setProviderNotice("");
      setError(searchError instanceof Error ? searchError.message : "AI search failed.");
    } finally {
      setIsAiLoading(false);
    }
  }

  async function saveAlert(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!lastSearchPayload) {
      setAlertStatus("Run a trip search before saving an alert.");
      return;
    }

    setIsSavingAlert(true);
    setAlertStatus("");
    setSavedAlert(null);

    try {
      const isAccountSave = Boolean(authUser);
      const response = await fetch(`${apiBaseUrl}${isAccountSave ? "/me/saved-searches" : "/alerts"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          ...lastSearchPayload,
          email: authUser?.email ?? alertEmail,
          name: alertName || suggestedAlertName(lastSearchPayload),
          frequency: alertFrequency,
        }),
      });

      if (!response.ok) {
        const message = await response.text();
        throw new Error(limitAwareError(message || "Alert save failed."));
      }

      const data: SavedSearchResponse = await response.json();
      setSavedAlert(data);
      setAlertStatus(
        authUser
          ? "Saved to your Triplet account."
          : "Alert saved. Local emails are printed in backend logs unless SMTP is configured.",
      );
    } catch (saveError) {
      setAlertStatus(saveError instanceof Error ? saveError.message : "Alert save failed.");
    } finally {
      setIsSavingAlert(false);
    }
  }

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!authMode) {
      return;
    }
    setIsAuthSubmitting(true);
    setAuthStatus("");

    try {
      const response = await fetch(`${apiBaseUrl}/auth/${authMode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          email: authForm.email,
          password: authForm.password,
          displayName: authMode === "signup" ? authForm.displayName || null : undefined,
        }),
      });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || "Authentication failed.");
      }
      const data: AuthResponse = await response.json();
      setAuthUser(data.user);
      setAlertEmail(data.user.email);
      setAuthMode(null);
      setAuthForm({ email: "", password: "", displayName: "" });
    } catch (authError) {
      setAuthStatus(authError instanceof Error ? authError.message : "Authentication failed.");
    } finally {
      setIsAuthSubmitting(false);
    }
  }

  async function logout() {
    await fetch(`${apiBaseUrl}/auth/logout`, {
      method: "POST",
      credentials: "include",
    }).catch(() => undefined);
    setAuthUser(null);
  }

  return (
    <main className="min-h-screen px-5 py-8 sm:px-8 lg:px-12">
      <section className="mx-auto flex max-w-7xl flex-col gap-8">
        <AccountBar user={authUser} onLogin={() => setAuthMode("login")} onSignup={() => setAuthMode("signup")} onLogout={logout} />

        <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-end">
          <div className="py-4">
            <p className="mb-4 text-sm font-semibold uppercase tracking-[0.22em] text-mint">
              TRIPLET
            </p>
            <h1 className="max-w-3xl text-4xl font-semibold leading-tight text-white sm:text-5xl">
              Find cheap trips, not just cheap flights.
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-300">
              Combine nearby airports, one-way deals, and smart open-jaw routes across Europe.
            </p>

            <form
              onSubmit={searchWithAi}
              className="mt-6 rounded-lg border border-line bg-panel/92 p-5 shadow-deal backdrop-blur"
            >
              <Field label="Natural-language search">
                <textarea
                  value={aiMessage}
                  onChange={(event) => setAiMessage(event.target.value)}
                  rows={4}
                  className="w-full resize-none rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
                  placeholder="Try: Find me a cheap 5 to 7 day trip in August from Vienna or Zagreb under €180. I like two-city trips."
                />
              </Field>
              <button
                type="submit"
                disabled={isAiLoading || !aiMessage.trim()}
                className="mt-4 w-full rounded-md bg-mint px-4 py-3 font-semibold text-ink transition hover:bg-[#93efd6] disabled:cursor-not-allowed disabled:opacity-70"
              >
                {isAiLoading ? "Searching with AI..." : "Search with AI"}
              </button>
            </form>
          </div>

          <form
            onSubmit={searchTrips}
            className="rounded-lg border border-line bg-panel/92 p-5 shadow-deal backdrop-blur"
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Origin airports" className="sm:col-span-2">
                <input
                  value={form.originAirports}
                  onChange={(event) => setForm({ ...form, originAirports: event.target.value })}
                  className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
                />
              </Field>
              <Field label="Start date">
                <input
                  type="date"
                  value={form.startDate}
                  onChange={(event) => setForm({ ...form, startDate: event.target.value })}
                  className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
                />
              </Field>
              <Field label="End date">
                <input
                  type="date"
                  value={form.endDate}
                  onChange={(event) => setForm({ ...form, endDate: event.target.value })}
                  className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
                />
              </Field>
              <Field label="Min nights">
                <input
                  type="number"
                  min="1"
                  value={form.minTripLengthDays}
                  onChange={(event) => setForm({ ...form, minTripLengthDays: Number(event.target.value) })}
                  className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
                />
              </Field>
              <Field label="Max nights">
                <input
                  type="number"
                  min="1"
                  value={form.maxTripLengthDays}
                  onChange={(event) => setForm({ ...form, maxTripLengthDays: Number(event.target.value) })}
                  className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
                />
              </Field>
              <Field label="Max budget">
                <input
                  type="number"
                  min="1"
                  value={form.maxBudget}
                  onChange={(event) => setForm({ ...form, maxBudget: Number(event.target.value) })}
                  className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
                />
              </Field>
              <Field label="Max transfer hours">
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  value={form.maxGroundTransferHours}
                  onChange={(event) => setForm({ ...form, maxGroundTransferHours: Number(event.target.value) })}
                  className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
                />
              </Field>
              <Field label="Trip style" className="sm:col-span-2">
                <select
                  value={form.tripStyle}
                  onChange={(event) =>
                    setForm({ ...form, tripStyle: event.target.value as TripSearchPayload["tripStyle"] })
                  }
                  className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
                >
                  <option>surprise me</option>
                  <option>one city</option>
                  <option>two nearby cities</option>
                </select>
              </Field>
            </div>
            <button
              type="submit"
              disabled={isLoading}
              className="mt-5 w-full rounded-md bg-mint px-4 py-3 font-semibold text-ink transition hover:bg-[#93efd6] disabled:cursor-not-allowed disabled:opacity-70"
            >
              {isLoading ? "Searching routes..." : "Find trips"}
            </button>
          </form>
        </div>

        {error ? (
          <div className="rounded-lg border border-coral/50 bg-coral/10 p-4 text-coral">
            {error}
          </div>
        ) : null}

        {providerNotice ? (
          <div className="rounded-lg border border-mint/35 bg-mint/10 p-4 text-sm text-mint">
            {providerNotice}
          </div>
        ) : null}

        {aiFallbackNotice ? (
          <div className="rounded-lg border border-amber-300/45 bg-amber-300/10 p-4 text-sm text-amber-100">
            {aiFallbackNotice}
          </div>
        ) : null}

        {isAiLoading || aiResponseMessage || aiParsedRequest || aiMissingFields.length ? (
          <div className="max-w-4xl rounded-lg border border-line bg-panel/80 p-5">
            {isAiLoading || aiResponseMessage ? (
              <AiSummary message={aiResponseMessage} isLoading={isAiLoading} />
            ) : null}
            {aiParsedRequest ? <ParsedSummary parsed={aiParsedRequest} /> : null}
            {aiMissingFields.length ? (
              <p className="mt-3 text-sm text-coral">
                Missing: {aiMissingFields.join(", ")}
              </p>
            ) : null}
          </div>
        ) : null}

        {lastSearchPayload && trips.length ? (
          <form onSubmit={saveAlert} className="max-w-4xl rounded-lg border border-line bg-panel/80 p-5">
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-white">Want to be notified when trips like this appear?</h2>
              <p className="mt-1 text-sm text-slate-400">
                Save this search as an alert. Local development prints emails in backend logs.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-[1fr_1fr_auto]">
              <Field label="Email">
                <input
                  type="email"
                  required={!authUser}
                  disabled={Boolean(authUser)}
                  value={authUser?.email ?? alertEmail}
                  onChange={(event) => setAlertEmail(event.target.value)}
                  className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2 disabled:opacity-70"
                />
              </Field>
              <Field label="Alert name">
                <input
                  value={alertName}
                  onChange={(event) => setAlertName(event.target.value)}
                  placeholder={suggestedAlertName(lastSearchPayload)}
                  className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
                />
              </Field>
              <Field label="Frequency">
                <select
                  value={alertFrequency}
                  onChange={(event) => setAlertFrequency(event.target.value as "daily" | "weekly")}
                  className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
                >
                  <option value="daily">daily</option>
                  <option value="weekly">weekly</option>
                </select>
              </Field>
            </div>
            <button
              type="submit"
              disabled={isSavingAlert}
              className="mt-4 rounded-md bg-mint px-4 py-2.5 font-semibold text-ink transition hover:bg-[#93efd6] disabled:cursor-not-allowed disabled:opacity-70"
            >
              {isSavingAlert ? "Saving alert..." : "Save alert"}
            </button>
            {alertStatus ? <p className="mt-3 text-sm text-slate-300">{alertStatus}</p> : null}
            {savedAlert ? (
              <div className="mt-3 flex flex-wrap gap-3 text-sm">
                {authUser ? (
                  <a className="text-mint underline-offset-4 hover:underline" href="/dashboard">
                    Open dashboard
                  </a>
                ) : null}
                {savedAlert.manageUrl ? (
                  <a className="text-mint underline-offset-4 hover:underline" href={savedAlert.manageUrl}>
                    Manage alert
                  </a>
                ) : null}
                {savedAlert.unsubscribeUrl ? (
                  <a className="text-mint underline-offset-4 hover:underline" href={savedAlert.unsubscribeUrl}>
                    Unsubscribe
                  </a>
                ) : null}
              </div>
            ) : null}
          </form>
        ) : null}

        <section>
          <div className="mb-4 flex items-end justify-between gap-4">
            <div>
              <h2 className="text-2xl font-semibold text-white">Trip deals</h2>
              <p className="mt-1 text-sm text-slate-400">
                {trips.length ? `${trips.length} mock routes found` : "Search uses mock flights and ground transfers."}
              </p>
            </div>
          </div>

          {hasSearched && !isLoading && !error && trips.length === 0 ? (
            <div className="rounded-lg border border-line bg-panel/80 p-8 text-center text-slate-300">
              No trips match this search. Try a higher budget, wider date range, or longer transfer limit.
            </div>
          ) : null}

          <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
            {trips.map((trip) => (
              <TripCard key={trip.id} trip={trip} />
            ))}
          </div>
        </section>
      </section>
      {authMode ? (
        <AuthDialog
          mode={authMode}
          form={authForm}
          status={authStatus}
          isSubmitting={isAuthSubmitting}
          onModeChange={setAuthMode}
          onChange={setAuthForm}
          onClose={() => setAuthMode(null)}
          onSubmit={submitAuth}
        />
      ) : null}
    </main>
  );
}

function AccountBar({
  user,
  onLogin,
  onSignup,
  onLogout,
}: {
  user: AuthUser | null;
  onLogin: () => void;
  onSignup: () => void;
  onLogout: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <a className="text-sm font-semibold uppercase tracking-[0.22em] text-mint" href="/">
        TRIPLET
      </a>
      {user ? (
        <div className="flex flex-wrap items-center justify-end gap-3 text-sm">
          <span className="text-slate-300">{user.displayName || user.email}</span>
          <a className="rounded-md border border-line px-3 py-2 text-white hover:border-mint" href="/dashboard">
            Dashboard
          </a>
          <button type="button" onClick={onLogout} className="rounded-md bg-mint px-3 py-2 font-semibold text-ink">
            Log out
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-3 text-sm">
          <button type="button" onClick={onLogin} className="rounded-md border border-line px-3 py-2 text-white hover:border-mint">
            Log in
          </button>
          <button type="button" onClick={onSignup} className="rounded-md bg-mint px-3 py-2 font-semibold text-ink">
            Sign up
          </button>
        </div>
      )}
    </div>
  );
}

function AuthDialog({
  mode,
  form,
  status,
  isSubmitting,
  onModeChange,
  onChange,
  onClose,
  onSubmit,
}: {
  mode: "login" | "signup";
  form: { email: string; password: string; displayName: string };
  status: string;
  isSubmitting: boolean;
  onModeChange: (mode: "login" | "signup") => void;
  onChange: (form: { email: string; password: string; displayName: string }) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/75 px-4">
      <form onSubmit={onSubmit} className="w-full max-w-md rounded-lg border border-line bg-panel p-5 shadow-deal">
        <div className="mb-5 flex items-center justify-between gap-4">
          <h2 className="text-xl font-semibold text-white">{mode === "login" ? "Log in" : "Create account"}</h2>
          <button type="button" onClick={onClose} className="rounded-md border border-line px-3 py-1.5 text-sm text-white">
            Close
          </button>
        </div>
        <div className="grid gap-4">
          {mode === "signup" ? (
            <Field label="Display name">
              <input
                value={form.displayName}
                onChange={(event) => onChange({ ...form, displayName: event.target.value })}
                className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
              />
            </Field>
          ) : null}
          <Field label="Email">
            <input
              type="email"
              required
              value={form.email}
              onChange={(event) => onChange({ ...form, email: event.target.value })}
              className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
            />
          </Field>
          <Field label="Password">
            <input
              type="password"
              required
              minLength={12}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              value={form.password}
              onChange={(event) => onChange({ ...form, password: event.target.value })}
              className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
            />
          </Field>
        </div>
        {status ? <p className="mt-3 text-sm text-coral">{status}</p> : null}
        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-5 w-full rounded-md bg-mint px-4 py-3 font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-70"
        >
          {isSubmitting ? "Working..." : mode === "login" ? "Log in" : "Create account"}
        </button>
        <button
          type="button"
          onClick={() => onModeChange(mode === "login" ? "signup" : "login")}
          className="mt-3 w-full text-sm text-mint underline-offset-4 hover:underline"
        >
          {mode === "login" ? "Need an account?" : "Already have an account?"}
        </button>
        <div className="my-4 flex items-center gap-3 text-xs uppercase tracking-[0.16em] text-slate-500">
          <span className="h-px flex-1 bg-line" />
          or
          <span className="h-px flex-1 bg-line" />
        </div>
        <div className="grid gap-3">
          <a
            className="block rounded-md border border-line px-4 py-3 text-center font-semibold text-white hover:border-mint"
            href={`${apiBaseUrl}/auth/oauth/google/start`}
          >
            Continue with Google
          </a>
          <a
            className="block rounded-md border border-line px-4 py-3 text-center font-semibold text-white hover:border-mint"
            href={`${apiBaseUrl}/auth/oauth/apple/start`}
          >
            Continue with Apple
          </a>
        </div>
        <a className="mt-3 block text-center text-sm text-slate-400 underline-offset-4 hover:underline" href="/reset-password">
          Reset password
        </a>
      </form>
    </div>
  );
}

function AiSummary({ message, isLoading }: { message: string; isLoading: boolean }) {
  const [visibleText, setVisibleText] = useState("");
  const cleanMessage = useMemo(() => sanitizeAiText(message), [message]);

  useEffect(() => {
    if (isLoading) {
      setVisibleText("Thinking");
      return;
    }

    if (!cleanMessage) {
      setVisibleText("");
      return;
    }

    setVisibleText("");
    let index = 0;
    let timeoutId: number;

    function tick() {
      const nextIndex = Math.min(index + typewriterStep(index, cleanMessage), cleanMessage.length);
      index = nextIndex;
      setVisibleText(cleanMessage.slice(0, index));

      if (index < cleanMessage.length) {
        timeoutId = window.setTimeout(tick, typewriterDelay(index, cleanMessage));
      }
    }

    timeoutId = window.setTimeout(tick, 8);

    return () => window.clearTimeout(timeoutId);
  }, [cleanMessage, isLoading]);

  return (
    <div className="flex max-w-3xl items-start gap-3 text-sm leading-6 text-slate-200">
      <span
        className={`mt-2 h-2.5 w-2.5 shrink-0 rounded-full bg-mint shadow-[0_0_16px_rgba(125,223,195,0.75)] ${
          isLoading || visibleText.length < cleanMessage.length ? "animate-ai-bounce" : ""
        }`}
        aria-hidden="true"
      />
      <p className="min-h-6 whitespace-pre-wrap">
        {visibleText}
        {isLoading ? <span className="inline-flex w-5 animate-pulse">...</span> : null}
      </p>
    </div>
  );
}

function sanitizeAiText(value: string) {
  return value
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/^\s{0,3}#{1,6}\s*/gm, "")
    .replace(/#{1,6}\s*/g, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/__(.*?)__/g, "$1")
    .replace(/\[(.*?)\]\([^)]*\)/g, "$1")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/(?:^|\s)\d+[.)]\s+/g, " ")
    .replace(/[|*_`#]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 400);
}

function limitAwareError(message: string) {
  if (message.includes("reached") || message.includes("Upgrade") || message.includes("plan allows")) {
    return `${message} Visit /pricing to upgrade.`;
  }
  return message;
}

function typewriterStep(index: number, text: string) {
  const progress = text.length ? index / text.length : 1;
  const wave = Math.sin(progress * Math.PI * 4);
  if (wave > 0.45) {
    return 3;
  }
  if (wave < -0.45) {
    return 1;
  }
  return 2;
}

function typewriterDelay(index: number, text: string) {
  const char = text[index] ?? "";
  const progress = text.length ? index / text.length : 1;
  const waveDelay = 34 + Math.sin(progress * Math.PI * 5) * 22;
  if (/[.!?]/.test(char)) {
    return waveDelay + 120;
  }
  if (/[,;:]/.test(char)) {
    return waveDelay + 55;
  }
  return Math.max(10, waveDelay);
}

function ParsedSummary({ parsed }: { parsed: TripSearchPayload }) {
  return (
    <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
      <SummaryItem label="Origins" value={parsed.originAirports.join(", ")} />
      <SummaryItem label="Dates" value={`${parsed.startDate} to ${parsed.endDate}`} />
      <SummaryItem label="Trip length" value={`${parsed.minTripLengthDays}-${parsed.maxTripLengthDays} days`} />
      <SummaryItem label="Budget" value={`€${Math.round(parsed.maxBudget)}`} />
      <SummaryItem label="Trip style" value={parsed.tripStyle} />
      <SummaryItem label="Transfer" value={`${parsed.maxGroundTransferHours}h max`} />
    </dl>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-ink/55 p-3">
      <dt className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</dt>
      <dd className="mt-1 font-medium text-white">{value}</dd>
    </div>
  );
}

function suggestedAlertName(payload: TripSearchPayload) {
  return `${payload.startDate.slice(5)}-${payload.endDate.slice(5)} trips under €${Math.round(payload.maxBudget)}`;
}

function Field({
  label,
  className = "",
  children,
}: {
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1.5 block text-sm font-medium text-slate-300">{label}</span>
      {children}
    </label>
  );
}

function TripCard({ trip }: { trip: TripOption }) {
  const tags = trip.tags ?? [];
  const warnings = trip.warnings ?? [];
  const nights = trip.nights ?? trip.tripLengthDays;

  return (
    <article className="rounded-lg border border-line bg-panel/90 p-5 shadow-deal">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-mint">
            {trip.tripType === "open_jaw" ? "Open jaw" : "One city"}
          </p>
          <h3 className="mt-2 text-xl font-semibold text-white">
            {cityLabel(trip.outboundFlight.destination)}
            {trip.groundTransfer ? ` + ${trip.groundTransfer.toCity}` : ""}
          </h3>
        </div>
        <div className="text-right">
          <p className="text-3xl font-semibold text-white">€{Math.round(trip.totalPrice)}</p>
          <p className="text-sm text-slate-400">{nights} nights</p>
        </div>
      </div>

      {tags.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {tags.map((tag) => (
            <span
              key={tag}
              className="rounded-md border border-mint/35 bg-mint/10 px-2.5 py-1 text-xs font-medium text-mint"
            >
              {tag}
            </span>
          ))}
        </div>
      ) : null}

      <div className="mt-5 space-y-3">
        <RouteLine label="Outbound" flight={trip.outboundFlight} />
        {trip.groundTransfer ? <TransferLine transfer={trip.groundTransfer} /> : null}
        <RouteLine label="Return" flight={trip.returnFlight} />
      </div>

      <div className="mt-5 flex items-center justify-between rounded-md border border-line bg-ink/70 px-3 py-2">
        <span className="text-sm text-slate-300">Trip score</span>
        <span className="font-semibold text-mint">{trip.score}/100</span>
      </div>

      <p className="mt-4 text-sm leading-6 text-slate-300">{trip.explanation}</p>

      <div className="mt-4 flex flex-wrap gap-2">
        {warnings.map((warning) => (
          <span
            key={warning}
            className="rounded-md border border-coral/35 bg-coral/10 px-2.5 py-1 text-xs text-[#ffc4b2]"
          >
            {warning}
          </span>
        ))}
      </div>
    </article>
  );
}

function RouteLine({ label, flight }: { label: string; flight: Flight }) {
  return (
    <div className="rounded-md border border-line bg-ink/55 p-3">
      <div className="mb-2 flex items-center justify-between gap-3 text-sm">
        <span className="font-medium text-white">{label}</span>
        <span className="text-slate-400">{flight.airline}</span>
      </div>
      <div className="flex items-center justify-between gap-3">
        <p className="font-semibold text-white">
          {flight.origin} &rarr; {flight.destination}
        </p>
        <p className="font-semibold text-mint">€{Math.round(flight.price)}</p>
      </div>
      <p className="mt-1 text-sm text-slate-400">
        {formatDateTime(flight.departureDateTime)} &rarr; {formatTime(flight.arrivalDateTime)}
      </p>
    </div>
  );
}

function TransferLine({ transfer }: { transfer: GroundTransfer }) {
  return (
    <div className="rounded-md border border-dashed border-mint/45 bg-mint/10 p-3">
      <div className="flex items-center justify-between gap-3">
        <p className="font-semibold text-white">
          {transfer.fromCity} &rarr; {transfer.toCity}
        </p>
        <p className="font-semibold text-mint">€{Math.round(transfer.estimatedCost)}</p>
      </div>
      <p className="mt-1 text-sm text-slate-300">
        {transfer.durationHours}h by {transfer.mode}
      </p>
    </div>
  );
}

function cityLabel(code: string) {
  return airportNames[code] ?? code;
}

function buildProviderNotice(data: TripSearchResponse) {
  const metadata = data.providerMetadata;
  const warnings = metadata?.providerWarnings ?? data.providerWarnings;
  if (warnings?.length) {
    return warnings.join(" ");
  }
  const providerUsed = metadata?.providerUsed ?? data.providerUsed;
  if (providerUsed === "amadeus") {
    const attempted = metadata?.amadeusRequestsAttempted;
    const limit = metadata?.amadeusRequestsLimit;
    return attempted && limit
      ? `Using Amadeus live fares. Live provider searched ${attempted}/${limit} allowed requests.`
      : "Using Amadeus live fares.";
  }
  if (metadata?.cachedResultsUsed ?? data.cachedResultsUsed) {
    return "Using cached fares because live provider data was unavailable.";
  }
  if (providerUsed === "database") {
    return "Using database demo fares.";
  }
  if (providerUsed === "hybrid") {
    return "Using database fares with live provider checks.";
  }
  return "";
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
