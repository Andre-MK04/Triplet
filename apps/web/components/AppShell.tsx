"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { useAuth } from "./AuthContext";
import { Button, ButtonLink } from "./ui/Button";

const navLinks = [
  { href: "/discover", label: "Discover" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/pricing", label: "Pricing" },
];

export function Navbar() {
  const pathname = usePathname();
  const { user, isLoading, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40">
      <div className="glass mx-auto mt-3 flex max-w-6xl items-center justify-between rounded-2xl px-4 py-2.5 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-display text-lg font-bold text-cloud">
          <TripletMark />
          Triplet
        </Link>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={
                "rounded-full px-4 py-2 text-sm font-medium transition " +
                (pathname?.startsWith(link.href)
                  ? "bg-white/10 text-cloud"
                  : "text-mist hover:bg-white/5 hover:text-cloud")
              }
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          {isLoading ? null : user ? (
            <>
              <Link
                href="/account"
                className="max-w-40 truncate rounded-full px-3 py-2 text-sm text-mist transition hover:bg-white/5 hover:text-cloud"
                title={user.email}
              >
                {user.displayName || user.email}
              </Link>
              <Button variant="secondary" size="sm" onClick={() => void logout()}>
                Log out
              </Button>
            </>
          ) : (
            <>
              <ButtonLink href="/login" variant="ghost" size="sm">
                Log in
              </ButtonLink>
              <ButtonLink href="/signup" variant="primary" size="sm">
                Create my travel profile
              </ButtonLink>
            </>
          )}
        </div>

        <button
          type="button"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
          className="rounded-lg p-2 text-cloud md:hidden"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            {menuOpen ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
          </svg>
        </button>
      </div>

      {menuOpen ? (
        <div className="glass mx-auto mt-1 max-w-6xl rounded-2xl p-3 md:hidden">
          <nav className="flex flex-col gap-1" aria-label="Mobile">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMenuOpen(false)}
                className="rounded-xl px-4 py-3 text-sm font-medium text-cloud hover:bg-white/5"
              >
                {link.label}
              </Link>
            ))}
            <div className="mt-2 flex flex-col gap-2 border-t border-line pt-3">
              {user ? (
                <>
                  <Link href="/account" onClick={() => setMenuOpen(false)} className="rounded-xl px-4 py-3 text-sm text-mist hover:bg-white/5">
                    Account — {user.email}
                  </Link>
                  <Button variant="secondary" onClick={() => void logout()}>
                    Log out
                  </Button>
                </>
              ) : (
                <>
                  <ButtonLink href="/login" variant="secondary">
                    Log in
                  </ButtonLink>
                  <ButtonLink href="/signup">Create my travel profile</ButtonLink>
                </>
              )}
            </div>
          </nav>
        </div>
      ) : null}
    </header>
  );
}

export function TripletMark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
      <circle cx="16" cy="16" r="14" stroke="url(#tg)" strokeWidth="2" />
      <path d="M7 20c4-8 14-11 18-8" stroke="url(#tg)" strokeWidth="2" strokeLinecap="round" strokeDasharray="3 3" />
      <circle cx="8" cy="19" r="2.4" fill="#7ddfc3" />
      <circle cx="24" cy="12" r="2.4" fill="#ff9a78" />
      <defs>
        <linearGradient id="tg" x1="0" y1="32" x2="32" y2="0">
          <stop offset="0%" stopColor="#7ddfc3" />
          <stop offset="100%" stopColor="#8ec5ff" />
        </linearGradient>
      </defs>
    </svg>
  );
}

export function Footer() {
  return (
    <footer className="mt-24 border-t border-line">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 sm:px-6 md:flex-row md:items-start md:justify-between">
        <div className="max-w-sm">
          <p className="flex items-center gap-2 font-display text-base font-bold text-cloud">
            <TripletMark size={20} /> Triplet
          </p>
          <p className="mt-2 text-sm text-mist">
            Find cheap trips, not just cheap flights. Prices are observed at check time and can change —
            always confirm the final fare with the provider.
          </p>
        </div>
        <nav className="grid grid-cols-2 gap-x-12 gap-y-2 text-sm" aria-label="Footer">
          <Link href="/discover" className="text-mist hover:text-cloud">Discover</Link>
          <Link href="/pricing" className="text-mist hover:text-cloud">Pricing</Link>
          <Link href="/dashboard" className="text-mist hover:text-cloud">Dashboard</Link>
          <Link href="/security" className="text-mist hover:text-cloud">Security & privacy</Link>
          <Link href="/onboarding" className="text-mist hover:text-cloud">Travel profile</Link>
          <Link href="/account" className="text-mist hover:text-cloud">Account</Link>
        </nav>
      </div>
      <p className="pb-8 text-center text-xs text-mist/60">
        © {new Date().getFullYear()} Triplet. Triplet does not sell or book flights.
      </p>
    </footer>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col px-3 sm:px-4">
      <Navbar />
      <main className="mx-auto w-full max-w-6xl flex-1 pt-8">{children}</main>
      <Footer />
    </div>
  );
}
