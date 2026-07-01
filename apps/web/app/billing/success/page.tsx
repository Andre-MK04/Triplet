"use client";

export default function BillingSuccessPage() {
  return (
    <main className="min-h-screen px-5 py-8 sm:px-8 lg:px-12">
      <section className="mx-auto max-w-2xl rounded-lg border border-line bg-panel/90 p-6">
        <a className="text-sm font-semibold uppercase tracking-[0.22em] text-mint" href="/">
          TRIPLET
        </a>
        <h1 className="mt-6 text-3xl font-semibold text-white">Checkout complete</h1>
        <p className="mt-3 text-slate-300">
          Your subscription status will update after Stripe sends the confirmation webhook.
        </p>
        <a className="mt-6 inline-block rounded-md bg-mint px-4 py-3 font-semibold text-ink" href="/dashboard">
          Open dashboard
        </a>
      </section>
    </main>
  );
}
