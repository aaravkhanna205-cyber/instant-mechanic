import { redirect } from "next/navigation";

/** The live workspace now lives at the main addresses. */
export default function Page() {
  redirect("/dashboard");
}
