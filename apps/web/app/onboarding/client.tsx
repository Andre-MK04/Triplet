"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { Autocomplete } from "../../components/Autocomplete";
import { useAuth } from "../../components/AuthContext";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Chip } from "../../components/ui/Chip";
import { Input } from "../../components/ui/Input";
import { Notice, Spinner } from "../../components/ui/Misc";
import { apiGet, apiPut } from "../../lib/api";
import type { AirportResult, ComfortRule, LocationResult, TravelProfile, TripType } from "../../lib/types";

const TRIP_TYPES: Array<{ value: TripType; label: string }> = [
  { value: "weekend_city_break", label: "Weekend city breaks" },
  { value: "beach", label: "Beach" },
  { value: "food", label: "Food" },
  { value: "culture", label: "Culture & design" },
  { value: "nature", label: "Nature & hikes" },
  { value: "nightlife", label: "Nightlife" },
  { value: "cheap_adventure", label: "Cheap random adventures" },
  { value: "long_haul_dream", label: "Long-haul dream trips" },
];

const COMFORT_RULES: Array<{ value: ComfortRule; label: string }> = [
  { value: "direct_only", label: "Direct flights" },
  { value: "max_one_stop", label: "Max 1 stop" },
  { value: "avoid_overnight_layovers", label: "Overnight layovers" },
  { value: "no_departures_before_6am", label: "Flights before 6am" },
  { value: "no_returns_after_midnight", label: "Returns after midnight" },
  { value: "cabin_bag_included", label: "Cabin bag included" },
];

const DISTANCES = [
  { km: 50, label: "≈30 min" },
  { km: 100, label: "≈1 hour" },
  { km: 200, label: "≈2 hours" },
  { km: 300, label: "≈3 hours" },
  { km: 450, label: "4+ hours" },
];

const DEAL_SENSITIVITY = [
  { value: "strict", label: "Only unusually cheap deals" },
  { value: "balanced", label: "Balanced price and comfort" },
  { value: "flexible", label: "I'll pay more for the right trip" },
] as const;

const BUDGET_BANDS = [
  { value: "under_100", label: "Under €100" },
  { value: "under_200", label: "€100–€200" },
  { value: "under_400", label: "€200–€400" },
  { value: "flexible", label: "Flexible" },
] as const;

const SPONTANEITY = [
  { value: "very_spontaneous", label: "I can leave within days" },
  { value: "soon", label: "I can travel next week" },
  { value: "flexible_monthly", label: "I usually need a few weeks" },
  { value: "planner", label: "I need at least a month" },
  { value: "long_term_planner", label: "I plan 2+ months ahead" },
] as const;

const OPEN_JAW = [
  { value: "simple_returns_only", label: "Simple returns only", hint: "Fly out and back from the same city." },
  { value: "nearby_city_open_jaw", label: "Nearby-city open-jaw is okay", hint: "Land in one city, fly home from another nearby." },
  { value: "adventurous_multi_city", label: "Adventurous multi-city", hint: "String cities together when it's cheap." },
] as const;

const NOTIFICATIONS = [
  { value: "instant_email", label: "Email me deals as they appear" },
  { value: "weekly_digest", label: "Weekly digest" },
  { value: "urgent_only", label: "Urgent deals only" },
  { value: "push_later", label: "Push (coming with the app)" },
] as const;

const COMFORT_MODES = ["off", "prefer", "require"] as const;
type ComfortMode = (typeof COMFORT_MODES)[number];

function BoardingPassPreview({ profile }: { profile: TravelProfile }) {
  const rows: Array<[string, string]> = [
    ["Home base", profile.homeLocation || "—"],
    ["Max to airport", profile.maxAirportDistanceKm ? `${profile.maxAirportDistanceKm} KM` : "—"],
    ["Airports", profile.originAirports.length ? profile.originAirports.join(" · ") : "—"],
    ["Styles", profile.preferredTripTypes.length ? `${profile.preferredTripTypes.length} SELECTED` : "—"],
    ["Trip length", `${profile.preferredTripLengthMin}–${profile.preferredTripLengthMax} DAYS`],
    ["Deals", (profile.dealSensitivity ?? "balanced").toUpperCase()],
  ];
  return (
    <aside className="hidden h-fit border border-line bg-ink-raised lg:block" aria-label="Travel profile preview">
      <div className="border-b border-dashed border-line px-5 py-4">
        <p className="font-mono text-[10px] font-semibold uppercase tracking-label text-mint">
          Triplet · Travel profile
        </p>
      </div>
      <dl className="px-5 py-2">
        {rows.map(([label, value]) => (
          <div key={label} className="border-b border-line py-3 last:border-b-0">
            <dt className="font-mono text-[9px] uppercase tracking-label text-mist/70">{label}</dt>
            <dd className="mono-num mt-1 font-mono text-xs uppercase text-cloud">{value}</dd>
          </div>
        ))}
      </dl>
      <div className="border-t border-dashed border-line px-5 py-3">
        <p className="font-mono text-[9px] uppercase tracking-label text-mist/50">Powers alerts &amp; every search</p>
      </div>
    </aside>
  );
}

