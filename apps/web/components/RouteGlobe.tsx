"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import { AIRPORTS } from "../lib/airports";

const GLOBE_RADIUS = 1.9;

function latLonToVector3(lat: number, lon: number, radius: number): THREE.Vector3 {
  const phi = ((90 - lat) * Math.PI) / 180;
  const theta = ((lon + 180) * Math.PI) / 180;
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  );
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
      <pointsMaterial color="#3d5a6e" size={0.022} sizeAttenuation transparent opacity={0.85} />
    </points>
  );
}

const ROUTES: Array<[string, string]> = [
  ["VIE", "ALC"],
  ["ZAG", "LIS"],
  ["VCE", "ATH"],
  ["BUD", "BCN"],
  ["LJU", "PMI"],
  ["TRS", "AGP"],
];

const ARC_SEGMENTS = 64;

function RouteArc({ from, to, phase }: { from: string; to: string; phase: number }) {
  const geometryRef = useRef<THREE.BufferGeometry>(null);
  const { line, glowPoints } = useMemo(() => {
    const a = AIRPORTS.find((airport) => airport.code === from)!;
    const b = AIRPORTS.find((airport) => airport.code === to)!;
    const start = latLonToVector3(a.lat, a.lon, GLOBE_RADIUS);
    const end = latLonToVector3(b.lat, b.lon, GLOBE_RADIUS);
    const mid = start.clone().add(end).multiplyScalar(0.5);
    mid.setLength(GLOBE_RADIUS * (1.18 + start.distanceTo(end) * 0.08));
    const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
    const points = curve.getPoints(ARC_SEGMENTS);
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineBasicMaterial({
      color: "#7ddfc3",
      transparent: true,
      opacity: 0.8,
    });
    const lineObject = new THREE.Line(geometry, material);
    return { line: lineObject, glowPoints: [start, end] };
  }, [from, to]);

  useFrame(({ clock }) => {
    // Draw the arc from origin to destination on a repeating cycle.
    const cycle = (clock.elapsedTime * 0.35 + phase) % 1.4;
    const progress = Math.min(cycle / 1, 1);
    line.geometry.setDrawRange(0, Math.max(2, Math.floor(progress * (ARC_SEGMENTS + 1))));
    geometryRef.current = line.geometry;
  });

  return (
    <group>
      <primitive object={line} />
      {glowPoints.map((point, index) => (
        <mesh key={index} position={point}>
          <sphereGeometry args={[0.032, 12, 12]} />
          <meshBasicMaterial color={index === 0 ? "#7ddfc3" : "#ff9a78"} />
        </mesh>
      ))}
    </group>
  );
}

function GlobeScene({ animate }: { animate: boolean }) {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((_, delta) => {
    if (animate && groupRef.current) {
      groupRef.current.rotation.y += delta * 0.08;
    }
  });

  return (
    <group ref={groupRef} rotation={[0.35, -0.6, 0]}>
      <mesh>
        <sphereGeometry args={[GLOBE_RADIUS * 0.995, 48, 48]} />
        <meshBasicMaterial color="#101a24" transparent opacity={0.92} />
      </mesh>
      <DotSphere />
      {ROUTES.map(([from, to], index) => (
        <RouteArc key={`${from}-${to}`} from={from} to={to} phase={index * 0.7} />
      ))}
    </group>
  );
}

export default function RouteGlobe({ animate = true }: { animate?: boolean }) {
  return (
    <Canvas
      camera={{ position: [0, 0, 5.4], fov: 42 }}
      dpr={[1, 1.75]}
      gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      style={{ background: "transparent" }}
      aria-hidden
    >
      <GlobeScene animate={animate} />
    </Canvas>
  );
}
