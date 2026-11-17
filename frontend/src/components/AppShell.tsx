"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";
import { BriefcaseBusiness, FolderOpen, LucideIcon } from "lucide-react";
import { AccountControl } from "@/components/AuthGate";
import { ThemeToggle } from "@/components/ThemeToggle";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Extra path prefixes that keep this item highlighted. */
  matches: string[];
}

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Proyek", icon: FolderOpen, matches: ["/jobs"] },
  { href: "/campaigns", label: "Campaign", icon: BriefcaseBusiness, matches: ["/campaigns"] },
];

function isActive(item: NavItem, pathname: string) {
  if (item.href === "/") return pathname === "/" || item.matches.some((prefix) => pathname.startsWith(prefix));
  return item.matches.some((prefix) => pathname.startsWith(prefix));
}

/**
 * Persistent workspace shell: a left rail on desktop (icon-only on the editor
 * route so the preview keeps its space) and a compact top bar on small screens.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "/";
  const compact = pathname.startsWith("/jobs");

  return (
    <div className="clipgen-app min-h-screen">
      <aside
        className={`fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-line bg-surface lg:flex ${compact ? "w-[4.5rem]" : "w-60"}`}
        aria-label="Navigasi utama"
      >
        <Brand compact={compact} />
        <nav className="mt-2 flex-1 space-y-1 px-3" aria-label="Menu">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.href} item={item} active={isActive(item, pathname)} compact={compact} />
          ))}
        </nav>
        <div className={`space-y-2 p-3 ${compact ? "[&_.shell-label]:hidden" : ""}`}>
          <AccountControl />
          <ThemeToggle className="w-full" />
        </div>
      </aside>

      <header className="sticky top-0 z-30 flex items-center gap-2 border-b border-line bg-surface/95 px-4 py-2 backdrop-blur lg:hidden">
        <Brand compact inline />
        <nav className="ml-2 flex flex-1 items-center gap-1" aria-label="Menu">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.href} item={item} active={isActive(item, pathname)} compact={false} small />
          ))}
        </nav>
        <ThemeToggle className="[&_.shell-label]:hidden" />
      </header>

      <main className={compact ? "lg:pl-[4.5rem]" : "lg:pl-60"}>
        <div className="mx-auto max-w-[1400px] px-4 py-6 sm:px-8 sm:py-8">{children}</div>
      </main>
    </div>
  );
}

function Brand({ compact, inline = false }: { compact: boolean; inline?: boolean }) {
  return (
    <Link href="/" className={`flex items-center gap-3 ${inline ? "" : "px-4 py-5"}`} aria-label="ClipGen, ke halaman proyek">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand to-accent text-sm font-bold tracking-tight text-white">
        CG
      </span>
      {!compact && (
        <span className="leading-tight">
          <span className="block text-sm font-semibold text-ink">ClipGen</span>
          <span className="block text-xs text-ink-subtle">Campaign clipping</span>
        </span>
      )}
    </Link>
  );
}

function NavLink({ item, active, compact, small = false }: { item: NavItem; active: boolean; compact: boolean; small?: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      title={compact ? item.label : undefined}
      className={`flex items-center gap-3 rounded-lg text-sm font-medium transition-colors duration-150 ${
        small ? "min-h-10 px-3" : "min-h-11 px-3"
      } ${compact ? "justify-center" : ""} ${
        active
          ? "bg-brand/15 text-brand-soft"
          : "text-ink-muted hover:bg-elevated hover:text-ink"
      }`}
    >
      <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden />
      {!compact && <span>{item.label}</span>}
    </Link>
  );
}
