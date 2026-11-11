import { redirect } from "next/navigation";

/** Onboarding is handled by a platform administrator assigning roles. */
export default function Page() {
  redirect("/login");
}
