/**
 * A minimal localStorage for modules that remember things between visits.
 *
 * Real browser storage throws in private windows and when a quota is hit, and
 * the modules under test are written to survive that — so this is a plain
 * in-memory stand-in and the failure paths are exercised by stubbing instead.
 */
class MemoryStorage implements Storage {
  private store = new Map<string, string>();

  get length(): number {
    return this.store.size;
  }
  clear(): void {
    this.store.clear();
  }
  getItem(key: string): string | null {
    return this.store.has(key) ? this.store.get(key)! : null;
  }
  key(index: number): string | null {
    return [...this.store.keys()][index] ?? null;
  }
  removeItem(key: string): void {
    this.store.delete(key);
  }
  setItem(key: string, value: string): void {
    this.store.set(key, String(value));
  }
}

const storage = new MemoryStorage();

Object.defineProperty(globalThis, "window", {
  value: { localStorage: storage, crypto: globalThis.crypto },
  writable: true,
  configurable: true,
});
Object.defineProperty(globalThis, "localStorage", {
  value: storage,
  writable: true,
  configurable: true,
});
