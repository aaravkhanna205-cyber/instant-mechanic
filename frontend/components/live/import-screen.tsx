"use client";
import { useLive } from "@/lib/live/session";
import { ImportWorkspace } from "./imports";
import { BackLink, NeedsOrganization, NeedsRecruiter, PageHeader } from "./ui";

export function ImportScreen({ kind }: { kind: "jobs" | "candidates" }) {
  const live = useLive();
  const jobs = kind === "jobs";
  const header = (
    <>
      <BackLink href={jobs ? "/jobs" : "/candidates"}>{jobs ? "All jobs" : "All candidates"}</BackLink>
      <PageHeader title={jobs ? "Import jobs" : "Import candidates"}
        subtitle={jobs ? "Add several vacancies from a spreadsheet. They are created as drafts." : "Add people you are already in touch with to a vacancy."} />
    </>
  );
  if (!live.orgId) return <>{header}<NeedsOrganization admin={live.admin} /></>;
  if (!live.recruiter) return <>{header}<NeedsRecruiter /></>;
  return <>{header}<ImportWorkspace kind={kind} /></>;
}