export function OnboardingClient() {
  const router = useRouter();
  const { user, isLoading } = useAuth();
  const reducedMotion = useReducedMotion();
  const [step, setStep] = useState(0);
  const [direction, setDirection] = useState(1);
  const [profile, setProfile] = useState<TravelProfile | null>(null);
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const [recommended, setRecommended] = useState<AirportResult[]>([]);
  const [recStatus, setRecStatus] = useState<"idle" | "loading" | "empty">("idle");
  const preselectedFor = useRef<number | null>(null);

  useEffect(() => {
    if (!user) return;
    apiGet<TravelProfile>("/me/travel-profile")
      .then(setProfile)
      .catch(() => setError("Could not load your profile. Is the API running?"));
  }, [user]);

  function update<K extends keyof TravelProfile>(key: K, value: TravelProfile[K]) {
    setProfile((current) => (current ? { ...current, [key]: value } : current));
  }

  function toggleInList<T>(list: T[], value: T): T[] {
    return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
  }

  // Fetch recommended airports whenever base coords + distance are known.
  useEffect(() => {
    if (!profile?.baseLatitude || !profile?.baseLongitude) {
      setRecommended([]);
      setRecStatus("idle");
      return;
    }
    const km = profile.maxAirportDistanceKm ?? 200;
    setRecStatus("loading");
    apiGet<AirportResult[]>(
      `/airports/recommended?lat=${profile.baseLatitude}&lon=${profile.baseLongitude}&maxDistanceKm=${km}`,
    )
      .then((data) => {
        setRecommended(data);
        setRecStatus(data.length ? "idle" : "empty");
        // Preselect the nearest three once per base location (don't clobber edits).
        if (profile.baseLocationId && preselectedFor.current !== profile.baseLocationId && data.length) {
          preselectedFor.current = profile.baseLocationId;
          const recommendedCodes = data.slice(0, 12).map((a) => a.iataCode);
          setProfile((cur) =>
            cur
              ? {
                  ...cur,
                  recommendedOriginAirports: recommendedCodes,
                  originAirports: cur.originAirports.length === 0 ? recommendedCodes.slice(0, 3) : cur.originAirports,
                }
              : cur,
          );
        }
      })
      .catch(() => setRecStatus("empty"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile?.baseLatitude, profile?.baseLongitude, profile?.maxAirportDistanceKm]);

  function comfortMode(rule: ComfortRule): ComfortMode {
    return (profile?.comfortRuleModes?.[rule] as ComfortMode) ?? "off";
  }

  function setComfortMode(rule: ComfortRule, mode: ComfortMode) {
    if (!profile) return;
    const modes = { ...(profile.comfortRuleModes ?? {}) };
    if (mode === "off") delete modes[rule];
    else modes[rule] = mode;
    // Keep the legacy list in sync (anything not "off") for existing scoring.
    const list = Object.keys(modes) as ComfortRule[];
    setProfile({ ...profile, comfortRuleModes: modes, comfortRules: list });
  }

  async function finish() {
    if (!profile) return;
    setIsSaving(true);
    setError("");
    try {
      const { userId, isComplete, createdAt, updatedAt, ...payload } = profile;
      await apiPut<TravelProfile>("/me/travel-profile", payload);
      router.push("/discover?welcome=1");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Could not save your profile.");
      setIsSaving(false);
    }
  }

  if (isLoading) {
    return (
      <AppShell>
        <div className="flex justify-center py-24"><Spinner label="Loading…" /></div>
      </AppShell>
    );
  }

  if (!user) {
    return (
      <AppShell>
        <div className="mx-auto max-w-md py-24 text-center">
          <h1 className="font-display text-2xl font-bold text-cloud">First, create your account</h1>
          <p className="mt-3 text-mist">The travel profile quiz takes about two minutes and powers all your alerts.</p>
          <div className="mt-6 flex justify-center gap-3">
            <ButtonLink href="/signup">Create account</ButtonLink>
            <ButtonLink href="/login" variant="secondary">Log in</ButtonLink>
          </div>
        </div>
      </AppShell>
    );
  }

  if (!profile) {
    return (
      <AppShell>
        <div className="flex flex-col items-center gap-4 py-24">
          <Spinner label="Fetching your profile…" />
          {error ? <Notice tone="error">{error}</Notice> : null}
        </div>
      </AppShell>
    );
  }

  const p = profile;
  const distanceKm = p.maxAirportDistanceKm ?? 200;

  const steps: Array<{ title: string; subtitle?: string; content: React.ReactNode; valid: boolean }> = [
    {
      title: "Where are you based?",
      subtitle: "Type your city or town — this powers airport recommendations and distances.",
      valid: Boolean(p.homeLocation),
      content: (
        <div className="space-y-3">
          <Autocomplete<LocationResult>
            endpoint={(q) => `/locations/search?q=${q}`}
            placeholder="e.g. Ljubljana, Paris, Maribor…"
            ariaLabel="Search for your base city or town"
            value={p.homeLocation ?? ""}
            optionKey={(loc) => String(loc.id)}
            renderOption={(loc) => (
              <span className="flex items-baseline justify-between gap-3">
                <span className="text-cloud">{loc.name}</span>
                <span className="font-mono text-[10px] uppercase tracking-label text-mist/70">
                  {loc.countryName}
                </span>
              </span>
            )}
            onSelect={(loc) => {
              preselectedFor.current = null;
              setProfile({
                ...p,
                homeLocation: `${loc.name}, ${loc.countryName}`,
                baseLocationId: loc.id,
                baseLatitude: loc.latitude,
                baseLongitude: loc.longitude,
                originAirports: [],
              });
            }}
          />
          {p.homeLocation && !p.baseLocationId ? (
            <p className="font-mono text-[10px] uppercase tracking-label text-gold">
              Using “{p.homeLocation}” as a custom location — airport suggestions need a matched city.
            </p>
          ) : p.baseLocationId ? (
            <p className="font-mono text-[10px] uppercase tracking-label text-mint">Base set · {p.homeLocation}</p>
          ) : null}
        </div>
      ),
    },
    {
      title: "How far would you travel to an airport?",
      subtitle: "We'll recommend airports within this range of your base.",
      valid: true,
      content: (
        <div className="space-y-5">
          <div className="flex flex-wrap gap-2">
            {DISTANCES.map((d) => (
              <Chip key={d.km} selected={distanceKm === d.km} onClick={() => update("maxAirportDistanceKm", d.km)}>
                {d.km} km · {d.label}
              </Chip>
            ))}
          </div>
          <div>
            <div className="mb-2 flex justify-between font-mono text-[11px] uppercase tracking-label text-mist">
              <span>Custom</span>
              <span className="text-mint">{distanceKm} km</span>
            </div>
            <input
              type="range"
              min={20}
              max={600}
              step={10}
              value={distanceKm}
              onChange={(event) => update("maxAirportDistanceKm", Number(event.target.value))}
              className="w-full"
              aria-label="Maximum distance to an airport in km"
            />
          </div>
        </div>
      ),
    },
    {
      title: "Recommended origin airports",
      subtitle: "Nearest first, within your range. We preselected a few — add or remove any.",
      valid: p.originAirports.length > 0,
      content: (
        <div className="space-y-3">
          {recStatus === "loading" ? (
            <Spinner label="Finding airports near you…" />
          ) : !p.baseLatitude ? (
            <Notice tone="info">Set a matched base city first, or add airports manually on the next step.</Notice>
          ) : recStatus === "empty" ? (
            <Notice tone="info">No airports within {distanceKm} km — widen the range or add one manually next.</Notice>
          ) : (
            <div className="flex flex-wrap gap-2">
              {recommended.map((a) => (
                <Chip
                  key={a.iataCode}
                  selected={p.originAirports.includes(a.iataCode)}
                  onClick={() => update("originAirports", toggleInList(p.originAirports, a.iataCode))}
                >
                  {a.city || a.name} · {a.iataCode}
                  {a.distanceKm != null ? ` · ${Math.round(a.distanceKm)} km` : ""}
                </Chip>
              ))}
            </div>
          )}
        </div>
      ),
    },
    {
      title: "Add any other airports",
      subtitle: "Search by city, airport name, or IATA code. More airports, more deals.",
      valid: p.originAirports.length > 0,
      content: (
        <div className="space-y-4">
          <Autocomplete<AirportResult>
            endpoint={(q) =>
              p.baseLatitude
                ? `/airports/search?q=${q}&lat=${p.baseLatitude}&lon=${p.baseLongitude}`
                : `/airports/search?q=${q}`
            }
            placeholder="e.g. Vienna, CDG, Zagreb…"
            ariaLabel="Search airports to add"
            optionKey={(a) => a.iataCode}
            renderOption={(a) => (
              <span className="flex items-baseline justify-between gap-3">
                <span className="text-cloud">
                  {a.name} · <span className="font-mono">{a.iataCode}</span>
                </span>
                <span className="font-mono text-[10px] uppercase tracking-label text-mist/70">
                  {a.city || a.countryName}
                  {a.distanceKm != null ? ` · ${Math.round(a.distanceKm)} km` : ""}
                </span>
              </span>
            )}
            onSelect={(a) => {
              if (!p.originAirports.includes(a.iataCode)) {
                update("originAirports", [...p.originAirports, a.iataCode]);
              }
            }}
          />
          <div className="flex flex-wrap gap-2">
            {p.originAirports.map((code) => (
              <Chip key={code} selected onClick={() => update("originAirports", toggleInList(p.originAirports, code))}>
                {code} ✕
              </Chip>
            ))}
            {p.originAirports.length === 0 ? (
              <span className="font-mono text-[11px] uppercase tracking-label text-mist/60">No airports yet</span>
            ) : null}
          </div>
        </div>
      ),
    },
    {
      title: "What kind of trips do you want?",
      subtitle: "Pick as many as you like.",
      valid: true,
      content: (
        <div className="flex flex-wrap gap-2">
          {TRIP_TYPES.map((type) => (
            <Chip
              key={type.value}
              selected={p.preferredTripTypes.includes(type.value)}
              onClick={() => update("preferredTripTypes", toggleInList(p.preferredTripTypes, type.value))}
            >
              {type.label}
            </Chip>
          ))}
        </div>
      ),
    },
    {
      title: "How long is your ideal trip?",
      valid: p.preferredTripLengthMin <= p.preferredTripLengthMax,
      content: (
        <div className="space-y-6">
          {[
            ["At least", "preferredTripLengthMin", 1, 21] as const,
            ["At most", "preferredTripLengthMax", 1, 30] as const,
          ].map(([label, key, min, max]) => (
            <div key={key}>
              <div className="mb-2 flex justify-between font-mono text-[11px] uppercase tracking-label text-mist">
                <span>{label}</span>
                <span className="text-mint">{p[key]} days</span>
              </div>
              <input
                type="range"
                min={min}
                max={max}
                value={p[key]}
                onChange={(event) => {
                  const value = Number(event.target.value);
                  if (key === "preferredTripLengthMin") update(key, Math.min(value, p.preferredTripLengthMax));
                  else update(key, Math.max(value, p.preferredTripLengthMin));
                }}
                className="w-full"
                aria-label={`${label} trip length in days`}
              />
            </div>
          ))}
        </div>
      ),
    },
    {
      title: "How do you feel about price?",
      subtitle: "This shapes ranking and when we alert you — not a hard filter.",
      valid: true,
      content: (
        <div className="space-y-6">
          <div>
            <p className="mb-2 font-mono text-[11px] uppercase tracking-label text-mist">Deal sensitivity</p>
            <div className="flex flex-wrap gap-2">
              {DEAL_SENSITIVITY.map((d) => (
                <Chip key={d.value} selected={(p.dealSensitivity ?? "balanced") === d.value} onClick={() => update("dealSensitivity", d.value)}>
                  {d.label}
                </Chip>
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 font-mono text-[11px] uppercase tracking-label text-mist">Typical flight budget</p>
            <div className="flex flex-wrap gap-2">
              {BUDGET_BANDS.map((b) => (
                <Chip key={b.value} selected={p.budgetComfortZone === b.value} onClick={() => update("budgetComfortZone", b.value)}>
                  {b.label}
                </Chip>
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 font-mono text-[11px] uppercase tracking-label text-mist">
              Absolute max budget <span className="text-mist/60">(optional)</span>
            </p>
            <Input
              type="number"
              min={20}
              placeholder="Leave empty for no hard cap"
              value={p.absoluteMaxBudget ?? ""}
              onChange={(event) =>
                update("absoluteMaxBudget", event.target.value ? Number(event.target.value) : null)
              }
              className="max-w-48"
              aria-label="Absolute maximum budget in euros"
            />
          </div>
        </div>
      ),
    },
    {
      title: "How spontaneous are you?",
      subtitle: "Sets your default search dates when you don't pick specific ones.",
      valid: true,
      content: (
        <div className="flex flex-wrap gap-2">
          {SPONTANEITY.map((option) => (
            <Chip key={option.value} selected={p.spontaneity === option.value} onClick={() => update("spontaneity", option.value)}>
              {option.label}
            </Chip>
          ))}
        </div>
      ),
    },
    {
      title: "Any comfort rules?",
      subtitle: "Require never shows breaking trips; Prefer just lowers their fit score.",
      valid: true,
      content: (
        <div className="space-y-5">
          <div className="space-y-2">
            {COMFORT_RULES.map((rule) => {
              const active = comfortMode(rule.value);
              return (
                <div key={rule.value} className="flex items-center justify-between gap-3 border-b border-line py-2.5">
                  <span className="text-sm text-cloud">{rule.label}</span>
                  <div className="flex gap-1">
                    {COMFORT_MODES.map((mode) => (
                      <button
                        key={mode}
                        type="button"
                        onClick={() => setComfortMode(rule.value, mode)}
                        className={
                          "border px-2.5 py-1 font-mono text-[10px] uppercase tracking-label transition-colors " +
                          (active === mode
                            ? "border-mint bg-mint text-mint-ink"
                            : "border-line bg-transparent text-mist hover:border-mint/40")
                        }
                      >
                        {mode}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="space-y-2">
            <p className="font-mono text-[11px] uppercase tracking-label text-mist">Open-jaw &amp; multi-city</p>
            {OPEN_JAW.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => update("openJawWillingness", option.value)}
                className={
                  "block w-full rounded-none border px-4 py-3 text-left text-sm transition " +
                  (p.openJawWillingness === option.value
                    ? "border-mint bg-mint-soft text-cloud"
                    : "border-line bg-transparent text-mist hover:border-mint/40")
                }
              >
                <span className="font-semibold">{option.label}</span>
                <span className="block text-xs text-mist">{option.hint}</span>
              </button>
            ))}
          </div>
        </div>
      ),
    },
    {
      title: "How should we tell you about deals?",
      valid: true,
      content: (
        <div className="flex flex-wrap gap-2">
          {NOTIFICATIONS.map((option) => (
            <Chip
              key={option.value}
              selected={p.notificationFrequency === option.value}
              onClick={() => update("notificationFrequency", option.value)}
            >
              {option.label}
            </Chip>
          ))}
        </div>
      ),
    },
  ];

  const totalSteps = steps.length;
  const progress = Math.round(((step + 1) / totalSteps) * 100);

  function goTo(next: number) {
    setDirection(next > step ? 1 : -1);
    setStep(Math.max(0, Math.min(totalSteps - 1, next)));
  }

  const current = steps[step];
  const isLast = step === totalSteps - 1;

  return (
    <AppShell>
      <div className="mx-auto grid max-w-4xl gap-10 py-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div>
          <div className="mb-10">
            <div className="mb-3 flex items-center justify-between font-mono text-[10px] uppercase tracking-label text-mist">
              <span>Travel profile</span>
              <span className="mono-num">
                {String(step + 1).padStart(2, "0")} / {String(totalSteps).padStart(2, "0")}
              </span>
            </div>
            <div className="flex gap-1" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
              {Array.from({ length: totalSteps }, (_, index) => (
                <span key={index} className={"h-0.5 flex-1 transition-colors " + (index <= step ? "bg-mint" : "bg-line")} />
              ))}
            </div>
          </div>

          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={step}
              initial={reducedMotion ? false : { opacity: 0, x: direction * 46 }}
              animate={{ opacity: 1, x: 0 }}
              exit={reducedMotion ? undefined : { opacity: 0, x: direction * -46 }}
              transition={{ duration: 0.3, ease: "easeOut" }}
            >
              <h1 className="font-display text-3xl font-bold text-cloud">{current.title}</h1>
              {current.subtitle ? <p className="mt-2 text-sm text-mist">{current.subtitle}</p> : null}
              <div className="mt-8">{current.content}</div>
            </motion.div>
          </AnimatePresence>

          {error ? <div className="mt-4"><Notice tone="error">{error}</Notice></div> : null}

          <div className="mt-10 flex items-center justify-between border-t border-line pt-6">
            <Button variant="ghost" onClick={() => goTo(step - 1)} disabled={step === 0}>
              ← Back
            </Button>
            {isLast ? (
              <Button size="lg" onClick={() => void finish()} disabled={isSaving || !current.valid}>
                {isSaving ? "Saving…" : "Start watching fares"}
              </Button>
            ) : (
              <Button size="lg" onClick={() => goTo(step + 1)} disabled={!current.valid}>
                Continue →
              </Button>
            )}
          </div>
        </div>

        <BoardingPassPreview profile={p} />
      </div>
    </AppShell>
  );
}
