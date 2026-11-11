import { Workspace } from "@/components/shell/workspace";
import { LiveProvider } from "@/lib/live/session";

export default function RecruiterLayout({ children }: { children: React.ReactNode }) {
  return (
    <LiveProvider area="staff">
      <Workspace>{children}</Workspace>
    </LiveProvider>
  );
}
