"use client";

import { Html, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useState } from "react";
import * as THREE from "three";

import { AIRPORTS } from "../lib/airports";

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

function DotSphere() {
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
      <pointsMaterial color="#3d5a6e" size={0.022} sizeAttenuation transparent opacity={0.9} />
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

// Stylised low-poly Europe: coarse outlines as [lat, lon] loops, deliberately
// abstract (an instrument overlay, not a map projection).
const EUROPE_OUTLINES: Array<Array<[number, number]>> = [
  // Continental silhouette (Iberia → Atlantic coast → Scandinavia → east → Med).
  [
    [36.0, -5.6], [37.0, -8.9], [38.7, -9.4], [41.1, -8.9], [43.4, -8.5], [43.4, -1.8],
    [46.0, -1.2], [48.4, -4.8], [49.7, -1.9], [51.0, 2.0], [53.4, 5.0], [55.5, 8.3],
    [57.7, 10.6], [58.0, 7.0], [60.4, 5.0], [63.4, 9.7], [67.3, 14.0], [71.0, 25.8],
    [70.0, 28.5], [66.0, 30.0], [61.0, 28.5], [59.9, 30.3], [57.0, 24.1], [54.4, 19.0],
    [54.1, 13.0], [53.5, 8.5], [52.0, 4.6], [51.0, 3.0], [48.6, -1.5], [46.5, -1.1],
    [44.0, -1.3], [43.3, -2.0], [41.9, 3.2], [39.5, 0.0], [36.7, -2.5], [36.0, -5.6],
  ],
  // Mediterranean arc: south France → Italy → Adriatic → Greece → back across.
  [
    [42.5, 3.2], [43.3, 5.4], [43.7, 7.3], [44.4, 8.9], [43.0, 10.0], [41.9, 12.5],
    [40.6, 14.3], [38.9, 16.6], [37.9, 15.7], [40.0, 18.5], [42.0, 15.0], [44.8, 13.6],
    [45.6, 13.8], [44.0, 15.2], [42.6, 18.1], [40.5, 19.4], [38.4, 21.5], [36.8, 22.5],
    [38.0, 23.7], [40.5, 22.9], [41.0, 29.0],
  ],
  // Britain.
  [
    [50.1, -5.7], [50.8, -0.8], [51.4, 1.4], [52.9, 1.7], [54.5, -0.6], [56.0, -2.6],
    [57.5, -1.8], [58.6, -5.0], [56.5, -6.0], [54.6, -3.4], [53.3, -4.6], [51.6, -5.1],
    [50.1, -5.7],
  ],
  // Ireland.
  [
    [51.8, -10.2], [52.2, -6.4], [53.3, -6.1], [55.2, -7.6], [54.3, -10.0], [51.8, -10.2],
  ],
  // Iceland.
  [
    [63.4, -18.5], [64.0, -22.6], [65.6, -24.0], [66.3, -18.7], [65.0, -13.8], [63.4, -18.5],
  ],
];

function latLonLoopPoints(loop: Array<[number, number]>, radius: number): THREE.Vector3[] {
  return loop.map(([lat, lon]) => latLonToVector3(lat, lon, radius));
}

function EuropeOutline() {
  const lines = useMemo(
    () =>
      EUROPE_OUTLINES.map((loop) => {
        const geometry = new THREE.BufferGeometry().setFromPoints(
          latLonLoopPoints(loop, GLOBE_RADIUS * 1.004),
        );
        const material = new THREE.LineBasicMaterial({
          color: "#7ddfc3",
          transparent: true,
          opacity: 0.4,
        });
        return new THREE.Line(geometry, material);
      }),
    [],
  );
  return (
    <group>
      {lines.map((line, index) => (
        <primitive key={index} object={line} />
      ))}
    </group>
  );
}

const ARC_SEGMENTS = 64;

function RouteArc({ from, to, phase, animate }: { from: string; to: string; phase: number; animate: boolean }) {
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
      color: "#7ddfc3",
      transparent: true,
      opacity: 0.85,
    });
    return new THREE.Line(geometry, material);
  }, [from, to]);

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
        <meshBasicMaterial color="#7ddfc3" />
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

function GlobeScene({ markers, animate }: { markers: GlobeMarker[]; animate: boolean }) {
  return (
    // Tilted and yawed so Europe (and its route arcs) faces the camera on first
    // paint — solved so Vienna lands just left of viewport centre, and the slow
    // auto-rotate carries the continent through centre.
    <group rotation={[0.75, -2.3, 0]}>
      {/* Solid core so the far side of the wireframe reads as a planet, not a cage. */}
      <mesh>
        <sphereGeometry args={[GLOBE_RADIUS * 0.98, 64, 64]} />
        <meshPhongMaterial color="#090f15" />
      </mesh>
      {/* Wireframe shell: the "wireframe-meets-satellite" instrument look. */}
      <mesh>
        <sphereGeometry args={[GLOBE_RADIUS, 48, 48]} />
        <meshPhongMaterial
          color="#16202a"
          emissive="#1d2733"
          specular="#343a41"
          shininess={10}
          wireframe
          transparent
          opacity={0.45}
        />
      </mesh>
      <DotSphere />
      <EuropeOutline />
      {DEFAULT_ROUTES.map(([from, to], index) => (
        <RouteArc key={`${from}-${to}`} from={from} to={to} phase={index * 0.45} animate={animate} />
      ))}
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
};

export default function RouteGlobe({ animate = true, interactive = true, markers = [] }: RouteGlobeProps) {
  const reducedMotion = usePrefersReducedMotion();
  const shouldAnimate = animate && !reducedMotion;
  return (
    <Canvas
      camera={{ position: [0, 0, 4.6], fov: 42 }}
      dpr={[1, 1.75]}
      gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      style={{ background: "transparent" }}
      aria-hidden
    >
      <ambientLight color="#6a7681" intensity={2.4} />
      <directionalLight color="#7ddfc3" intensity={1.6} position={[5, 3, 5]} />
      <GlobeScene markers={markers} animate={shouldAnimate} />
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
