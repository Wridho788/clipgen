import Link from "next/link";
import { ReactNode } from "react";
import { ArrowLeft } from "lucide-react";

export function CampaignPageHeader({
  backHref,
  backLabel,
  title,
  description,
  actions,
}: {
  backHref: string;
  backLabel: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="space-y-4">
      <Link
        href={backHref}
        className="inline-flex min-h-10 items-center gap-2 text-sm font-medium text-ink-muted transition-colors hover:text-ink"
      >
        <ArrowLeft className="h-4 w-4" />
        {backLabel}
      </Link>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="cg-eyebrow">Campaign</p>
          <h1 className="mt-1 break-words text-2xl font-semibold text-ink sm:text-3xl">{title}</h1>
          {description && <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted">{description}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {actions}
        </div>
      </div>
    </header>
  );
}
