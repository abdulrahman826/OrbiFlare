"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import type { AgentResponse } from "@/types/domain";

interface Turn {
  role: "user" | "agent";
  text: string;
  response?: AgentResponse;
}

const SUGGESTIONS = [
  "list high risk events",
  "which events are escalating?",
  "what is the normal baseline for FAC-REF-ALPHA",
];

export function AgentPanel() {
  const [turns, setTurns] = useState<Turn[]>([
    {
      role: "agent",
      text: "I'm the OrbiFlare Fire Intelligence Agent -- read-only, and I only answer from real computed data. Ask me about an event (e.g. an EVT-... id), a facility (FAC-... id), or say \"list high risk events\".",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(message: string) {
    if (!message.trim() || busy) return;
    setTurns((t) => [...t, { role: "user", text: message }]);
    setInput("");
    setBusy(true);
    try {
      const res = await api.agentQuery(message);
      setTurns((t) => [...t, { role: "agent", text: res.text, response: res }]);
    } catch {
      setTurns((t) => [...t, { role: "agent", text: "Sorry, I couldn't reach the intelligence layer just now." }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-3 overflow-y-auto scrollbar-thin px-1 py-2">
        {turns.map((t, i) => (
          <div key={i} className={t.role === "user" ? "flex justify-end" : "flex justify-start"}>
            <div className={`max-w-[85%] rounded-md px-3 py-2 text-sm leading-relaxed ${t.role === "user" ? "bg-accent/15 text-accent-bright" : "bg-base-800 text-base-200"}`}>
              <p>{t.text}</p>
              {t.response?.result_cards.map((c, ci) => (
                <div key={ci} className="mt-2 rounded border border-base-600 bg-base-850 p-2 text-xs">
                  <div className="font-mono font-semibold text-base-100">{c.title}</div>
                  {c.subtitle && <div className="text-base-400">{c.subtitle}</div>}
                </div>
              ))}
              {t.response?.ui_action?.action === "open_investigation" && t.response.ui_action.target_id && (
                <Link href={`/investigation/${t.response.ui_action.target_id}`} className="mt-2 inline-block text-xs font-medium text-accent hover:underline">
                  Open investigation &rarr;
                </Link>
              )}
              {t.response?.ui_action?.action === "open_facility" && t.response.ui_action.target_id && (
                <Link href={`/facilities/${t.response.ui_action.target_id}`} className="mt-2 inline-block text-xs font-medium text-accent hover:underline">
                  Open facility &rarr;
                </Link>
              )}
            </div>
          </div>
        ))}
        {busy && <div className="text-xs text-base-500">Thinking...</div>}
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button key={s} onClick={() => send(s)} className="rounded border border-base-600 px-2 py-1 text-[11px] text-base-300 hover:border-accent/50 hover:text-accent">
            {s}
          </button>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="mt-2 flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about an event, facility, or risk trend..."
          className="flex-1 rounded border border-base-600 bg-base-800 px-3 py-2 text-sm text-base-100 focus:border-accent focus:outline-none"
        />
        <button type="submit" disabled={busy} className="rounded bg-accent px-4 py-2 text-sm font-medium text-base-950 disabled:opacity-50">
          Send
        </button>
      </form>
    </div>
  );
}
