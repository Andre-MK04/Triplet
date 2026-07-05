"use client";

import { useEffect, useState } from "react";

import { AppShell } from "../../../components/AppShell";
import { Badge } from "../../../components/ui/Badge";
import { Button } from "../../../components/ui/Button";
import { Card } from "../../../components/ui/Card";
import { EmptyState, Notice, Spinner } from "../../../components/ui/Misc";
import { ApiError, apiGet } from "../../../lib/api";
import type { ProviderStatusEntry, ProvidersStatusResponse } from "../../../lib/types";

const ACCESS_TONES: Record<ProviderStatusEntry["accessStatus"], "mint" | "gold" | "coral" | "neutral"> = {
  available: "mint",
  requires_approval: "gold",
  not_configured: "neutral",
  disabled: "coral",
};

type SmokeResult = {
  result: {
    provider: string;
    ok: boolean;
    apiOk: boolean;
    mappedFlightsCount: number;
    warnings: string[];
  };
  overallStatus: string;
};

export default function ProviderStatusPage() {
  const [data, setData] = useState<ProvidersStatusResponse | null>(null);
  const [error, setError] = useState("");
  const [smoke, setSmoke] = useState<Record<string, SmokeResult | "running">>({});

  useEffect(() => {
    apiGet<ProvidersStatusResponse>("/providers/status")
      .then(setData)
      .catch((loadError) => {
        setError(
          loadError instanceof ApiError && loadError.status === 404
            ? "Provider diagnostics are disabled (ENABLE_DEV_TOOL_ENDPOINTS=false). This page is development-only."
            : "Could not load provider status. Is the API running?",
        );
      });
  }, []);

  async function runSmokeTest(provider: string) {
    setSmoke((current) => ({ ...current, [provider]: "running" }));
    try {
      const result = await apiGet<SmokeResult>(`/providers/smoke-test?provider=${provider}`);
      setSmoke((current) => ({ ...current, [provider]: result }));
    } catch (smokeError) {
      setSmoke((current) => {
        const next = { ...current };
        delete next[provider];
        return next;
      });
      setError(smokeError instanceof Error ? smokeError.message : "Smoke test failed.");
    }
  }

  return (
    <AppShell>
      <div className="space-y-6 pb-10">
        <header>
          <h1 className="font-display text-3xl font-bold text-cloud">Provider status</h1>
          <p className="mt-1 text-mist">
            Development-only diagnostics. No secrets are shown here — only configuration state and counts.
          </p>
        </header>

        {error ? <Notice tone="warning">{error}</Notice> : null}

        {!data && !error ? <div className="flex justify-center py-16"><Spinner /></div> : null}

        {data ? (
          <>
            <div className="flex flex-wrap gap-2">
              <Badge tone="sky">FLIGHT_PROVIDER = {data.configuredProvider}</Badge>
              <Badge tone="sky">LIVE_FLIGHT_PROVIDER = {data.liveProvider}</Badge>
              <Badge tone={data.database.available ? "mint" : "coral"}>
                database {data.database.available ? `ok · ${data.database.cachedFlightsCount} cached flights` : "unavailable"}
              </Badge>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {data.providers.map((provider) => {
                const smokeState = smoke[provider.name];
                return (
                  <Card key={provider.name}>
                    <div className="flex items-start justify-between gap-3">
                      <h2 className="font-display text-lg font-bold text-cloud">{provider.name}</h2>
                      <Badge tone={ACCESS_TONES[provider.accessStatus]}>{provider.accessStatus.replace("_", " ")}</Badge>
                    </div>
                    <p className="mt-1 text-xs text-mist/70">{provider.implementationStatus.replace("_", " ")}</p>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {Object.entries(provider.capabilities)
                        .filter(([, enabled]) => enabled)
                        .map(([capability]) => (
                          <Badge key={capability}>{capability}</Badge>
                        ))}
                    </div>
                    {provider.rateLimitNotes ? (
                      <p className="mt-3 text-xs text-mist">{provider.rateLimitNotes}</p>
                    ) : null}
                    {provider.warnings.length > 0 ? (
                      <ul className="mt-3 space-y-1 text-xs text-gold">
                        {provider.warnings.map((warning) => (
                          <li key={warning}>⚠️ {warning}</li>
                        ))}
                      </ul>
                    ) : null}
                    <div className="mt-4 flex items-center gap-3 border-t border-dashed border-line pt-3">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => void runSmokeTest(provider.name)}
                        disabled={smokeState === "running"}
                      >
                        {smokeState === "running" ? "Running…" : "Run smoke test"}
                      </Button>
                      {smokeState && smokeState !== "running" ? (
                        <span className={`text-xs ${smokeState.result.ok ? "text-mint" : "text-gold"}`}>
                          {smokeState.result.ok
                            ? `ok · ${smokeState.result.mappedFlightsCount} flights mapped`
                            : smokeState.result.warnings[0] ?? "not ok"}
                        </span>
                      ) : null}
                    </div>
                  </Card>
                );
              })}
            </div>
          </>
        ) : null}

        {error && !data ? (
          <EmptyState icon="🛠" title="Diagnostics unavailable">
            Start the API with <code className="text-mint">ENABLE_DEV_TOOL_ENDPOINTS=true</code> (local
            development only) to see provider status here.
          </EmptyState>
        ) : null}
      </div>
    </AppShell>
  );
}
