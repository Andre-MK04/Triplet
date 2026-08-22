"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { useAuth } from "../../components/AuthContext";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Field, Input, Select, Textarea } from "../../components/ui/Input";
import { Notice, Spinner } from "../../components/ui/Misc";
import { apiDelete, apiGet, apiPatch, apiPost } from "../../lib/api";
import type {
  CountryCatalogEntry,
  CountryCatalogResponse,
  CountryVisit,
  TravelDatePrecision,
  TravelMapCountry,
  TravelMapResponse,
} from "../../lib/types";

const TravelMapGlobe = dynamic(
  () => import("../../components/TravelMapGlobe").then((module) => module.TravelMapGlobe),
  {
    ssr: false,
    loading: () => <div className="min-h-[480px] animate-pulse rounded-full border border-line bg-ink-soft" />,
  },
);

type CountryPatch = { visited?: boolean; lived?: boolean; wishlist?: boolean };
type VisitDraft = {
  id?: string;
  kind: "visit" | "lived";
  startDate: string;
  endDate: string;
  startPrecision: TravelDatePrecision;
  endPrecision: TravelDatePrecision;
  note: string;
};

const EMPTY_VISIT: VisitDraft = {
  kind: "visit",
  startDate: "",
  endDate: "",
  startPrecision: "month",
  endPrecision: "month",
  note: "",
};

const STATUS_LABEL = {
  lived: "Lived here",
  visited: "Visited",
  wishlist: "Wishlist",
  unvisited: "Not mapped yet",
};

