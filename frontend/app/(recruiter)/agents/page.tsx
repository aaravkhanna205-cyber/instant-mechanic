import { redirect } from "next/navigation";

// Phase 6 agents are live; this old placeholder address now opens them.
export default function Page() {
  redirect("/phase6/workflows");
}
