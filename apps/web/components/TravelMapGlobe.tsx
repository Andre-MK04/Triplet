"use client";

import { ThreeEvent } from "@react-three/fiber";
import { feature } from "topojson-client";
import ConicPolygonGeometry from "three-conic-polygon-geometry";
import { useEffect, useMemo, useRef, useState } from "react";
import type { MutableRefObject } from "react";
import * as THREE from "three";
import worldTopology from "world-atlas/countries-110m.json";

import type { CountryCatalogEntry, TravelMapCountry, TravelMapStatus } from "../lib/types";
import RouteGlobe from "./RouteGlobe";
import { useResolvedTheme } from "./useResolvedTheme";

type PolygonCoordinates = number[][][];
type Geometry =
  | { type: "Polygon"; coordinates: PolygonCoordinates }
  | { type: "MultiPolygon"; coordinates: PolygonCoordinates[] };
type CountryFeature = {
  id?: string | number;
  properties?: { name?: string };
  geometry: Geometry | null;
};

const topology = worldTopology as unknown as {
  type: "Topology";
  objects: { countries: object };
  arcs: unknown[];
  transform?: object;
};

const COUNTRY_FEATURES = (
  feature(topology as never, topology.objects.countries as never) as unknown as { features: CountryFeature[] }
).features;

const STATUS_COLORS_DARK: Record<TravelMapStatus, string> = {
  lived: "#ff9a78",
  visited: "#7ddfc3",
  wishlist: "#e8c46a",
  unvisited: "#476575",
};

const STATUS_COLORS_LIGHT: Record<TravelMapStatus, string> = {
  lived: "#d65f42",
  visited: "#16836f",
  wishlist: "#a97a12",
  unvisited: "#f0f8fb",
};

type CountryPolygonProps = {
  code: string;
  coordinates: PolygonCoordinates;
  status: TravelMapStatus;
  selected: boolean;
  light: boolean;
  onHover: (code: string | null) => void;
  onSelect: (code: string) => void;
  pointerStart: MutableRefObject<{ code: string; x: number; y: number } | null>;
};

function CountryPolygon({ code, coordinates, status, selected, light, onHover, onSelect, pointerStart }: CountryPolygonProps) {
  const geometry = useMemo(
    () => new ConicPolygonGeometry(coordinates, 1.902, selected ? 1.942 : 1.922, false, true, false, 7),
    [coordinates, selected],
  );

  useEffect(() => () => geometry.dispose(), [geometry]);

  const palette = light ? STATUS_COLORS_LIGHT : STATUS_COLORS_DARK;
  const unvisited = status === "unvisited";
  const opacity = unvisited ? (light ? 0.64 : 0.36) : 0.86;

  function hover(event: ThreeEvent<PointerEvent>) {
    event.stopPropagation();
    document.body.style.cursor = "pointer";
    onHover(code);
  }

  function leave(event: ThreeEvent<PointerEvent>) {
    event.stopPropagation();
    document.body.style.cursor = "";
    onHover(null);
  }

  function pointerDown(event: ThreeEvent<PointerEvent>) {
    pointerStart.current = { code, x: event.nativeEvent.clientX, y: event.nativeEvent.clientY };
  }

  function pointerUp(event: ThreeEvent<PointerEvent>) {
    const start = pointerStart.current;
    pointerStart.current = null;
    if (!start || start.code !== code) return;
    const distance = Math.hypot(event.nativeEvent.clientX - start.x, event.nativeEvent.clientY - start.y);
    if (distance > 7) return;
    event.stopPropagation();
    onSelect(code);
  }

  return (
    <group>
      <mesh
        geometry={geometry}
        onPointerOver={hover}
        onPointerOut={leave}
        onPointerDown={pointerDown}
        onPointerUp={pointerUp}
        onClick={(event) => {
          event.stopPropagation();
          onSelect(code);
        }}
        renderOrder={2}
      >
        <meshBasicMaterial
          color={selected ? (light ? "#0d5f51" : "#b7f5e3") : palette[status]}
          transparent
          opacity={selected ? 0.98 : opacity}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>
      {unvisited && !selected ? (
        <mesh geometry={geometry} renderOrder={3}>
          <meshBasicMaterial
            color={light ? "#ffffff" : "#9fd8ea"}
            transparent
            opacity={light ? 0.16 : 0.1}
            side={THREE.DoubleSide}
            depthWrite={false}
            blending={THREE.AdditiveBlending}
            polygonOffset
            polygonOffsetFactor={-1}
          />
        </mesh>
      ) : null}
    </group>
  );
}

