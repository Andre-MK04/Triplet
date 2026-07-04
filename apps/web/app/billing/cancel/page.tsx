"use client";

export default function BillingCancelPage() {
  return (
    <main className="min-h-screen px-5 py-8 sm:px-8 lg:px-12">
      <section className="mx-auto max-w-2xl rounded-lg border border-line bg-panel/90 p-6">
        <a className="text-sm font-semibold uppercase tracking-[0.22em] text-mint" href="/">
          TRIPLET
        </a>
        <h1 className="mt-6 text-3xl font-semibold text-white">Checkout canceled</h1>
        <p className="mt-3 text-slate-300">No changes were made to your plan.</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <a className="rounded-md bg-mint px-4 py-3 font-semibold text-ink" href="/pricing">Back to pricing</a>
          <a className="rounded-md border border-line px-4 py-3 font-semibold text-white hover:border-mint" href="/">Search trips</a>
        </div>
      </section>
    </main>
  );
}
