"use client";

import { StateBlock } from "@/components/Panel";

export default function ErrorPage({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="mx-auto max-w-lg pt-16">
      <StateBlock kind="error" title="This view could not load">
        The OrbiFlare API may be unreachable. Start it with <span className="font-mono">make backend-dev</span>, then retry.
        <div className="mt-1 font-mono text-[10px] text-base-500">{error.message.slice(0, 160)}</div>
        <button onClick={reset} className="mt-3 rounded border border-base-600 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-accent hover:border-accent/60">Retry</button>
      </StateBlock>
    </div>
  );
}
