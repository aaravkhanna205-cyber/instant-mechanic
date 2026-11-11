import { PortalShell } from "@/components/live/portal";
import { LiveProvider } from "@/lib/live/session";

export default function CandidateLayout({ children }: { children: React.ReactNode }) {
  return (
    <LiveProvider area="candidate">
      <PortalShell>{children}</PortalShell>
    </LiveProvider>
  );
}
