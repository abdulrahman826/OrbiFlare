import Link from "next/link";
import { StateBlock } from "@/components/Panel";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md pt-16">
      <StateBlock kind="unavailable" title="Not found">
        That event, facility or page does not exist in the current data set.
        <div className="mt-3 flex justify-center gap-4 text-[11px] font-semibold uppercase tracking-wider">
          <Link href="/command-center" className="text-accent hover:text-accent-bright">Command Center</Link>
          <Link href="/events" className="text-accent hover:text-accent-bright">Events</Link>
        </div>
      </StateBlock>
    </div>
  );
}
