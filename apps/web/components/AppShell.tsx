"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { useAuth } from "./AuthContext";
import { ThemeToggle } from "./ThemeToggle";
import { Button, ButtonLink } from "./ui/Button";

const navLinks = [
  { href: "/discover", label: "Discover" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/pricing", label: "Pricing" },
];

function NavLink({ href, label, active, onClick }: { href: string; label: string; active: boolean; onClick?: () => void }) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className={
        "border-b-2 pb-1 font-mono text-[11px] font-semibold uppercase tracking-label transition-colors " +
        (active ? "border-mint text-mint" : "border-transparent text-mist hover:text-cloud")
      }
    >
      {label}
    </Link>
  );
}

export function Navbar() {
  const pathname = usePathname();
  const { user, isLoading, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-ink/90">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-display text-lg font-bold text-cloud">
          <TripletMark />
          Triplet
        </Link>

        <nav className="hidden items-center gap-7 md:flex" aria-label="Main">
          {navLinks.map((link) => (
            <NavLink key={link.href} {...link} active={pathname?.startsWith(link.href) ?? false} />
          ))}
        </nav>

        <div className="hidden items-center gap-5 md:flex">
          <ThemeToggle />
          {isLoading ? null : user ? (
            <>
              <Link
                href="/account"
                className="max-w-40 truncate font-mono text-[11px] uppercase tracking-label text-mist transition-colors hover:text-cloud"
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
                Get started
              </ButtonLink>
            </>
          )}
        </div>

        <div className="flex items-center gap-3 md:hidden">
          <ThemeToggle />
          <button
            type="button"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
            className="p-2 text-cloud"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {menuOpen ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
            </svg>
          </button>
        </div>
      </div>

      {menuOpen ? (
        <div className="border-t border-line bg-ink px-4 pb-5 pt-3 md:hidden">
          <nav className="flex flex-col gap-4" aria-label="Mobile">
            {navLinks.map((link) => (
              <NavLink
                key={link.href}
                {...link}
                active={pathname?.startsWith(link.href) ?? false}
                onClick={() => setMenuOpen(false)}
              />
            ))}
            <div className="mt-2 flex flex-col gap-2 border-t border-line pt-4">
              {user ? (
                <>
                  <Link
                    href="/account"
                    onClick={() => setMenuOpen(false)}
                    className="font-mono text-[11px] uppercase tracking-label text-mist hover:text-cloud"
                  >
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
                  <ButtonLink href="/signup">Get started</ButtonLink>
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
      <circle cx="16" cy="16" r="14" stroke="#7ddfc3" strokeWidth="2" />
      <path d="M7 20c4-8 14-11 18-8" stroke="#7ddfc3" strokeWidth="2" strokeLinecap="round" strokeDasharray="3 3" />
      <circle cx="8" cy="19" r="2.4" fill="#7ddfc3" />
      <circle cx="24" cy="12" r="2.4" fill="#ff9a78" />
    </svg>
  );
}

const footerGroups = [
  {
    label: "Product",
    links: [
      { href: "/discover", label: "Discover" },
      { href: "/dashboard", label: "Dashboard" },
      { href: "/pricing", label: "Pricing" },
    ],
  },
  {
    label: "Account",
    links: [
      { href: "/onboarding", label: "Travel profile" },
      { href: "/account", label: "Account" },
    ],
  },
  {
    label: "Protocol",
    links: [
      { href: "/privacy", label: "EU privacy" },
      { href: "/security", label: "Security" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="mt-24 border-t border-line">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-[minmax(0,5fr)_repeat(3,minmax(0,2fr))]">
        <div className="max-w-xs">
          <p className="flex items-center gap-2 font-display text-base font-bold text-cloud">
            <TripletMark size={20} /> Triplet
          </p>
          <p className="mt-3 text-sm leading-relaxed text-mist">
            Find cheap trips, not just cheap flights. Prices are observed at check time and can change —
            always confirm the final fare with the provider.
          </p>
          <p className="mt-4 font-mono text-[10px] uppercase tracking-label text-mist/70">
            Your data lives in the EU.
          </p>
        </div>
        {footerGroups.map((group) => (
          <nav key={group.label} aria-label={group.label} className="flex flex-col gap-2.5">
            <span className="mb-1 font-mono text-[11px] font-semibold uppercase tracking-label text-cloud">
              {group.label}
            </span>
            {group.links.map((link) => (
              <Link key={link.href} href={link.href} className="font-mono text-xs text-mist transition-colors hover:text-mint">
                {link.label}
              </Link>
            ))}
          </nav>
        ))}
      </div>
      <div className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-5 font-mono text-[10px] uppercase tracking-label text-mist/60 sm:px-6">
          <span>© {new Date().getFullYear()} Triplet — does not sell or book flights</span>
          <span className="inline-flex items-center gap-2">
            <span className="h-1.5 w-1.5 bg-mint" aria-hidden />
            Systems nominal
          </span>
        </div>
      </div>
    </footer>
  );
}

export function AppShell({ children, wide = false }: { children: React.ReactNode; wide?: boolean }) {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className={"w-full flex-1 " + (wide ? "" : "mx-auto max-w-6xl px-4 pt-8 sm:px-6")}>{children}</main>
      <Footer />
    </div>
  );
}
