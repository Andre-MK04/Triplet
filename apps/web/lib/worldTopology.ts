"use client";

import { useEffect, useState } from "react";

export type PolygonCoordinates = number[][][];

/**
 * Narrower than GeoJSON's own union on purpose.
 *
 * The country layer contains only polygons and multipolygons, and both globes
 * read `.coordinates` directly. Typing this as the full GeoJSON `Geometry`
 * would drag in geometry collections that cannot appear here and force a cast
 * at every use.
 */
export type CountryGeometry =
  | { type: "Polygon"; coordinates: PolygonCoordinates }
  | { type: "MultiPolygon"; coordinates: PolygonCoordinates[] };

export type CountryFeature = {
  id?: string | number;
  properties?: { name?: string };
  geometry: CountryGeometry | null;
};

/**
 * The world's country outlines, loaded once and shared.
 *
 * Two globes need these — the landing/auth decoration and the travel map — and
 * each used to import the topology at module scope and convert it to GeoJSON
 * features itself. That meant the 105 KB source was parsed as part of a
 * JavaScript chunk rather than as data, and the travel map, which renders a
 * RouteGlobe inside itself, built and held two identical feature arrays.
 *
 * The import is deliberately dynamic. It keeps the topology and topojson-client
 * in their own chunk, fetched only when a globe actually renders, while leaving
 * the file under npm's management — copying it into `public/` at build time
 * would shave a little more but makes a visible globe depend on a copy step
 * silently having run.
 */
let pending: Promise<CountryFeature[]> | null = null;

export function loadCountryFeatures(): Promise<CountryFeature[]> {
  // Memoised on the promise, not the result: two globes mounting in the same
  // tick must share one download rather than starting a race.
  if (pending) return pending;

  pending = (async () => {
    const [{ feature }, topojson] = await Promise.all([
      import("topojson-client"),
      import("world-atlas/countries-110m.json"),
    ]);

    const topology = (topojson.default ?? topojson) as unknown as {
      type: "Topology";
      objects: { countries: object };
      arcs: unknown[];
      transform?: object;
    };

    return (
      feature(topology as never, topology.objects.countries as never) as unknown as {
        features: CountryFeature[];
      }
    ).features;
  })();

  return pending;
}

/**
 * The country features, or an empty list until they arrive.
 *
 * Globes render their sphere, routes and markers immediately and gain country
 * outlines a moment later. That ordering is deliberate: the outlines are the
 * heaviest part and the least important — a globe with no borders still reads
 * as a globe, whereas an empty box while the topology downloads does not.
 */
export function useCountryFeatures(): CountryFeature[] {
  const [features, setFeatures] = useState<CountryFeature[]>([]);

  useEffect(() => {
    let cancelled = false;
    loadCountryFeatures()
      .then((loaded) => {
        if (!cancelled) setFeatures(loaded);
      })
      .catch(() => {
        // A globe without borders is a degraded globe, not a broken page.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return features;
}
