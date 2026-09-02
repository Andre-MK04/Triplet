"use client";

import { Html, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { ReactNode, useEffect, useMemo, useState } from "react";
import * as THREE from "three";
import ConicPolygonGeometry from "three-conic-polygon-geometry";

import { AIRPORTS } from "../lib/airports";
import { useResolvedTheme } from "./useResolvedTheme";
import { useCountryFeatures } from "../lib/worldTopology";
import type { PolygonCoordinates } from "../lib/worldTopology";


function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const onChange = (event: MediaQueryListEvent) => setReduced(event.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

const GLOBE_RADIUS = 1.9;

/** A destination pin with an optional label (e.g. a live price tag: "MIL €39"). */
export type GlobeMarker = {
  code: string;
  label?: string;
};

function latLonToVector3(lat: number, lon: number, radius: number): THREE.Vector3 {
  const phi = ((90 - lat) * Math.PI) / 180;
  const theta = ((lon + 180) * Math.PI) / 180;
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  );
}

function positionFor(code: string): THREE.Vector3 | null {
  const airport = AIRPORTS.find((a) => a.code === code);
  if (!airport) return null;
  return latLonToVector3(airport.lat, airport.lon, GLOBE_RADIUS);
}

// Deterministic pseudo-random so the dot sphere is stable between renders.
function mulberry32(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function DotSphere({ light }: { light: boolean }) {
  const geometry = useMemo(() => {
    const random = mulberry32(42);
    const count = 700;
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      // Even-ish distribution using the golden spiral with jitter
      const y = 1 - (i / (count - 1)) * 2;
      const r = Math.sqrt(1 - y * y);
      const theta = i * 2.399963 + random() * 0.12;
      positions[i * 3] = Math.cos(theta) * r * GLOBE_RADIUS;
      positions[i * 3 + 1] = y * GLOBE_RADIUS;
      positions[i * 3 + 2] = Math.sin(theta) * r * GLOBE_RADIUS;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    return geo;
  }, []);

  return (
    <points geometry={geometry}>
      <pointsMaterial color={light ? "#526b78" : "#3d5a6e"} size={0.022} sizeAttenuation transparent opacity={light ? 0.72 : 0.9} />
    </points>
  );
}

const DEFAULT_ROUTES: Array<[string, string]> = [
  ["VIE", "ALC"],
  ["ZAG", "LIS"],
  ["VCE", "ATH"],
  ["BUD", "BCN"],
  ["LJU", "PMI"],
  ["TRS", "AGP"],
  ["VIE", "CPH"],
  ["BUD", "PAR"],
  ["ZAG", "BER"],
  ["VCE", "MAD"],
  ["LJU", "AMS"],
  ["VIE", "ARN"],
  ["BUD", "HEL"],
  ["TRS", "DUB"],
];

function CountrySurfacePolygon({ coordinates, light }: { coordinates: PolygonCoordinates; light: boolean }) {
  const geometry = useMemo(
    () => new ConicPolygonGeometry(coordinates, 1.902, 1.918, false, true, false, 7),
    [coordinates],
  );

  useEffect(() => () => geometry.dispose(), [geometry]);

  return (
    <mesh geometry={geometry} renderOrder={1}>
      <meshBasicMaterial
        color={light ? "#8198a3" : "#5f7f90"}
        transparent
        opacity={light ? 0.42 : 0.46}
        side={THREE.DoubleSide}
        depthWrite={false}
      />
    </mesh>
  );
}

function CountrySurface({ light }: { light: boolean }) {
  const countryFeatures = useCountryFeatures();
  const polygons = useMemo(
    () =>
      countryFeatures.flatMap((countryFeature) => {
        if (!countryFeature.geometry) return [];
        return countryFeature.geometry.type === "Polygon"
          ? [countryFeature.geometry.coordinates]
          : countryFeature.geometry.coordinates;
      }),
    // Recomputed once, when the topology finishes loading.
    [countryFeatures],
  );

  return (
    // ConicPolygonGeometry uses globe.gl's axis convention. A 90° Y rotation
    // aligns the topojson country layer with the existing route/marker vectors.
    <group rotation={[0, Math.PI / 2, 0]}>
      {polygons.map((coordinates, index) => (
        <CountrySurfacePolygon key={index} coordinates={coordinates} light={light} />
      ))}
    </group>
  );
}

const ARC_SEGMENTS = 64;

function RouteArc({ from, to, phase, animate, light }: { from: string; to: string; phase: number; animate: boolean; light: boolean }) {
  const line = useMemo(() => {
    const start = positionFor(from);
    const end = positionFor(to);
    if (!start || !end) return null;
    const mid = start.clone().add(end).multiplyScalar(0.5);
    mid.setLength(GLOBE_RADIUS * (1.18 + start.distanceTo(end) * 0.08));
    const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
    const points = curve.getPoints(ARC_SEGMENTS);
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineBasicMaterial({
      color: light ? "#16836f" : "#7ddfc3",
      transparent: true,
      opacity: 0.85,
    });
    return new THREE.Line(geometry, material);
  }, [from, to, light]);

  useFrame(({ clock }) => {
    if (!line) return;
    if (!animate) {
      // Reduced motion: show the full route, no draw cycle.
      line.geometry.setDrawRange(0, ARC_SEGMENTS + 1);
      return;
    }
    // Draw the arc from origin to destination on a repeating cycle.
    const cycle = (clock.elapsedTime * 0.35 + phase) % 1.4;
    const progress = Math.min(cycle / 1, 1);
    line.geometry.setDrawRange(0, Math.max(2, Math.floor(progress * (ARC_SEGMENTS + 1))));
  });

  if (!line) return null;
  const start = positionFor(from)!;
  const end = positionFor(to)!;
  return (
    <group>
      <primitive object={line} />
      <mesh position={start}>
        <sphereGeometry args={[0.028, 12, 12]} />
        <meshBasicMaterial color={light ? "#16836f" : "#7ddfc3"} />
      </mesh>
      <mesh position={end}>
        <sphereGeometry args={[0.028, 12, 12]} />
        <meshBasicMaterial color="#ff9a78" />
      </mesh>
    </group>
  );
}

function PriceTag({ marker }: { marker: GlobeMarker }) {
  const position = useMemo(() => positionFor(marker.code), [marker.code]);
  if (!position || !marker.label) return null;
  const anchor = position.clone().multiplyScalar(1.06);
  return (
    <Html position={anchor} center zIndexRange={[20, 0]} occlude={false}>
      <span className="pointer-events-none whitespace-nowrap border border-line bg-ink/90 px-1.5 py-0.5 font-mono text-[10px] font-medium tracking-[0.06em] text-cloud">
        {marker.label}
      </span>
    </Html>
  );
}

function GlobeScene({
  markers,
  animate,
  overlay,
  light,
  showRoutes,
  showEuropeOutline,
}: {
  markers: GlobeMarker[];
  animate: boolean;
  overlay?: ReactNode;
  light: boolean;
  showRoutes: boolean;
  showEuropeOutline: boolean;
}) {
  return (
    // Tilted and yawed so Europe (and its route arcs) faces the camera on first
    // paint — solved so Vienna lands just left of viewport centre, and the slow
    // auto-rotate carries the continent through centre.
    <group rotation={[0.75, -2.3, 0]}>
      {/* Solid core so the far side of the wireframe reads as a planet, not a cage. */}
      <mesh>
        <sphereGeometry args={[GLOBE_RADIUS * 0.98, 64, 64]} />
        <meshPhongMaterial color={light ? "#dce6ea" : "#090f15"} />
      </mesh>
      {/* Wireframe shell: the "wireframe-meets-satellite" instrument look. */}
      <mesh>
        <sphereGeometry args={[GLOBE_RADIUS, 48, 48]} />
        <meshPhongMaterial
          color={light ? "#8299a4" : "#16202a"}
          emissive={light ? "#aebfc7" : "#1d2733"}
          specular={light ? "#ffffff" : "#343a41"}
          shininess={10}
          wireframe
          transparent
          opacity={light ? 0.44 : 0.45}
        />
      </mesh>
      <DotSphere light={light} />
      {showEuropeOutline ? <CountrySurface light={light} /> : null}
      {overlay}
      {showRoutes ? DEFAULT_ROUTES.map(([from, to], index) => (
        <RouteArc key={`${from}-${to}`} from={from} to={to} phase={index * 0.45} animate={animate} light={light} />
      )) : null}
      {markers.map((marker) => (
        <PriceTag key={marker.code} marker={marker} />
      ))}
    </group>
  );
}

type RouteGlobeProps = {
  animate?: boolean;
  /** Drag to rotate. Zoom and pan stay disabled so it behaves like an instrument, not a map. */
  interactive?: boolean;
  markers?: GlobeMarker[];
  /** Optional geometry rendered in the same rotated world space as the globe. */
  overlay?: ReactNode;
  /** Homepage visuals are decorative; the Travel Map supplies an accessible label. */
  ariaHidden?: boolean;
  ariaLabel?: string;
  showRoutes?: boolean;
  showEuropeOutline?: boolean;
  cameraDistance?: number;
};

export default function RouteGlobe({
  animate = true,
  interactive = true,
  markers = [],
  overlay,
  ariaHidden = true,
  ariaLabel,
  showRoutes = true,
  showEuropeOutline = true,
  cameraDistance = 4.6,
}: RouteGlobeProps) {
  const reducedMotion = usePrefersReducedMotion();
  const light = useResolvedTheme() === "light";
  const [webGlAvailable, setWebGlAvailable] = useState<boolean | null>(null);
  const shouldAnimate = animate && !reducedMotion;

  useEffect(() => {
    try {
      const canvas = document.createElement("canvas");
      setWebGlAvailable(Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl")));
    } catch {
      setWebGlAvailable(false);
    }
  }, []);

  if (webGlAvailable === false) {
    return (
      <div
        className="flex h-full min-h-64 items-center justify-center rounded-full border border-line bg-ink-soft"
        role="img"
        aria-label={ariaLabel ?? "Triplet globe"}
      >
        <div className="relative h-48 w-48 rounded-full border border-mint/40 bg-ink-raised shadow-[inset_-24px_-18px_45px_rgba(0,0,0,0.18)]">
          <span className="absolute left-[28%] top-[30%] h-2 w-2 rounded-full bg-mint" />
          <span className="absolute right-[24%] top-[44%] h-2 w-2 rounded-full bg-coral" />
          <span className="absolute bottom-[28%] left-[45%] font-mono text-[10px] uppercase tracking-label text-mist">
            Map view
          </span>
        </div>
      </div>
    );
  }

  return (
    <Canvas
      camera={{ position: [0, 0, cameraDistance], fov: 42 }}
      dpr={[1, 1.75]}
      gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      style={{ background: "transparent" }}
      aria-hidden={ariaHidden || undefined}
      aria-label={!ariaHidden ? ariaLabel : undefined}
      role={!ariaHidden ? "img" : undefined}
    >
      <ambientLight color={light ? "#b8c8cf" : "#6a7681"} intensity={light ? 2.9 : 2.4} />
      <directionalLight color={light ? "#16836f" : "#7ddfc3"} intensity={1.6} position={[5, 3, 5]} />
      <GlobeScene
        markers={markers}
        animate={shouldAnimate}
        overlay={overlay}
        light={light}
        showRoutes={showRoutes}
        showEuropeOutline={showEuropeOutline}
      />
      <OrbitControls
        enableZoom={false}
        enablePan={false}
        enabled={interactive}
        autoRotate={shouldAnimate}
        autoRotateSpeed={0.3}
        rotateSpeed={0.6}
      />
    </Canvas>
  );
}
