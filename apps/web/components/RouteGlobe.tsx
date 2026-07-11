"use client";

import { Html, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import { AIRPORTS } from "../lib/airports";

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
];

const ARC_SEGMENTS = 64;

function RouteArc({ from, to, phase }: { from: string; to: string; phase: number }) {
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

function GlobeScene({ markers }: { markers: GlobeMarker[] }) {
  return (
    // Yawed so Europe (and its route arcs) faces the camera on first paint.
    <group rotation={[0.35, -1.75, 0]}>
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
      {DEFAULT_ROUTES.map(([from, to], index) => (
        <RouteArc key={`${from}-${to}`} from={from} to={to} phase={index * 0.7} />
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
  return (
    <Canvas
      camera={{ position: [0, 0, 5.4], fov: 42 }}
      dpr={[1, 1.75]}
      gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      style={{ background: "transparent" }}
      aria-hidden
    >
      <ambientLight color="#6a7681" intensity={2.4} />
      <directionalLight color="#7ddfc3" intensity={1.6} position={[5, 3, 5]} />
      <GlobeScene markers={markers} />
      <OrbitControls
        enableZoom={false}
        enablePan={false}
        enabled={interactive}
        autoRotate={animate}
        autoRotateSpeed={0.55}
        rotateSpeed={0.6}
      />
    </Canvas>
  );
}
