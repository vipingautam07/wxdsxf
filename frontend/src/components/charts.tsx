import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Hour } from "@/api/types";
import { clock, number } from "@/lib/format";
import { EmptyState, Legend } from "./analytics";

export const grid = {
  stroke: "#edf0ee",
  strokeDasharray: "3 3",
  vertical: false,
};
export const tooltipStyle = {
  borderRadius: 10,
  border: "1px solid #dfe7e4",
  fontSize: 12,
  boxShadow: "0 5px 20px #19323810",
};
export const tickGW = (value: number) => `${number(value / 1000, 1)}`;

export function GenerationChart({ hours }: { hours: Hour[] }) {
  if (!hours.some((hour) => hour.forecast_mw != null || hour.actual_mw != null))
    return (
      <EmptyState message="No forecast or actual generation is available for this delivery day." />
    );
  return (
    <>
      <div className="mb-3 flex justify-between text-[10px] text-muted-foreground">
        <span>Generation · GW</span>
        <Legend />
      </div>
      <div
        className="chart"
        role="img"
        aria-label="Hourly wind forecasts available at the decision cutoff compared with retrospective actual generation. Exact values are in the interval table."
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={hours}
            margin={{ top: 12, right: 12, bottom: 6, left: 0 }}
            accessibilityLayer
          >
            <CartesianGrid {...grid} />
            <XAxis
              dataKey="start_time"
              tickFormatter={clock}
              minTickGap={38}
              axisLine={false}
              tickLine={false}
              dy={9}
            />
            <YAxis
              tickFormatter={tickGW}
              axisLine={false}
              tickLine={false}
              width={44}
              domain={[0, "auto"]}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              labelFormatter={(v) => `${clock(String(v))} GMT`}
              formatter={(value, name) => [`${number(Number(value))} MW`, name]}
            />
            <Line
              name="Forecast at cutoff"
              type="monotone"
              dataKey="forecast_mw"
              stroke="#198469"
              strokeWidth={2.5}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
              name="Retrospective actual"
              type="monotone"
              dataKey="actual_mw"
              stroke="#8572ad"
              strokeWidth={2}
              strokeDasharray="5 4"
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}
