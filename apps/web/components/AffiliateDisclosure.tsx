/**
 * Triplet earns commission on some booking links, and says so.
 *
 * Deliberately not rendered on every result card: a disclosure repeated beside
 * every price becomes furniture people stop reading. It belongs where someone
 * is deciding to follow a link or reading about how Triplet works.
 */
export function AffiliateDisclosure({ className = "" }: { className?: string }) {
  return (
    <p className={`text-xs leading-relaxed text-mist-dim ${className}`}>
      Triplet may earn a commission when you book through certain links, at no additional cost
      to you. Commission does not affect how Triplet ranks results.
    </p>
  );
}
