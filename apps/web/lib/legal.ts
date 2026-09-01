/**
 * Who legally operates Triplet.
 *
 * Every value here is read from configuration and every one may be absent.
 * Nothing in this file invents an operator name, company number, VAT number or
 * address: publishing a registration that does not exist is worse than
 * publishing none, and a placeholder has a way of surviving to production.
 *
 * These are NEXT_PUBLIC_ by design. Legal operator details are meant to be
 * read by anyone using the service — they are the opposite of a secret.
 */

function configured(value: string | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

export const legalOperator = {
  /** Trading or company name, e.g. "Triplet Labs OÜ". */
  name: configured(process.env.NEXT_PUBLIC_LEGAL_OPERATOR_NAME),
  /** Where users reach a human about the service. */
  supportEmail: configured(process.env.NEXT_PUBLIC_LEGAL_SUPPORT_EMAIL),
  /** Registered business address, as one line or newline-separated. */
  address: configured(process.env.NEXT_PUBLIC_LEGAL_ADDRESS),
  /** Company registration number. */
  registrationNumber: configured(process.env.NEXT_PUBLIC_LEGAL_REGISTRATION_NUMBER),
  /** VAT identifier, where the operator is VAT registered. */
  vatNumber: configured(process.env.NEXT_PUBLIC_LEGAL_VAT_NUMBER),
} as const;

export type LegalOperator = typeof legalOperator;

/** The details a published Terms page is normally expected to carry. */
export const REQUIRED_FOR_PUBLICATION = ["name", "supportEmail", "address"] as const;

export function missingOperatorDetails(): string[] {
  return REQUIRED_FOR_PUBLICATION.filter((key) => legalOperator[key] === null);
}

/** True when there is enough to identify who is behind the service. */
export function hasOperatorIdentity(): boolean {
  return legalOperator.name !== null || legalOperator.supportEmail !== null;
}
