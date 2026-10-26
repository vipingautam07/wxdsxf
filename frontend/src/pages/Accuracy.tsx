import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  ChartNoAxesCombined,
  Target,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Link } from "react-router-dom";
import { endpoint, useApi } from "@/api/client";
import type { AccuracyResponse, DailyResponse } from "@/api/types";
import { dateLabel, number, signed } from "@/lib/format";
import {
  CoverageBadge,
  EmptyState,
  ErrorState,
  LoadingState,
  MethodNote,
  MetricCard,
  Panel,
  SourceFooter,
} from "@/components/analytics";
import { grid, tickGW, tooltipStyle } from "@/components/charts";

export function Accuracy({ cutoff }: { cutoff: string }) {
  const query = { cutoff };
  const analysis = useApi<AccuracyResponse>(endpoint("/accuracy", query));
  const daily = useApi<DailyResponse>(endpoint("/accuracy/daily", query));
  if (analysis.loading || daily.loading) return <LoadingState />;
  if (analysis.error || daily.error || !analysis.data || !daily.data)
    return (
      <ErrorState
        message={analysis.error || daily.error || "No response received."}
        retry={() => {
          analysis.retry();
          daily.retry();
        }}
      />
    );
  const data = analysis.data,
    metrics = data.metrics;
  const limit =
    Math.ceil(
      Math.max(
        1000,
        ...data.scatter.flatMap((point) => [
          point.forecast_mw,
          point.actual_mw,
        ]),
      ) / 5000,
    ) * 5000;
  const bins = data.error_distribution.map((bin) => ({
    ...bin,
    label: `${number(bin.lower_mw / 1000, 1)} to ${number(bin.upper_mw / 1000, 1)}`,
  }));
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
        <p>
          1–31 January decisions <span className="mx-2 text-[#a4b4ad]">/</span>{" "}
          2 January–1 February deliveries{" "}
          <span className="mx-2 text-[#a4b4ad]">/</span> {cutoff} GMT cutoff
        </p>
        <CoverageBadge coverage={data.coverage} />
      </div>
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <MetricCard
          label="Mean absolute error"
          value={number(metrics.mae_mw)}
          unit="MW"
          note="MAE · average size of forecast error"
          icon={<Target size={16} />}
        />
        <MetricCard
          label="Root mean squared error"
          value={number(metrics.rmse_mw)}
          unit="MW"
          note="RMSE · gives larger errors more weight"
          icon={<Activity size={16} />}
        />
        <MetricCard
          label="Mean bias error"
          value={signed(metrics.mean_bias_mw)}
          unit="MW"
          note="Signed average · positive = overforecast"
          icon={<ArrowUpRight size={16} />}
          tone="amber"
        />
        <MetricCard
          label="Weighted absolute error"
          value={number(metrics.wape_pct, 2)}
          unit="%"
          note="WAPE · absolute error / total actual MW"
          icon={<ChartNoAxesCombined size={16} />}
        />
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Panel
          title="How accuracy changed each day"
          subtitle="Errors by delivery date · GW"
          action={
            <div className="flex gap-3 text-[10px] text-muted-foreground">
              <span>● MAE</span>
              <span className="text-[#a36726]">┄ Bias</span>
            </div>
          }
        >
          {metrics.matched_hours ? (
            <div
              className="chart"
              role="img"
              aria-label="Daily absolute error and signed bias. Exact daily metrics are available in the table below."
            >
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={daily.data.days}
                  accessibilityLayer
                  margin={{ left: 0, right: 14, top: 20, bottom: 5 }}
                >
                  <CartesianGrid {...grid} />
                  <XAxis
                    dataKey="delivery_date"
                    tickFormatter={(v) => dateLabel(v, true)}
                    minTickGap={24}
                    axisLine={false}
                    tickLine={false}
                    dy={8}
                  />
                  <YAxis
                    tickFormatter={tickGW}
                    width={40}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    labelFormatter={(v) => dateLabel(String(v), true)}
                    formatter={(v, n) => [`${number(Number(v))} MW`, n]}
                  />
                  <ReferenceLine y={0} stroke="#b9c9c1" />
                  <Line
                    dataKey="metrics.mae_mw"
                    name="MAE"
                    stroke="#198469"
                    strokeWidth={2.5}
                    dot={false}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                  <Line
                    dataKey="metrics.mean_bias_mw"
                    name="Bias"
                    stroke="#b07c3d"
                    strokeWidth={1.8}
                    strokeDasharray="5 4"
                    dot={false}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState />
          )}
        </Panel>
        <Panel
          title="Over or under?"
          subtitle="Direction of error across all matched hours"
        >
          {metrics.matched_hours ? (
            <>
              <div
                className="mt-6 flex h-3 overflow-hidden rounded-full bg-[#edf1ee]"
                aria-hidden="true"
              >
                <div
                  className="bg-[#bd945d]"
                  style={{ width: `${metrics.overforecast_pct}%` }}
                />
                <div
                  className="bg-[#668eaa]"
                  style={{ width: `${metrics.underforecast_pct}%` }}
                />
                <div
                  className="bg-[#a7b7ac]"
                  style={{ width: `${metrics.exact_pct}%` }}
                />
              </div>
              <div className="mt-6 grid grid-cols-2 gap-5">
                <div>
                  <div className="flex items-center gap-1.5 text-xs text-[#916936]">
                    <ArrowUpRight size={15} />
                    Overforecast
                  </div>
                  <p className="tabular mt-2 text-3xl font-semibold tracking-tight">
                    {number(metrics.overforecast_pct, 1)}
                    <span className="text-sm font-normal">%</span>
                  </p>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    {number(metrics.overforecast_hours)} hours
                  </p>
                </div>
                <div>
                  <div className="flex items-center gap-1.5 text-xs text-[#55768e]">
                    <ArrowDownRight size={15} />
                    Underforecast
                  </div>
                  <p className="tabular mt-2 text-3xl font-semibold tracking-tight">
                    {number(metrics.underforecast_pct, 1)}
                    <span className="text-sm font-normal">%</span>
                  </p>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    {number(metrics.underforecast_hours)} hours
                  </p>
                </div>
              </div>
              <div className="mt-6 border-t border-[#e7ece8] pt-4 text-[11px] leading-relaxed text-muted-foreground">
                Exact forecasts: {number(metrics.exact_hours)} hours (
                {number(metrics.exact_pct, 1)}%). Positive error means the
                forecast exceeded reported actual generation.
              </div>
            </>
          ) : (
            <EmptyState />
          )}
          <div className="mt-4 rounded-lg bg-[#f3f6f3] p-4">
            <span className="eyebrow">90th percentile absolute error</span>
            <p className="tabular mt-1 text-xl font-semibold">
              {number(metrics.p90_absolute_error_mw)}{" "}
              <span className="text-xs font-normal text-muted-foreground">
                MW
              </span>
            </p>
            <p className="mt-1 text-[10px] text-muted-foreground">
              90% of matched absolute errors fall at or below this value.
            </p>
          </div>
        </Panel>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Panel
          title="Forecast vs actual"
          subtitle="Matched hourly observations · both axes in GW · diagonal = perfect forecast"
        >
          {data.scatter.length ? (
            <div
              className="chart-small"
              role="img"
              aria-label="Scatter plot with actual generation on the horizontal axis and forecast on the vertical axis."
            >
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart
                  accessibilityLayer
                  margin={{ left: 5, right: 18, bottom: 18, top: 8 }}
                >
                  <CartesianGrid stroke="#edf0ee" strokeDasharray="3 3" />
                  <XAxis
                    type="number"
                    dataKey="actual_mw"
                    name="Actual"
                    tickFormatter={tickGW}
                    domain={[0, limit]}
                    axisLine={false}
                    tickLine={false}
                    label={{
                      value: "Actual GW",
                      position: "insideBottom",
                      offset: -12,
                      fontSize: 10,
                      fill: "#718080",
                    }}
                  />
                  <YAxis
                    type="number"
                    dataKey="forecast_mw"
                    name="Forecast"
                    tickFormatter={tickGW}
                    domain={[0, limit]}
                    axisLine={false}
                    tickLine={false}
                    width={40}
                  />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    formatter={(v, n) => [`${number(Number(v))} MW`, n]}
                  />
                  <ReferenceLine
                    segment={[
                      { x: 0, y: 0 },
                      { x: limit, y: limit },
                    ]}
                    stroke="#a3b9ad"
                    strokeDasharray="4 4"
                  />
                  <Scatter
                    data={data.scatter}
                    fill="#198469"
                    fillOpacity={0.5}
                    isAnimationActive={false}
                  />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState />
          )}
        </Panel>
        <Panel
          title="Error distribution"
          subtitle="Number of hours in each signed error range · GW"
        >
          {bins.length ? (
            <div
              className="chart-small"
              role="img"
              aria-label="Histogram of signed forecast error; positive values are overforecasts."
            >
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={bins}
                  accessibilityLayer
                  margin={{ left: 0, right: 10, bottom: 18, top: 8 }}
                >
                  <CartesianGrid {...grid} />
                  <XAxis
                    dataKey="label"
                    interval={2}
                    fontSize={9}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    width={30}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    labelFormatter={(v) => `${v} GW error`}
                    formatter={(v) => [`${v} hours`, "Frequency"]}
                  />
                  <Bar
                    dataKey="count"
                    fill="#7a9d8b"
                    radius={[3, 3, 0, 0]}
                    isAnimationActive={false}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState />
          )}
        </Panel>
      </div>
      <Panel
        title="Days with the largest errors"
        subtitle="Ranked by MAE · delivery dates · coverage is shown for context"
      >
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Delivery day</th>
                <th>MAE (MW)</th>
                <th>RMSE (MW)</th>
                <th>Bias (MW)</th>
                <th>WAPE</th>
                <th>Matched</th>
              </tr>
            </thead>
            <tbody>
              {data.worst_days.map((day) => (
                <tr key={day.decision_date}>
                  <td>
                    <Link
                      className="font-medium text-primary hover:underline"
                      to={`/?date=${day.decision_date}&cutoff=${cutoff}`}
                    >
                      {dateLabel(day.delivery_date, true)} ↗
                    </Link>
                  </td>
                  <td>{number(day.metrics.mae_mw)}</td>
                  <td>{number(day.metrics.rmse_mw)}</td>
                  <td>{signed(day.metrics.mean_bias_mw)}</td>
                  <td>{number(day.metrics.wape_pct, 1)}%</td>
                  <td>
                    {day.coverage.matched_hours} / {day.coverage.expected_hours}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!data.worst_days.length && <EmptyState />}
      </Panel>
      <Panel
        title="Daily metrics and metric definitions"
        subtitle="Exact numerical alternative to the charts"
      >
        <details>
          <summary className="py-2 text-xs font-medium text-primary">
            Show daily metrics and definitions
          </summary>
          <p className="my-3 text-xs leading-relaxed text-muted-foreground">
            MAE is mean |forecast − actual|. RMSE is the square root of mean
            squared error. Bias is mean (forecast − actual). WAPE is total
            absolute error divided by total absolute actual generation,
            multiplied by 100; it is undefined when the denominator is zero. All
            metrics use matched hourly pairs. Monthly metrics are pooled, not
            averages of daily statistics.
          </p>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Delivery</th>
                  <th>MAE MW</th>
                  <th>RMSE MW</th>
                  <th>Bias MW</th>
                  <th>WAPE %</th>
                  <th>Hours</th>
                </tr>
              </thead>
              <tbody>
                {daily.data.days.map((day) => (
                  <tr key={day.decision_date}>
                    <td>{dateLabel(day.delivery_date, true)}</td>
                    <td>{number(day.metrics.mae_mw, 1)}</td>
                    <td>{number(day.metrics.rmse_mw, 1)}</td>
                    <td>{signed(day.metrics.mean_bias_mw, 1)}</td>
                    <td>{number(day.metrics.wape_pct, 2)}</td>
                    <td>
                      {day.coverage.matched_hours}/{day.coverage.expected_hours}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </Panel>
      <MethodNote>
        This is retrospective evaluation at the selected purchasing cutoff.
        Hourly forecasts are compared with the mean of both FUELHH half-hours.
        Missing pairs are excluded from metrics and retained in coverage.
        Historical error does not establish future accuracy.
      </MethodNote>
      <SourceFooter meta={data.meta} />
    </div>
  );
}
