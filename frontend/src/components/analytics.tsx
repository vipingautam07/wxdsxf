import type { ReactNode } from "react";
import {
  AlertCircle,
  ArrowUpRight,
  Check,
  Info,
  RotateCcw,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { Coverage, Meta } from "@/api/types";
import { number, stamp } from "@/lib/format";

export function Panel({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={`gap-0 border-[#dfe7e4] py-0 shadow-none ${className}`}>
      <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5 pb-3">
        <div>
          <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>
          {subtitle && (
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {subtitle}
            </p>
          )}
        </div>
        {action}
      </div>
      <CardContent className="min-w-0 px-5 pb-5">{children}</CardContent>
    </Card>
  );
}
export function MetricCard({
  label,
  value,
  unit,
  note,
  icon,
  tone,
}: {
  label: string;
  value: string;
  unit?: string;
  note: string;
  icon?: ReactNode;
  tone?: "green" | "amber";
}) {
  return (
    <Card className="gap-0 border-[#dfe7e4] py-0 shadow-none">
      <CardContent className="px-5 py-5">
        <div className="flex items-center justify-between text-[12px] font-medium text-muted-foreground">
          {label}
          <span className="text-[#91a5a0]">{icon}</span>
        </div>
        <div
          className={`tabular mt-3 text-[30px] font-semibold leading-tight tracking-[-.045em] ${tone === "amber" ? "text-[#a36726]" : tone === "green" ? "text-primary" : ""}`}
        >
          {value}
          <span className="ml-1.5 text-xs font-normal tracking-normal text-muted-foreground">
            {unit}
          </span>
        </div>
        <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
          {note}
        </p>
      </CardContent>
    </Card>
  );
}
export function CoverageBadge({ coverage }: { coverage: Coverage }) {
  const complete = coverage.matched_hours === coverage.expected_hours;
  return (
    <Badge
      variant="outline"
      className={
        complete
          ? "border-[#cce6d7] bg-[#edf7ef] text-[#306b4c]"
          : "border-amber-200 bg-amber-50 text-amber-800"
      }
    >
      {complete ? <Check size={12} /> : <AlertCircle size={12} />}
      {number(coverage.matched_hours)} / {number(coverage.expected_hours)} hours
      matched
    </Badge>
  );
}
export function LoadingState() {
  return (
    <div role="status" aria-label="Loading analysis" className="space-y-5">
      <span className="sr-only">Loading analysis</span>
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-36 rounded-xl bg-[#e3ebe7]" />
        ))}
      </div>
      <Skeleton className="h-[400px] rounded-xl bg-[#e3ebe7]" />
    </div>
  );
}
export function ErrorState({
  message,
  retry,
}: {
  message: string;
  retry: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-red-200 bg-white p-8 text-center"
    >
      <AlertCircle className="mx-auto mb-3 text-red-700" size={28} />
      <h2 className="font-semibold">Analysis unavailable</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
        {message}
      </p>
      <Button onClick={retry} className="mt-5">
        <RotateCcw size={14} />
        Try again
      </Button>
      <p className="mt-3 text-xs text-muted-foreground">
        No substitute data or estimated metrics are displayed.
      </p>
    </div>
  );
}
export function EmptyState({
  message = "No matched observations are available for these filters.",
}: {
  message?: string;
}) {
  return (
    <p
      role="status"
      className="flex min-h-32 items-center justify-center rounded-lg bg-[#f5f7f5] p-6 text-center text-sm text-muted-foreground"
    >
      {message}
    </p>
  );
}
export function SourceFooter({ meta }: { meta: Meta }) {
  return (
    <div className="mt-7 flex flex-wrap items-center justify-between gap-3 border-t border-[#dfe7e4] pt-4 text-[11px] text-muted-foreground">
      <span>
        Elexon Insights · FUELHH + WINDFOR · Captured{" "}
        {stamp(meta.data_retrieved_at)}
      </span>
      <a
        className="flex items-center gap-1 hover:text-primary"
        href="https://bmrs.elexon.co.uk/wind-generation"
        target="_blank"
        rel="noreferrer"
      >
        Official source <ArrowUpRight size={12} />
      </a>
    </div>
  );
}
export function MethodNote({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2.5 rounded-lg border border-[#dee8e3] bg-[#edf3ef] px-4 py-3 text-[11px] leading-relaxed text-[#586d66]">
      <Info size={14} className="mt-0.5 shrink-0" />
      <div>{children}</div>
    </div>
  );
}
export function Legend({ revision = false }: { revision?: boolean }) {
  return (
    <div className="flex flex-wrap gap-4 text-[11px] text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <i className="inline-block w-5 border-t-2 border-[#198469]" />
        {revision ? "Published forecast" : "Forecast at cutoff"}
      </span>
      <span className="flex items-center gap-1.5">
        <i className="inline-block w-5 border-t-2 border-dashed border-[#8572ad]" />
        Retrospective actual
      </span>
    </div>
  );
}