function displayPartialDate(value: string | null): string {
  if (!value) return "Date not recorded";
  if (/^\d{4}$/.test(value)) return value;
  if (/^\d{4}-\d{2}$/.test(value)) {
    const [year, month] = value.split("-").map(Number);
    return new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString("en-GB", {
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    });
  }
  return new Date(`${value}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

function visitPeriod(visit: CountryVisit): string {
  const start = displayPartialDate(visit.startDate);
  if (!visit.endDate) return start;
  return `${start} – ${displayPartialDate(visit.endDate)}`;
}

function TravelStats({ map }: { map: TravelMapResponse }) {
  const stats = map.stats;
  return (
    <div className="grid border-y border-line sm:grid-cols-4">
      {[
        ["Countries", `${stats.countriesVisited} / ${stats.worldTotal}`],
        ["World explored", `${stats.worldExploredPercentage}%`],
        ["Continents", `${stats.continentsVisited} / ${stats.continentTotal}`],
        ["Wishlist", String(stats.wishlistCountries)],
      ].map(([label, value], index) => (
        <div key={label} className={(index ? "border-t border-line sm:border-l sm:border-t-0 " : "") + "px-4 py-4"}>
          <p className="font-mono text-[9px] uppercase tracking-label text-mist">{label}</p>
          <p className="mono-num mt-1 font-display text-2xl font-bold text-cloud">{value}</p>
        </div>
      ))}
    </div>
  );
}

function Legend() {
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-2 font-mono text-[9px] uppercase tracking-label text-mist" aria-label="Travel map legend">
      <span className="inline-flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-mint" />Visited</span>
      <span className="inline-flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-coral" />Lived</span>
      <span className="inline-flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-gold" />Wishlist</span>
    </div>
  );
}

function CountryPanel({
  metadata,
  country,
  busy,
  onClose,
  onUpdate,
  onAddVisit,
  onEditVisit,
  onDeleteVisit,
}: {
  metadata: CountryCatalogEntry;
  country?: TravelMapCountry;
  busy: boolean;
  onClose: () => void;
  onUpdate: (patch: CountryPatch) => void;
  onAddVisit: (kind: "visit" | "lived") => void;
  onEditVisit: (visit: CountryVisit) => void;
  onDeleteVisit: (visit: CountryVisit) => void;
}) {
  const status = country?.primaryStatus ?? "unvisited";
  return (
    <aside className="fixed inset-x-0 bottom-0 z-50 max-h-[74vh] overflow-y-auto border-t border-line bg-ink-raised p-5 shadow-2xl lg:static lg:z-auto lg:max-h-[680px] lg:border lg:shadow-none">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[9px] uppercase tracking-label text-mist">{metadata.continent} · {metadata.code}</p>
          <h2 className="mt-1 font-display text-3xl font-bold text-cloud">{metadata.name}</h2>
          <p className="mt-2 font-mono text-[10px] font-semibold uppercase tracking-label text-mint">
            {STATUS_LABEL[status]}
          </p>
        </div>
        <button type="button" onClick={onClose} className="p-2 text-mist hover:text-cloud" aria-label="Close country details">×</button>
      </div>

      {status === "unvisited" ? (
        <div className="mt-6 grid gap-2">
          <Button onClick={() => onUpdate({ visited: true })} disabled={busy}>I&apos;ve been here</Button>
          <Button variant="secondary" onClick={() => onUpdate({ wishlist: true })} disabled={busy}>Add to wishlist</Button>
          <Button variant="secondary" onClick={() => onUpdate({ lived: true })} disabled={busy}>I lived here</Button>
        </div>
      ) : null}

      {country?.wishlist ? (
        <div className="mt-6 space-y-2 border-y border-line py-4">
          <ButtonLink href={`/discover?q=${encodeURIComponent(`Find me a trip to ${metadata.name}`)}`} className="w-full">
            Plan a trip
          </ButtonLink>
          <Button className="w-full" variant="ghost" onClick={() => onUpdate({ wishlist: false })} disabled={busy}>
            Remove from wishlist
          </Button>
        </div>
      ) : null}

      {country?.visited ? (
        <div className="mt-6">
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => onAddVisit("visit")} disabled={busy}>Add another visit</Button>
            <Button size="sm" variant="secondary" onClick={() => onAddVisit("lived")} disabled={busy}>Add lived dates</Button>
          </div>
          <div className="mt-5 border-t border-line">
            {country.visits.length ? country.visits.map((visit) => (
              <article key={visit.id} className="border-b border-line py-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-mono text-[9px] uppercase tracking-label text-mist">
                      {visit.kind === "lived" ? "Lived here" : "Visit"}
                    </p>
                    <p className="mt-1 text-sm font-medium text-cloud">{visitPeriod(visit)}</p>
                    {visit.note ? <p className="mt-1 text-sm leading-relaxed text-mist">{visit.note}</p> : null}
                  </div>
                  <div className="flex gap-3">
                    <button type="button" onClick={() => onEditVisit(visit)} className="font-mono text-[9px] uppercase text-mist hover:text-mint">Edit</button>
                    <button type="button" onClick={() => onDeleteVisit(visit)} className="font-mono text-[9px] uppercase text-coral hover:text-cloud">Delete</button>
                  </div>
                </div>
              </article>
            )) : (
              <p className="py-5 text-sm leading-relaxed text-mist">Marked as visited. Add a month or year whenever you remember it.</p>
            )}
          </div>
          <div className="mt-4 flex flex-wrap gap-4">
            {country.lived ? (
              <button type="button" onClick={() => onUpdate({ lived: false })} className="font-mono text-[9px] uppercase tracking-label text-mist hover:text-coral">
                Clear lived status
              </button>
            ) : (
              <button type="button" onClick={() => onUpdate({ lived: true })} className="font-mono text-[9px] uppercase tracking-label text-mist hover:text-mint">
                Mark as lived
              </button>
            )}
            {!country.visits.length ? (
              <button type="button" onClick={() => onUpdate({ visited: false })} className="font-mono text-[9px] uppercase tracking-label text-mist hover:text-coral">
                Mark unvisited
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
    </aside>
  );
}

function PartialDateField({
  label,
  value,
  precision,
  required = false,
  onChange,
}: {
  label: string;
  value: string;
  precision: TravelDatePrecision;
  required?: boolean;
  onChange: (value: string, precision: TravelDatePrecision) => void;
}) {
  return (
    <div className="space-y-2">
      <p className="font-mono text-[10px] font-semibold uppercase tracking-label text-mist">{label}</p>
      <Select value={precision} onChange={(event) => onChange("", event.target.value as TravelDatePrecision)} aria-label={`${label} precision`}>
        <option value="month">Month + year</option>
        <option value="year">Year only</option>
        <option value="exact">Exact date</option>
        <option value="unknown">I don&apos;t remember</option>
      </Select>
      {precision === "month" ? <Input aria-label={`${label} month and year`} type="month" value={value} onChange={(event) => onChange(event.target.value, precision)} required={required} /> : null}
      {precision === "year" ? <Input aria-label={`${label} year`} type="number" min="1900" max="2100" placeholder="2024" value={value} onChange={(event) => onChange(event.target.value, precision)} required={required} /> : null}
      {precision === "exact" ? <Input aria-label={`${label} exact date`} type="date" value={value} onChange={(event) => onChange(event.target.value, precision)} required={required} /> : null}
    </div>
  );
}

function VisitEditor({
  countryName,
  draft,
  saving,
  onChange,
  onClose,
  onSave,
}: {
  countryName: string;
  draft: VisitDraft;
  saving: boolean;
  onChange: (draft: VisitDraft) => void;
  onClose: () => void;
  onSave: () => void;
}) {
  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center bg-ink/70 p-0 backdrop-blur-sm sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-labelledby="visit-editor-title">
      <form
        className="max-h-[90vh] w-full max-w-xl overflow-y-auto border border-line bg-ink-raised p-5 shadow-2xl sm:p-7"
        onSubmit={(event) => { event.preventDefault(); onSave(); }}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono text-[9px] uppercase tracking-label text-mint">Travel memory</p>
            <h2 id="visit-editor-title" className="mt-1 font-display text-2xl font-bold text-cloud">{draft.id ? "Edit" : "Add"} · {countryName}</h2>
          </div>
          <button type="button" onClick={onClose} className="p-2 text-mist hover:text-cloud" aria-label="Close visit editor">×</button>
        </div>
        <div className="mt-6 space-y-5">
          <Field label="What kind of stay?">
            <Select value={draft.kind} onChange={(event) => onChange({ ...draft, kind: event.target.value as "visit" | "lived" })}>
              <option value="visit">Visited</option>
              <option value="lived">Lived here</option>
            </Select>
          </Field>
          <div className="grid gap-5 sm:grid-cols-2">
            <PartialDateField label="Started" value={draft.startDate} precision={draft.startPrecision} required onChange={(value, precision) => onChange({ ...draft, startDate: value, startPrecision: precision })} />
            <PartialDateField label="Ended (optional)" value={draft.endDate} precision={draft.endPrecision} onChange={(value, precision) => onChange({ ...draft, endDate: value, endPrecision: precision })} />
          </div>
          <Field label="Note (optional)" hint="Keep it short. This remains private to your account.">
            <Textarea value={draft.note} maxLength={1000} onChange={(event) => onChange({ ...draft, note: event.target.value })} placeholder="A food weekend in Bologna…" />
          </Field>
        </div>
        <div className="mt-7 flex justify-end gap-3">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={saving}>{saving ? "Saving…" : "Save memory"}</Button>
        </div>
      </form>
    </div>
  );
}

function AddCountries({
  catalog,
  countries,
  saving,
  onClose,
  onOpenCountry,
  onSave,
}: {
  catalog: CountryCatalogEntry[];
  countries: TravelMapCountry[];
  saving: boolean;
  onClose: () => void;
  onOpenCountry: (code: string) => void;
  onSave: (codes: string[], status: "visited" | "lived" | "wishlist") => void;
}) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [status, setStatus] = useState<"visited" | "lived" | "wishlist">("visited");
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return catalog.filter((country) => !needle || country.name.toLowerCase().includes(needle) || country.code.toLowerCase().includes(needle)).slice(0, 60);
  }, [catalog, query]);
  const statusByCode = useMemo(
    () => new Map(countries.map((country) => [country.code, country.primaryStatus])),
    [countries],
  );

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center bg-ink/70 backdrop-blur-sm sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-labelledby="add-countries-title">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col border border-line bg-ink-raised shadow-2xl">
        <div className="flex items-start justify-between border-b border-line p-5 sm:p-6">
          <div><p className="font-mono text-[9px] uppercase tracking-label text-mint">Quick add</p><h2 id="add-countries-title" className="mt-1 font-display text-2xl font-bold text-cloud">Add countries</h2></div>
          <button type="button" onClick={onClose} className="p-2 text-mist hover:text-cloud" aria-label="Close country picker">×</button>
        </div>
        <div className="grid gap-4 border-b border-line p-5 sm:grid-cols-[1fr_180px] sm:p-6">
          <Input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search country or ISO code…" aria-label="Search countries" />
          <Select value={status} onChange={(event) => setStatus(event.target.value as typeof status)} aria-label="Country status to add">
            <option value="visited">Visited</option><option value="lived">Lived</option><option value="wishlist">Wishlist</option>
          </Select>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-3 sm:p-4">
          {visible.map((country) => {
            const checked = selected.has(country.code);
            return (
              <div key={country.code} className="flex items-center gap-3 border-b border-line px-3 py-3 hover:bg-mint/5">
                <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-3">
                  <input type="checkbox" checked={checked} onChange={() => setSelected((current) => { const next = new Set(current); checked ? next.delete(country.code) : next.add(country.code); return next; })} className="h-4 w-4 shrink-0 accent-[rgb(var(--mint))]" />
                  <span className="min-w-0"><span className="block truncate font-display font-semibold text-cloud">{country.name}</span><span className="font-mono text-[9px] uppercase tracking-label text-mist">{country.code} · {statusByCode.get(country.code) ? STATUS_LABEL[statusByCode.get(country.code)!] : country.continent}</span></span>
                </label>
                <button type="button" onClick={() => onOpenCountry(country.code)} className="shrink-0 font-mono text-[9px] uppercase tracking-label text-mist hover:text-mint" aria-label={`Open ${country.name}`}>
                  Open
                </button>
              </div>
            );
          })}
          {!visible.length ? <p className="p-8 text-center text-sm text-mist">No matching country.</p> : null}
        </div>
        <div className="flex items-center justify-between border-t border-line p-5 sm:p-6">
          <p className="font-mono text-[10px] uppercase tracking-label text-mist">{selected.size} selected</p>
          <Button disabled={!selected.size || saving} onClick={() => onSave(Array.from(selected), status)}>{saving ? "Saving…" : "Add to my world"}</Button>
        </div>
      </div>
    </div>
  );
}

export function TravelMapClient() {
  const { user, isLoading: authLoading } = useAuth();
  const [catalog, setCatalog] = useState<CountryCatalogResponse | null>(null);
  const [travelMap, setTravelMap] = useState<TravelMapResponse | null>(null);
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [addCountriesOpen, setAddCountriesOpen] = useState(false);
  const [visitDraft, setVisitDraft] = useState<VisitDraft | null>(null);

  const load = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError("");
    try {
      const [catalogData, mapData] = await Promise.all([
        apiGet<CountryCatalogResponse>("/countries"),
        apiGet<TravelMapResponse>("/me/travel-map"),
      ]);
      setCatalog(catalogData);
      setTravelMap(mapData);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load your travel map.");
    } finally {
      setLoading(false);
    }
  }, [user]);

  const refreshTravelMap = useCallback(async () => {
    if (!user) return;
    setTravelMap(await apiGet<TravelMapResponse>("/me/travel-map"));
  }, [user]);

  useEffect(() => { void load(); }, [load]);

  const metadataByCode = useMemo(() => new Map(catalog?.countries.map((country) => [country.code, country]) ?? []), [catalog]);
  const countryByCode = useMemo(() => new Map(travelMap?.countries.map((country) => [country.code, country]) ?? []), [travelMap]);
  const selectedMetadata = selectedCode ? metadataByCode.get(selectedCode) : undefined;
  const selectedCountry = selectedCode ? countryByCode.get(selectedCode) : undefined;

  async function updateCountry(patch: CountryPatch) {
    if (!selectedCode || !travelMap || !selectedMetadata) return;
    const previous = travelMap;
    const current = selectedCountry ?? {
      code: selectedMetadata.code, name: selectedMetadata.name, continent: selectedMetadata.continent,
      visited: false, lived: false, wishlist: false, primaryStatus: "unvisited" as const,
      visitCount: 0, residenceCount: 0, visits: [], updatedAt: new Date().toISOString(),
    };
    const next = { ...current, ...patch };
    if (patch.lived) { next.visited = true; next.wishlist = false; }
    if (patch.visited) next.wishlist = false;
    next.primaryStatus = next.lived ? "lived" : next.visited ? "visited" : next.wishlist ? "wishlist" : "unvisited";
    setTravelMap({ ...travelMap, countries: [...travelMap.countries.filter((country) => country.code !== selectedCode), next] });
    setBusy(true);
    setError("");
    try {
      await apiPatch(`/me/travel-map/countries/${selectedCode}`, patch);
      await refreshTravelMap();
    } catch (saveError) {
      setTravelMap(previous);
      setError(saveError instanceof Error ? saveError.message : "Could not update that country.");
    } finally { setBusy(false); }
  }

  async function saveBulk(codes: string[], status: "visited" | "lived" | "wishlist") {
    setBusy(true); setError("");
    try {
      const updated = await apiPost<TravelMapResponse>("/me/travel-map/countries/bulk", { countryCodes: codes, status, enabled: true });
      setTravelMap(updated); setAddCountriesOpen(false);
    } catch (saveError) { setError(saveError instanceof Error ? saveError.message : "Could not add countries."); }
    finally { setBusy(false); }
  }

  function openVisit(kind: "visit" | "lived", visit?: CountryVisit) {
    setVisitDraft(visit ? {
      id: visit.id, kind: visit.kind, startDate: visit.startDate ?? "", endDate: visit.endDate ?? "",
      startPrecision: visit.startPrecision, endPrecision: visit.endPrecision, note: visit.note ?? "",
    } : { ...EMPTY_VISIT, kind });
  }

  async function saveVisit() {
    if (!selectedCode || !visitDraft) return;
    setBusy(true); setError("");
    const body = {
      kind: visitDraft.kind,
      startDate: visitDraft.startPrecision === "unknown" ? null : visitDraft.startDate || null,
      endDate: visitDraft.endPrecision === "unknown" ? null : visitDraft.endDate || null,
      note: visitDraft.note || null,
    };
    try {
      if (visitDraft.id) await apiPatch(`/me/travel-map/visits/${visitDraft.id}`, body);
      else await apiPost(`/me/travel-map/countries/${selectedCode}/visits`, body);
      setVisitDraft(null); await refreshTravelMap();
    } catch (saveError) { setError(saveError instanceof Error ? saveError.message : "Could not save this memory."); }
    finally { setBusy(false); }
  }

  async function deleteVisit(visit: CountryVisit) {
    if (!window.confirm(`Delete this ${visit.kind === "lived" ? "lived-here record" : "visit"}?`)) return;
    setBusy(true); setError("");
    try { await apiDelete(`/me/travel-map/visits/${visit.id}`); await refreshTravelMap(); }
    catch (deleteError) { setError(deleteError instanceof Error ? deleteError.message : "Could not delete this memory."); }
    finally { setBusy(false); }
  }

  if (authLoading) return <AppShell><div className="flex min-h-[55vh] items-center justify-center"><Spinner label="Loading your world…" /></div></AppShell>;
  if (!user) return (
    <AppShell><section className="mx-auto max-w-xl py-24 text-center"><p className="font-mono text-[10px] uppercase tracking-label text-mint">Private travel profile</p><h1 className="mt-3 font-display text-4xl font-bold text-cloud">Log in to map your world.</h1><p className="mt-4 text-mist">Your travel history is private and follows you across devices.</p><div className="mt-8 flex justify-center gap-3"><ButtonLink href="/login">Log in</ButtonLink><ButtonLink href="/signup" variant="secondary">Create account</ButtonLink></div></section></AppShell>
  );

  return (
    <AppShell wide>
      <div className="mx-auto max-w-7xl px-4 pb-16 pt-10 sm:px-6">
        <header className="flex flex-wrap items-end justify-between gap-6">
          <div><p className="font-mono text-[10px] font-semibold uppercase tracking-label text-mint">My World</p><h1 className="mt-2 font-display text-5xl font-extrabold tracking-tight text-cloud sm:text-6xl">The places that shaped you.</h1><p className="mt-4 max-w-2xl text-lg leading-relaxed text-mist">Remember where you&apos;ve been, keep a quiet wishlist, and let Triplet find the next place worth going.</p></div>
          <Button onClick={() => setAddCountriesOpen(true)}>Add countries</Button>
        </header>
        {error ? <div className="mt-6"><Notice tone="error">{error}</Notice></div> : null}
        {loading || !catalog || !travelMap ? <div className="flex min-h-[560px] items-center justify-center"><Spinner label="Drawing your world…" /></div> : (
          <>
            <div className="mt-9"><TravelStats map={travelMap} /></div>
            <div className="mt-7 flex flex-wrap items-center justify-between gap-4"><Legend /><p className="font-mono text-[9px] uppercase tracking-label text-mist/60">Private to your account</p></div>
            {!travelMap.countries.length ? <div className="mt-8 border-y border-line py-6 text-center"><h2 className="font-display text-2xl font-bold text-cloud">Map your world</h2><p className="mt-2 text-sm text-mist">Start with a few countries. Dates can always come later.</p><Button className="mt-4" size="sm" onClick={() => setAddCountriesOpen(true)}>Start adding countries</Button></div> : null}
            <div className="mt-5 grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
              <div className="relative min-w-0 overflow-visible lg:-ml-12 lg:-mr-8 lg:-mt-8">
                <TravelMapGlobe catalog={catalog.countries} countries={travelMap.countries} selectedCode={selectedCode} onSelect={setSelectedCode} />
              </div>
              <div className="hidden lg:block">
                {selectedMetadata ? <CountryPanel metadata={selectedMetadata} country={selectedCountry} busy={busy} onClose={() => setSelectedCode(null)} onUpdate={(patch) => void updateCountry(patch)} onAddVisit={(kind) => openVisit(kind)} onEditVisit={(visit) => openVisit(visit.kind, visit)} onDeleteVisit={(visit) => void deleteVisit(visit)} /> : <div className="border border-line p-8"><p className="font-mono text-[9px] uppercase tracking-label text-mint">Explore</p><h2 className="mt-2 font-display text-2xl font-bold text-cloud">Select a country</h2><p className="mt-3 text-sm leading-relaxed text-mist">Rotate the globe or use Add countries for a quick, keyboard-friendly list.</p></div>}
              </div>
            </div>
            <section className="mt-12 border-t border-line pt-7"><div className="flex items-baseline justify-between gap-4"><div><p className="font-mono text-[9px] uppercase tracking-label text-mint">Continents</p><h2 className="mt-1 font-display text-2xl font-bold text-cloud">Progress, without pressure.</h2></div><span className="font-mono text-[9px] uppercase tracking-label text-mist">{travelMap.stats.continentsVisited} explored</span></div><div className="mt-5 grid gap-x-8 sm:grid-cols-2 lg:grid-cols-3">{travelMap.stats.continentProgress.map((continent) => <div key={continent.name} className="border-b border-line py-4"><div className="flex justify-between"><span className="text-sm font-medium text-cloud">{continent.name}</span><span className="mono-num font-mono text-xs text-mist">{continent.visited} / {continent.total}</span></div><div className="mt-2 h-px bg-line"><div className="h-px bg-mint" style={{ width: `${continent.total ? Math.min(100, (continent.visited / continent.total) * 100) : 0}%` }} /></div></div>)}</div></section>
          </>
        )}
      </div>
      {selectedMetadata ? <><button type="button" className="fixed inset-0 z-40 bg-ink/55 lg:hidden" onClick={() => setSelectedCode(null)} aria-label="Close country details" /><div className="lg:hidden"><CountryPanel metadata={selectedMetadata} country={selectedCountry} busy={busy} onClose={() => setSelectedCode(null)} onUpdate={(patch) => void updateCountry(patch)} onAddVisit={(kind) => openVisit(kind)} onEditVisit={(visit) => openVisit(visit.kind, visit)} onDeleteVisit={(visit) => void deleteVisit(visit)} /></div></> : null}
      {addCountriesOpen && catalog && travelMap ? <AddCountries catalog={catalog.countries} countries={travelMap.countries} saving={busy} onClose={() => setAddCountriesOpen(false)} onOpenCountry={(code) => { setSelectedCode(code); setAddCountriesOpen(false); }} onSave={(codes, status) => void saveBulk(codes, status)} /> : null}
      {visitDraft && selectedMetadata ? <VisitEditor countryName={selectedMetadata.name} draft={visitDraft} saving={busy} onChange={setVisitDraft} onClose={() => setVisitDraft(null)} onSave={() => void saveVisit()} /> : null}
    </AppShell>
  );
}