function CountryLayer({
  catalog,
  countryStates,
  selectedCode,
  onHover,
  onSelect,
}: {
  catalog: CountryCatalogEntry[];
  countryStates: Record<string, TravelMapCountry>;
  selectedCode: string | null;
  onHover: (code: string | null) => void;
  onSelect: (code: string) => void;
}) {
  const light = useResolvedTheme() === "light";
  const pointerStart = useRef<{ code: string; x: number; y: number } | null>(null);
  const codeByNumeric = useMemo(
    () => new Map(catalog.map((country) => [country.numericCode, country.code])),
    [catalog],
  );

  const polygons = useMemo(
    () =>
      COUNTRY_FEATURES.flatMap((countryFeature) => {
        const numeric = String(countryFeature.id ?? "").padStart(3, "0");
        const code = codeByNumeric.get(numeric);
        if (!code || !countryFeature.geometry) return [];
        const coordinateSets =
          countryFeature.geometry.type === "Polygon"
            ? [countryFeature.geometry.coordinates]
            : countryFeature.geometry.coordinates;
        return coordinateSets.map((coordinates, index) => ({ code, coordinates, index }));
      }),
    [codeByNumeric],
  );

  return (
    // ConicPolygonGeometry uses globe.gl's axis convention. A 90° Y rotation
    // aligns it with Triplet's existing lat/lon vectors and route arcs.
    <group rotation={[0, Math.PI / 2, 0]}>
      {polygons.map(({ code, coordinates, index }) => (
        <CountryPolygon
          key={`${code}-${index}`}
          code={code}
          coordinates={coordinates}
          status={countryStates[code]?.primaryStatus ?? "unvisited"}
          selected={selectedCode === code}
          light={light}
          onHover={onHover}
          onSelect={onSelect}
          pointerStart={pointerStart}
        />
      ))}
    </group>
  );
}

export function TravelMapGlobe({
  catalog,
  countries,
  selectedCode,
  onSelect,
}: {
  catalog: CountryCatalogEntry[];
  countries: TravelMapCountry[];
  selectedCode: string | null;
  onSelect: (code: string) => void;
}) {
  const [hoveredCode, setHoveredCode] = useState<string | null>(null);
  const metadata = useMemo(() => new Map(catalog.map((country) => [country.code, country])), [catalog]);
  const countryStates = useMemo(
    () => Object.fromEntries(countries.map((country) => [country.code, country])),
    [countries],
  );
  const activeCode = hoveredCode ?? selectedCode;

  return (
    <div className="relative h-[clamp(320px,72vw,720px)] w-full touch-none overflow-visible">
      <RouteGlobe
        animate
        interactive
        ariaHidden={false}
        ariaLabel="Interactive personal travel globe. Use the searchable country list as a keyboard-accessible alternative."
        showRoutes={false}
        showEuropeOutline={false}
        cameraDistance={6.25}
        overlay={
          <CountryLayer
            catalog={catalog}
            countryStates={countryStates}
            selectedCode={selectedCode}
            onHover={setHoveredCode}
            onSelect={onSelect}
          />
        }
      />
      {activeCode && metadata.get(activeCode) ? (
        <div className="pointer-events-none absolute left-3 top-3 border border-line bg-ink/90 px-3 py-2 shadow-lg backdrop-blur sm:left-5 sm:top-5">
          <p className="font-display text-sm font-semibold text-cloud">{metadata.get(activeCode)?.name}</p>
          <p className="mt-0.5 font-mono text-[9px] uppercase tracking-label text-mist">
            {countryStates[activeCode]?.primaryStatus ?? "Select to update"}
          </p>
        </div>
      ) : null}
      <p className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2 whitespace-nowrap font-mono text-[9px] uppercase tracking-label text-mist/70">
        Drag to rotate · tap a country
      </p>
    </div>
  );
}
