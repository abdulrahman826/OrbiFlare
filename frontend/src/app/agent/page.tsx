import { AgentPanel } from "@/components/AgentPanel";
import { Panel } from "@/components/Panel";

export default function AgentPage() {
  return (
    <div className="flex h-[calc(100vh-140px)] flex-col space-y-3">
      <div>
        <h1 className="text-lg font-semibold text-base-100">Fire Intelligence Agent</h1>
        <p className="text-sm text-base-400">Read-only analyst assistant. It only retrieves and explains real computed data -- it cannot mutate state, run arbitrary queries, or fabricate results.</p>
      </div>
      <Panel className="flex-1 overflow-hidden">
        <AgentPanel />
      </Panel>
    </div>
  );
}
