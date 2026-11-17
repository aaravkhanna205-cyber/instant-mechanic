import { redirect } from "next/navigation";

// Agent message approvals are live on the Phase 6 page.
export default function Page() {
  redirect("/phase6");
}
