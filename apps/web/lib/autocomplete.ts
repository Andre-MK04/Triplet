/** A committed display label is not a new type-ahead query. */
export function shouldSearchAutocomplete(
  query: string,
  committedValue: string,
  minChars: number,
  hasCommittedSelection: boolean,
): boolean {
  const term = query.trim();
  if (term.length < minChars) return false;
  return !hasCommittedSelection || term !== committedValue.trim();
}
