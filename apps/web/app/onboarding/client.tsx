"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { useAuth } from "../../components/AuthContext";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Chip } from "../../components/ui/Chip";
import { Field, Input } from "../../components/ui/Input";
import { Notice, Spinner } from "../../components/ui/Misc";
import { apiGet, apiPut } from "../../lib/api";
import { AIRPORTS_BY_CODE, ORIGIN_AIRPORT_CODES } from "../../lib/airports";
import type { ComfortRule, TravelProfile, TripType } from "../../lib/types";

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
  { value: "direct_only", label: "Direct flights only" },
  { value: "max_one_stop", label: "Max 1 stop" },
  { value: "avoid_overnight_layovers", label: "No overnight layovers" },
  { value: "no_departures_before_6am", label: "No flights before 6am" },
  { value: "no_returns_after_midnight", label: "No returns after midnight" },
  { value: "cabin_bag_included", label: "Cabin bag included preferred" },
];

const TRAVEL_TIMES = [
  { minutes: 30, label: "30 min" },
  { minutes: 60, label: "1 hour" },
  { minutes: 120, label: "2 hours" },
  { minutes: 180, label: "3 hours" },
];

const BUDGETS = [
  { value: "under_100", label: "Under €100" },
  { value: "under_200", label: "Under €200" },
  { value: "under_400", label: "Under €400" },
  { value: "flexible", label: "Flexible" },
] as const;

