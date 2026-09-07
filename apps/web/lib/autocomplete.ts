/** A committed display label is not a new type-ahead query. */
export function shouldSearchAutocomplete(
  query: string,
  committedValue: string,
  minChars: number,
  controlled: boolean,
): boolean {
  const term = query.trim();
  if (term.length < minChars) return false;
  return !controlled || term !== committedValue.trim();
}
