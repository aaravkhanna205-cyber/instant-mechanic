import { AccountPage } from "@/components/live/auth";
import { LiveProvider } from "@/lib/live/session";

export default function Page() {
  return (
    <LiveProvider area="candidate">
      <AccountPage />
    </LiveProvider>
  );
}
