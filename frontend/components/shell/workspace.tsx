"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import {
  BrainCircuit, Briefcase, CalendarDays, ChartNoAxesColumn, LayoutDashboard, Menu, Moon,
  PanelLeftClose, PanelLeftOpen, Settings, ShieldCheck, Sun, UserRound, Users,
} from "lucide-react";
import { brand } from "@/lib/brand";
import { useLive } from "@/lib/live/session";
import { errorText } from "@/lib/api/phase3";

const WORK = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/jobs", label: "Jobs", icon: Briefcase },
  { href: "/candidates", label: "Candidates", icon: Users },
  { href: "/interviews", label: "Interviews", icon: CalendarDays },
  { href: "/analytics", label: "Analytics", icon: ChartNoAxesColumn },
];
const LATER = [
  { href: "/agents", label: "AI agents", icon: BrainCircuit },
  { href: "/approvals", label: "Approvals", icon: ShieldCheck },
];
const COLLAPSE_KEY = "im-sidebar-collapsed";

function isActive(path: string, href: string) {
  return path === href || path.startsWith(`${href}/`);
}

/** Recruiter and admin shell: sidebar, organization switcher and account menu. */
export function Workspace({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const live = useLive();
  const { theme, setTheme } = useTheme();
  const [collapsed, setCollapsed] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [logoutError, setLogoutError] = useState("");

  useEffect(() => {
    const stored = localStorage.getItem(COLLAPSE_KEY) === "true";
    queueMicrotask(() => setCollapsed(stored));
  }, []);
  const toggle = () =>
    setCollapsed((value) => {
      localStorage.setItem(COLLAPSE_KEY, String(!value));
      return !value;
    });

  const link = ({ href, label, icon: Icon }: (typeof WORK)[number], badge?: string) => (
    <Link key={href} href={href} title={label} onClick={() => setMobile(false)}
      aria-current={isActive(path, href) ? "page" : undefined}
      className={`navlink ${isActive(path, href) ? "active" : ""}`}>
      <Icon size={19} className="shrink-0" />
      {!collapsed && <span className="flex-1">{label}</span>}
      {!collapsed && badge && <span className="pill pill-grey">{badge}</span>}
    </Link>
  );
  const heading = (text: string) => (
    <div className="px-3 pt-5 pb-2 text-[10px] tracking-widest text-muted">{collapsed ? "···" : text}</div>
  );
  const section = path.split("/").filter(Boolean)[0] || "dashboard";

  return (
    <div className="shell">
      <div className={`overlay ${mobile ? "show" : ""}`} onClick={() => setMobile(false)} />
      <aside className={`sidebar ${collapsed ? "collapsed" : ""} ${mobile ? "mobile-open" : ""}`}>
        <div className="p-4 flex items-center gap-3 border-b border-[var(--border)]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={brand.logoPath} alt="" width={34} height={34} />
          {!collapsed && (
            <div className="min-w-0">
              <strong className="text-sm">Instant Mechanic</strong>
              <div className="text-xs text-muted">Hire · Workspace</div>
            </div>
          )}
        </div>
        <nav aria-label="Workspace" className="p-3 space-y-1 flex-1 overflow-y-auto">
          {heading("WORKSPACE")}
          {WORK.map((item) => link(item))}
          {heading("MANAGEMENT")}
          {live.admin && link({ href: "/admin", label: "Super Admin", icon: Settings })}
          {link({ href: "/portal", label: "Candidate portal", icon: UserRound })}
          {heading("LATER PHASES")}
          {LATER.map((item) => link(item, "Phase 6"))}
        </nav>
        <div className="p-3 border-t border-[var(--border)]">
          <button onClick={toggle} className="navlink w-full" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
            {collapsed ? <PanelLeftOpen size={19} /> : <PanelLeftClose size={19} />}
            {!collapsed && "Collapse sidebar"}
          </button>
        </div>
      </aside>

      <div className="maincol">
        <header className="header">
          <div className="flex gap-3 items-center min-w-0">
            <button className="btn mobile-menu" aria-label="Open navigation" onClick={() => setMobile(true)}>
              <Menu size={18} />
            </button>
            <div className="text-sm text-muted hide-mobile">
              Workspace <span className="mx-2">/</span>
              <strong className="text-[var(--text)] capitalize">{section}</strong>
            </div>
          </div>
          <div className="flex items-center gap-2 min-w-0">
            {live.organizations.length > 0 && (
              <select aria-label="Organization" className="control org-select" value={live.orgId}
                onChange={(event) => live.setOrgId(event.target.value)}>
                {live.organizations.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}
              </select>
            )}
            <button aria-label="Toggle dark mode" className="btn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <details className="menu">
              <summary className="btn" aria-label="Account menu">
                <UserRound size={18} />
                <span className="hide-mobile">{live.session.user.full_name}</span>
              </summary>
              <div className="panel menu-list">
                <div className="px-2.5 py-2 text-xs text-muted break-all">
                  {live.session.user.email}
                  <br />
                  {live.admin ? "Platform administrator" : "Organization member"}
                </div>
                <Link href="/auth-live/account">Account</Link>
                <button onClick={() => live.logout().catch((error) => setLogoutError(errorText(error)))}>Sign out</button>
              </div>
            </details>
          </div>
        </header>
        <main className="content">
          {logoutError && <div className="notice notice-error mb-4" role="alert">{logoutError}</div>}
          {children}
        </main>
      </div>
    </div>
  );
}