const SPONTANEITY = [
  { value: "tomorrow", label: "I'd leave tomorrow" },
  { value: "next_week", label: "Next week works" },
  { value: "next_month", label: "Give me a month" },
  { value: "planning_ahead", label: "I plan ahead" },
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

const TOTAL_STEPS = 9;

const BUDGET_LABEL: Record<TravelProfile["budgetComfortZone"], string> = {
  under_100: "UNDER €100",
  under_200: "UNDER €200",
  under_400: "UNDER €400",
  flexible: "FLEXIBLE",
};

/** The pass "prints" as the traveller answers — the quiz assembles a boarding pass. */
function BoardingPassPreview({ profile }: { profile: TravelProfile }) {
  const rows: Array<[string, string]> = [
    ["Home base", profile.homeLocation || "—"],
    ["Airports", profile.originAirports.length ? profile.originAirports.join(" · ") : "—"],
    [
      "Styles",
      profile.preferredTripTypes.length
        ? profile.preferredTripTypes.map((type) => type.replaceAll("_", " ")).join(", ")
        : "—",
    ],
    ["Trip length", `${profile.preferredTripLengthMin}–${profile.preferredTripLengthMax} DAYS`],
    ["Budget", BUDGET_LABEL[profile.budgetComfortZone]],
    ["Rules", profile.comfortRules.length ? `${profile.comfortRules.length} SET` : "—"],
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
        <p className="font-mono text-[9px] uppercase tracking-label text-mist/50">
          Powers alerts &amp; every search
        </p>
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
  const [customAirport, setCustomAirport] = useState("");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!user) return;
    apiGet<TravelProfile>("/me/travel-profile")
      .then(setProfile)
      .catch(() => setError("Could not load your profile. Is the API running?"));
  }, [user]);

  const progress = useMemo(() => Math.round(((step + 1) / TOTAL_STEPS) * 100), [step]);

  function update<K extends keyof TravelProfile>(key: K, value: TravelProfile[K]) {
    setProfile((current) => (current ? { ...current, [key]: value } : current));
  }

  function toggleInList<T>(list: T[], value: T): T[] {
    return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
  }

  function goTo(next: number) {
    setDirection(next > step ? 1 : -1);
    setStep(Math.max(0, Math.min(TOTAL_STEPS - 1, next)));
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

  const steps: Array<{ title: string; subtitle?: string; content: React.ReactNode; valid: boolean }> = [
    {
      title: "Where are you based?",
      subtitle: "City and country is enough — it helps us suggest nearby airports.",
      valid: true,
      content: (
        <Field label="Home base">
          <Input
            value={profile.homeLocation ?? ""}
            onChange={(event) => update("homeLocation", event.target.value)}
            placeholder="e.g. Ljubljana, Slovenia"
            autoFocus
          />
        </Field>
      ),
    },
    {
      title: "Which airports would you fly from?",
      subtitle: "Pick every airport you'd realistically use. More airports, more deals.",
      valid: profile.originAirports.length > 0,
      content: (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {ORIGIN_AIRPORT_CODES.map((code) => {
              const info = AIRPORTS_BY_CODE[code];
              return (
                <Chip
                  key={code}
                  selected={profile.originAirports.includes(code)}
                  onClick={() => update("originAirports", toggleInList(profile.originAirports, code))}
                >
                  {info ? `${info.city} ${code}` : code}
                </Chip>
              );
            })}
            {profile.originAirports
              .filter((code) => !ORIGIN_AIRPORT_CODES.includes(code))
              .map((code) => (
                <Chip key={code} selected onClick={() => update("originAirports", toggleInList(profile.originAirports, code))}>
                  {code} ✕
                </Chip>
              ))}
          </div>
          <div className="flex gap-2">
            <Input
              value={customAirport}
              onChange={(event) => setCustomAirport(event.target.value.toUpperCase())}
              placeholder="Add IATA code, e.g. MUC"
              maxLength={3}
              className="max-w-44"
              aria-label="Add another airport by IATA code"
            />
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                const code = customAirport.trim().toUpperCase();
                if (/^[A-Z]{3}$/.test(code) && !profile.originAirports.includes(code)) {
                  update("originAirports", [...profile.originAirports, code]);
                }
                setCustomAirport("");
              }}
            >
              Add
            </Button>
          </div>
          <p className="text-xs text-mist/70">Free plans watch up to 6 origin airports.</p>
        </div>
      ),
    },
    {
      title: "How far would you travel to catch a flight?",
      valid: true,
      content: (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {TRAVEL_TIMES.map((option) => (
              <Chip
                key={option.minutes}
                selected={profile.maxAirportTravelTimeMinutes === option.minutes}
                onClick={() => update("maxAirportTravelTimeMinutes", option.minutes)}
              >
                {option.label}
              </Chip>
            ))}
          </div>
          <div>
            <div className="mb-2 flex justify-between text-xs text-mist">
              <span>Custom</span>
              <span className="font-semibold text-mint">
                {Math.floor(profile.maxAirportTravelTimeMinutes / 60)}h {profile.maxAirportTravelTimeMinutes % 60 ? `${profile.maxAirportTravelTimeMinutes % 60}m` : ""}
              </span>
            </div>
            <input
              type="range"
              min={30}
              max={360}
              step={15}
              value={profile.maxAirportTravelTimeMinutes}
              onChange={(event) => update("maxAirportTravelTimeMinutes", Number(event.target.value))}
              className="w-full"
              aria-label="Maximum travel time to airport in minutes"
            />
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
              selected={profile.preferredTripTypes.includes(type.value)}
              onClick={() => update("preferredTripTypes", toggleInList(profile.preferredTripTypes, type.value))}
            >
              {type.label}
            </Chip>
          ))}
        </div>
      ),
    },
    {
      title: "How long is your ideal trip?",
      valid: profile.preferredTripLengthMin <= profile.preferredTripLengthMax,
      content: (
        <div className="space-y-6">
          <div>
            <div className="mb-2 flex justify-between text-xs text-mist">
              <span>At least</span>
              <span className="font-semibold text-mint">{profile.preferredTripLengthMin} days</span>
            </div>
            <input
              type="range"
              min={1}
              max={21}
              value={profile.preferredTripLengthMin}
              onChange={(event) =>
                update("preferredTripLengthMin", Math.min(Number(event.target.value), profile.preferredTripLengthMax))
              }
              className="w-full"
              aria-label="Minimum trip length in days"
            />
          </div>
          <div>
            <div className="mb-2 flex justify-between text-xs text-mist">
              <span>At most</span>
              <span className="font-semibold text-mint">{profile.preferredTripLengthMax} days</span>
            </div>
            <input
              type="range"
              min={1}
              max={30}
              value={profile.preferredTripLengthMax}
              onChange={(event) =>
                update("preferredTripLengthMax", Math.max(Number(event.target.value), profile.preferredTripLengthMin))
              }
              className="w-full"
              aria-label="Maximum trip length in days"
            />
          </div>
        </div>
      ),
    },
    {
      title: "What's your budget comfort zone?",
      subtitle: "For the whole trip's flights — we'll still show you outliers.",
      valid: true,
      content: (
        <div className="flex flex-wrap gap-2">
          {BUDGETS.map((budget) => (
            <Chip
              key={budget.value}
              selected={profile.budgetComfortZone === budget.value}
              onClick={() => update("budgetComfortZone", budget.value)}
            >
              {budget.label}
            </Chip>
          ))}
        </div>
      ),
    },
    {
      title: "How spontaneous are you?",
      valid: true,
      content: (
        <div className="flex flex-wrap gap-2">
          {SPONTANEITY.map((option) => (
            <Chip
              key={option.value}
              selected={profile.spontaneity === option.value}
              onClick={() => update("spontaneity", option.value)}
            >
              {option.label}
            </Chip>
          ))}
        </div>
      ),
    },
    {
      title: "Any comfort rules?",
      subtitle: "Trips that break these get flagged or filtered.",
      valid: true,
      content: (
        <div className="space-y-5">
          <div className="flex flex-wrap gap-2">
            {COMFORT_RULES.map((rule) => (
              <Chip
                key={rule.value}
                selected={profile.comfortRules.includes(rule.value)}
                onClick={() => update("comfortRules", toggleInList(profile.comfortRules, rule.value))}
              >
                {rule.label}
              </Chip>
            ))}
          </div>
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-mist">Open-jaw &amp; multi-city</p>
            {OPEN_JAW.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => update("openJawWillingness", option.value)}
                className={
                  "block w-full rounded-none border px-4 py-3 text-left text-sm transition " +
                  (profile.openJawWillingness === option.value
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
              selected={profile.notificationFrequency === option.value}
              onClick={() => update("notificationFrequency", option.value)}
            >
              {option.label}
            </Chip>
          ))}
        </div>
      ),
    },
  ];

  const current = steps[step];
  const isLast = step === TOTAL_STEPS - 1;

  return (
    <AppShell>
      <div className="mx-auto grid max-w-4xl gap-10 py-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div>
          <div className="mb-10">
            <div className="mb-3 flex items-center justify-between font-mono text-[10px] uppercase tracking-label text-mist">
              <span>Travel profile</span>
              <span className="mono-num">{String(step + 1).padStart(2, "0")} / {String(TOTAL_STEPS).padStart(2, "0")}</span>
            </div>
            {/* Segmented progress rule: sharp rectangles, active in mint. */}
            <div className="flex gap-1" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
              {Array.from({ length: TOTAL_STEPS }, (_, index) => (
                <span
                  key={index}
                  className={"h-0.5 flex-1 transition-colors " + (index <= step ? "bg-mint" : "bg-line")}
                />
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

        <BoardingPassPreview profile={profile} />
      </div>
    </AppShell>
  );
}
