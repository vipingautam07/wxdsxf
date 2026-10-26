import { ArrowRight, Clock3, Gauge, TrendingUp, Wind } from "lucide-react";
import { Link } from "react-router-dom";
import { endpoint, useApi } from "@/api/client";
import type { DayResponse } from "@/api/types";
import { clock, dateLabel, number, signed, stamp } from "@/lib/format";
import {
  CoverageBadge,
  ErrorState,
  LoadingState,
  MethodNote,
  MetricCard,
  Panel,
  SourceFooter,
} from "@/components/analytics";
import { GenerationChart } from "@/components/charts";
import { Button } from "@/components/ui/button";

export function Dashboard({
  decision,
  cutoff,
  setDecision,
  search,
}: {
  decision: string;
  cutoff: string;
  setDecision: (date: string) => void;
  search: string;
}) {
  const { data, loading, error, retry } = useApi<DayResponse>(
    endpoint("/day", { date: decision, cutoff }),
  );
  if (loading) return <LoadingState />;
  if (error || !data)
    return (
      <ErrorState message={error || "No response received."} retry={retry} />
    );
  const { summary, historical_reliability: history } = data;
  const publication =
    data.selected_publication_from === data.selected_publication_to
      ? stamp(data.selected_publication_from)
      : `${stamp(data.selected_publication_from)} – ${stamp(data.selected_publication_to)}`;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-[#dfe7e4] bg-white px-5 py-4">
        <div className="flex flex-wrap items-center gap-5">
          <label className="flex items-center gap-3 text-xs font-medium">
            Decision date
            <input
              aria-label="Decision date"
              type="date"
              min="2026-01-01"
              max="2026-01-31"
              value={decision}
              onChange={(e) => e.target.value && setDecision(e.target.value)}
            />
          </label>
          <ArrowRight size={16} className="text-[#a2b1ac]" />
          <div>
            <div className="eyebrow">Following-day delivery</div>
            <div className="mt-1 text-sm font-semibold">
              {dateLabel(summary.delivery_date)}
            </div>
          </div>
        </div>
        <CoverageBadge coverage={summary.coverage} />
      </div>
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <MetricCard
          label="Day-ahead forecast"
          value={number(summary.forecast_mean_mw)}
          unit="MW"
          note="Mean hourly forecast available at cutoff"
          icon={<Wind size={16} />}
          tone="green"
        />
        <MetricCard
          label="Actual generation"
          value={number(summary.actual_mean_mw)}
          unit="MW"
          note="Retrospective · mean reported outturn"
          icon={<Gauge size={16} />}
        />
        <MetricCard
          label="Average forecast error"
          value={signed(summary.metrics.mean_bias_mw)}
          unit="MW"
          note="Forecast − actual · positive = overforecast"
          icon={<TrendingUp size={16} />}
          tone="amber"
        />
        <MetricCard
          label="Prior forecast reliability"
          value={number(history.metrics.mae_mw)}
          unit="MW MAE"
          note={
            history.metrics.matched_hours
              ? `${number(history.metrics.matched_hours)} prior hours observed by this cutoff`
              : "No earlier observed deliveries in this snapshot"
          }
          icon={<Clock3 size={16} />}
        />
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_290px]">
        <Panel
          title="Wind generation outlook"
          subtitle={`${dateLabel(summary.delivery_date)} · 00:00–24:00 GMT · hourly evaluation`}
          action={
            <span className="rounded-md bg-[#f0f4f2] px-2.5 py-1 text-[10px] font-medium text-[#637872]">
              DAY AHEAD
            </span>
          }
        >
          <GenerationChart hours={data.hours} />
          <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-[#eef1ef] pt-3 text-[11px] text-muted-foreground">
            <span>
              <Clock3 size={12} className="mr-1.5 inline" />
              Selected publication: {publication}
            </span>
            <Link
              to={`/explorer?${search}`}
              className="flex items-center gap-1 font-medium text-primary"
            >
              Inspect revisions <ArrowRight size={12} />
            </Link>
          </div>
        </Panel>
        <Panel title="Decision context" subtitle="A clear point-in-time view">
          <div className="mt-2 rounded-lg bg-[#eff6f1] p-4">
            <div className="eyebrow text-[#5a7a69]">Available at decision</div>
            <p className="mt-2 text-2xl font-semibold tracking-tight">
              {cutoff}{" "}
              <span className="text-xs font-normal text-muted-foreground">
                GMT
              </span>
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
              {dateLabel(summary.decision_date)}
              <br />
              Only publications at or before this cutoff qualify.
            </p>
          </div>
          <dl className="mt-5 space-y-4 text-xs">
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Delivery hours matched</dt>
              <dd className="font-medium">
                {summary.coverage.matched_hours} /{" "}
                {summary.coverage.expected_hours}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">
                Actual settlement periods
              </dt>
              <dd className="font-medium">
                {summary.coverage.available_actual_settlement_periods} /{" "}
                {summary.coverage.expected_actual_settlement_periods}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Day MAE</dt>
              <dd className="font-medium">
                {number(summary.metrics.mae_mw)} MW
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Missing forecast hours</dt>
              <dd className="font-medium">
                {summary.coverage.missing_forecast_hours}
              </dd>
            </div>
          </dl>
          <div className="mt-5 border-t border-[#e6ece8] pt-4 text-[11px] leading-relaxed text-muted-foreground">
            Actual generation and this day's error are retrospective. They were
            unavailable when the purchasing decision was made.
          </div>
        </Panel>
      </div>
      <MethodNote>
        Hourly evaluation: actual generation is the mean of both half-hour
        settlement periods. The hourly forecast is treated as representative of
        that hour, a pilot alignment assumption. The {cutoff} UK cutoff is a
        pilot assumption, not a verified market gate-closure rule.
      </MethodNote>
      <Panel
        title="Delivery interval detail"
        subtitle="Publication provenance and exact values · all power values in MW"
        action={
          <Button variant="ghost" size="sm" asChild>
            <Link to={`/accuracy?${search}`}>
              View month accuracy <ArrowRight size={13} />
            </Link>
          </Button>
        }
      >
        <details>
          <summary className="py-2 text-xs font-medium text-primary">
            Show {data.hours.length} hourly intervals
          </summary>
          <div className="mt-3 overflow-x-auto">
            <table className="data-table">
              <caption className="sr-only">
                Hourly delivery forecast and retrospective actuals
              </caption>
              <thead>
                <tr>
                  <th>Delivery start (GMT)</th>
                  <th>Forecast MW</th>
                  <th>Actual MW</th>
                  <th>Error MW</th>
                  <th>Published (GMT)</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.hours.map((hour) => (
                  <tr key={hour.start_time}>
                    <td>{clock(hour.start_time)}</td>
                    <td>{number(hour.forecast_mw)}</td>
                    <td>{number(hour.actual_mw, 1)}</td>
                    <td>{signed(hour.error_mw, 1)}</td>
                    <td>{stamp(hour.selected_publish_time)}</td>
                    <td>{hour.status.replaceAll("_", " ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </Panel>
      <SourceFooter meta={data.meta} />
    </div>
  );
}
