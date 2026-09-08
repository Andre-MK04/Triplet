"use client";

import { FormEvent, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Notice } from "../../components/ui/Misc";
import { ApiError, apiPost } from "../../lib/api";
import { legalOperator, missingOperatorDetails } from "../../lib/legal";

const TOPICS = [
  { value: "general", label: "General question" },
  { value: "account", label: "Account help" },
  { value: "fare", label: "Fare or trip issue" },
  { value: "privacy", label: "Privacy request" },
  { value: "security", label: "Security report" },
  { value: "partnership", label: "Partnership" },
] as const;

type ContactState = "idle" | "sending" | "sent" | "error";

const fieldClass =
  "mt-2 w-full rounded-none border border-line bg-ink-raised px-3 py-3 text-sm text-cloud outline-none transition placeholder:text-mist-dim focus:border-mint focus:ring-1 focus:ring-mint";

export function ContactClient() {
  const missingOperator = missingOperatorDetails();
  const [state, setState] = useState<ContactState>("idle");
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // React only guarantees currentTarget while the event handler is actively
    // handling the event. Capture the form before awaiting the API; reading
    // event.currentTarget afterwards can yield null and turn a successful
    // delivery into the generic error state when reset() throws.
    const formElement = event.currentTarget;
    setState("sending");
    setError("");
    const form = new FormData(formElement);

    try {
      await apiPost<{ accepted: boolean }>("/contact", {
        name: form.get("name"),
        email: form.get("email"),
        topic: form.get("topic"),
        message: form.get("message"),
        website: form.get("website"),
      });
      formElement.reset();
      setState("sent");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "We could not send your message. Please try again.");
      setState("error");
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl py-8 sm:py-14">
        <div className="grid gap-12 lg:grid-cols-[minmax(0,0.75fr)_minmax(0,1.25fr)] lg:gap-20">
          <header>
            <p className="font-mono text-[11px] font-semibold uppercase tracking-label text-mint">
              Contact Farelin
            </p>
            <h1 className="mt-4 max-w-md font-display text-4xl font-bold tracking-tight text-cloud sm:text-5xl">
              Tell us what you need.
            </h1>
            <p className="mt-5 max-w-md text-base leading-relaxed text-mist">
              Ask about your account, report a fare that looks wrong, or raise a privacy or security concern.
              A person reads every message.
            </p>
            {missingOperator.length > 0 ? (
              <div className="mt-6 border-l-2 border-gold/50 pl-4 text-sm leading-relaxed text-mist">
                Farelin&apos;s legal operator details are not yet fully published. The form still
                reaches support, but this must be resolved before public commercial launch.
              </div>
            ) : (
              <address className="mt-6 text-sm not-italic leading-relaxed text-mist">
                Operated by <strong className="text-cloud">{legalOperator.name}</strong>
                <br />
                {legalOperator.address}
                <br />
                <a className="underline underline-offset-2 hover:text-mint" href={`mailto:${legalOperator.supportEmail}`}>
                  {legalOperator.supportEmail}
                </a>
              </address>
            )}
            <div className="mt-10 border-t border-line pt-6">
              <p className="font-mono text-[10px] uppercase tracking-label text-mist-dim">Before you send</p>
              <p className="mt-3 text-sm leading-relaxed text-mist">
                Farelin does not sell flights and cannot change, cancel, or refund a booking. For an existing
                booking, contact the airline or provider shown on your confirmation.
              </p>
            </div>
            <div className="mt-8 flex flex-wrap gap-3">
              <ButtonLink href="/security" variant="secondary" size="sm">Security</ButtonLink>
              <ButtonLink href="/privacy" variant="ghost" size="sm">Privacy policy</ButtonLink>
            </div>
          </header>

          <section aria-labelledby="contact-form-title" className="border-t border-line pt-6 lg:border-l lg:border-t-0 lg:pl-10 lg:pt-0">
            <h2 id="contact-form-title" className="font-display text-xl font-bold text-cloud">Send a message</h2>
            <p className="mt-2 text-sm text-mist">We use these details only to understand and reply to your request.</p>

            {state === "sent" ? (
              <div className="mt-8 space-y-6">
                <Notice tone="success">Your message was accepted by our email service. We’ll reply to the address you provided.</Notice>
                <Button type="button" variant="secondary" onClick={() => setState("idle")}>Send another message</Button>
              </div>
            ) : (
              <form onSubmit={submit} className="mt-8 space-y-6">
                <div>
                  <label htmlFor="contact-name" className="font-mono text-[10px] font-semibold uppercase tracking-label text-mist">Name</label>
                  <input id="contact-name" name="name" required maxLength={80} autoComplete="name" className={fieldClass} />
                </div>
                <div>
                  <label htmlFor="contact-email" className="font-mono text-[10px] font-semibold uppercase tracking-label text-mist">Email</label>
                  <input id="contact-email" name="email" type="email" required maxLength={254} autoComplete="email" className={fieldClass} />
                </div>
                <div>
                  <label htmlFor="contact-topic" className="font-mono text-[10px] font-semibold uppercase tracking-label text-mist">What is this about?</label>
                  <select id="contact-topic" name="topic" required defaultValue="general" className={fieldClass}>
                    {TOPICS.map((topic) => <option key={topic.value} value={topic.value}>{topic.label}</option>)}
                  </select>
                </div>
                <div>
                  <label htmlFor="contact-message" className="font-mono text-[10px] font-semibold uppercase tracking-label text-mist">Message</label>
                  <textarea id="contact-message" name="message" required minLength={20} maxLength={4000} rows={8} className={`${fieldClass} resize-y`} placeholder="Include the route, dates, or account detail that will help us understand the issue." />
                  <p className="mt-2 text-xs text-mist-dim">Do not include passwords, payment card details, or API keys.</p>
                </div>
                <div className="absolute -left-[10000px] top-auto h-px w-px overflow-hidden" aria-hidden="true">
                  <label htmlFor="contact-website">Website</label>
                  <input id="contact-website" name="website" tabIndex={-1} autoComplete="off" />
                </div>
                {state === "error" ? <Notice tone="error">{error}</Notice> : null}
                <Button type="submit" size="lg" disabled={state === "sending"}>
                  {state === "sending" ? "Sending…" : "Send message"}
                </Button>
              </form>
            )}
          </section>
        </div>
      </div>
    </AppShell>
  );
}
