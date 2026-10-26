import { Clock3, History, Target } from "lucide-react";
import {
  Line,
  LineChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { endpoint, useApi } from "@/api/client";
import type { HistoryResponse } from "@/api/types";
import {
  clock,
  dateLabel,
  number,
  shiftDate,
  signed,
  stamp,
} from "@/lib/format";
import {
  EmptyState,
  ErrorState,
  Legend,
  LoadingState,
  MethodNote,
  MetricCard,
  Panel,
  SourceFooter,
} from "@/components/analytics";
import { grid, tickGW, tooltipStyle } from "@/components/charts";
import { Badge } from "@/components/ui/badge";

export function Explorer({
  decision,
  cutoff,
  hour,
  setDecision,
  setHour,
}: {
  decision: string;
  cutoff: string;
  hour: string;
  setDecision: (value: string) => void;
  setHour: (value: string) => void;
}) {
  const delivery = shiftDate(decision, 1),
    target = `${delivery}T${hour}:00:00Z`;
  const query = useApi<HistoryResponse>(
    endpoint("/forecast-history", { start_time: target, cutoff }),
  );
  if (query.loading) return <LoadingState />;
  if (query.error || !query.data)
    return (
      <ErrorState
        message={query.error || "No response received."}
        retry={query.retry}
      />
    );
  const data = query.data,
    interval = data.hour;
  const revisions = data.revisions.map((revision) => ({
    ...revision,
    published_ms: new Date(revision.publish_time).getTime(),
    chart_mw: revision.valid ? revision.forecast_mw : null,
  }));
  const deadline = new Date(interval.cutoff_utc).getTime();
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-[#dfe7e4] bg-white px-5 py-4">
        <div className="flex flex-wrap items-center gap-5">
          <label className="flex items-center gap-3 text-xs font-medium">
            Delivery date
            <input
              aria-label="Delivery date"
              type="date"
              value={delivery}
              min="2026-01-02"
              max="2026-02-01"
              onChange={(e) =>
                e.target.value && setDecision(shiftDate(e.target.value, -1))
              }
            />
          </label>
          <label className="flex items-center gap-3 text-xs font-medium">
            Interval
            <select
              aria-label="Delivery interval"
              value={hour}
              onChange={(e) => setHour(e.target.value)}
            >
              {Array.from({ length: 24 }, (_, i) =>
                String(i).padStart(2, "0"),
              ).map((value) => (
                <option key={value} value={value}>
                  {value}:00–{String((Number(value) + 1) % 24).padStart(2, "0")}
                  :00 GMT
                </option>
              ))}
            </select>
          </label>
        </div>
        <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <History size={14} />
          {data.revisions.length} retained revisions
        </span>
      </div>
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <MetricCard
          label="Selected forecast"
          value={number(interval.forecast_mw)}
          unit="MW"
          note={`Published ${stamp(interval.selected_publish_time)}`}
          icon={<Target size={16} />}
          tone="green"
        />
        <MetricCard
          label="Retrospective actual"
          value={number(interval.actual_mw, 1)}
          unit="MW"
          note={`${interval.actual_settlement_period_count} of 2 actual half-hours available`}
        />
        <MetricCard
          label="Forecast error"
          value={signed(interval.error_mw, 1)}
          unit="MW"
          note="Selected forecast − retrospective actual"
          tone="amber"
        />
        <MetricCard
          label="Decision cutoff"
          value={cutoff}
          unit="GMT"
          note={dateLabel(decision)}
          icon={<Clock3 size={16} />}
        />
      </div>
      <Panel
        title="A forecast is a moving picture"
        subtitle={`Revisions for ${dateLabel(delivery)}, ${hour}:00 GMT · only the latest eligible publication is selected`}
      >
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3 text-[11px] text-muted-foreground">
          <span>Forecast generation · GW</span>
          <Legend revision />
        </div>
        {revisions.length ? (
          <div
            className="chart"
            role="img"
            aria-label="Wind forecast revisions by publication time, with purchasing cutoff and retrospective actual reference. Exact revisions appear in the table below."
          >
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={revisions}
                accessibilityLayer
                margin={{ top: 24, right: 22, bottom: 12, left: 0 }}
              >
                <CartesianGrid {...grid} />
                <XAxis
                  dataKey="published_ms"
                  type="number"
                  scale="time"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={(v) =>
                    stamp(new Date(Number(v)).toISOString())
                  }
                  minTickGap={40}
                  axisLine={false}
                  tickLine={false}
                  dy={8}
                />
                <YAxis
                  tickFormatter={tickGW}
                  width={45}
                  domain={[0, "auto"]}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelFormatter={(v) =>
                    stamp(new Date(Number(v)).toISOString())
                  }
                  formatter={(v) => [
                    `${number(Number(v))} MW`,
                    "Published forecast",
                  ]}
                />
                <ReferenceLine
                  x={deadline}
                  stroke="#b78339"
                  strokeDasharray="4 3"
                  label={{
                    value: "Decision cutoff",
                    fill: "#986825",
                    fontSize: 11,
                    position: "insideTopRight",
                  }}
                />
                {interval.actual_mw != null && (
                  <ReferenceLine
                    y={interval.actual_mw}
                    stroke="#8572ad"
                    strokeDasharray="5 4"
                  />
                )}
                <Line
                  dataKey="chart_mw"
                  name="Published forecast"
                  type="stepAfter"
                  stroke="#198469"
                  strokeWidth={2}
                  dot={{ r: 3, fill: "#fff", strokeWidth: 1.5 }}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyState message="No revisions are retained for this target in the snapshot." />
        )}
      </Panel>
      <MethodNote>
        <strong>Point-in-time selection:</strong> the latest publication at or
        before {stamp(interval.cutoff_utc)} is eligible for the decision. Later
        revisions are shown for exploration and never replace the selected
        forecast. {data.uncertainty_note}
      </MethodNote>
      <Panel
        title="Publication history"
        subtitle="Full provenance for this target within the captured publication window"
        action={<Badge variant="outline">UTC stored · UK time displayed</Badge>}
      >
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Published (GMT)</th>
                <th>Forecast MW</th>
                <th>At decision cutoff</th>
                <th>Selection</th>
              </tr>
            </thead>
            <tbody>
              {data.revisions.map((revision) => (
                <tr
                  className={revision.selected ? "selected" : ""}
                  key={revision.publish_time}
                >
                  <td>{stamp(revision.publish_time)}</td>
                  <td className="font-medium">
                    {number(revision.forecast_mw)}
                  </td>
                  <td>
                    {revision.eligible_at_cutoff
                      ? "Available"
                      : "Published after cutoff"}
                  </td>
                  <td>
                    {revision.selected ? (
                      <Badge className="bg-[#d8eddf] text-[#326d4b]">
                        Selected at cutoff
                      </Badge>
                    ) : !revision.valid ? (
                      <Badge variant="destructive">
                        Invalid: {revision.invalid_reason}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground">
                        {revision.eligible_at_cutoff
                          ? "Superseded before cutoff"
                          : "Excluded"}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-[11px] leading-relaxed text-muted-foreground">
          History bounded to publications from{" "}
          {stamp(data.meta.publication_from)} through{" "}
          {stamp(data.meta.publication_to)}. Global archive completeness is not
          guaranteed. Actual interval: {clock(interval.start_time)}–
          {clock(interval.end_time)} GMT, aggregated from both actual
          half-hours.
        </p>
      </Panel>
      <SourceFooter meta={data.meta} />
    </div>
  );
}
