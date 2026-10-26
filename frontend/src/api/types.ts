export type Metrics = {
  matched_hours: number;
  mae_mw: number | null;
  rmse_mw: number | null;
  mean_bias_mw: number | null;
  wape_pct: number | null;
  p90_absolute_error_mw: number | null;
  overforecast_hours: number;
  underforecast_hours: number;
  exact_hours: number;
  overforecast_pct: number | null;
  underforecast_pct: number | null;
  exact_pct: number | null;
};
export type Coverage = {
  expected_hours: number;
  matched_hours: number;
  unmatched_hours: number;
  missing_forecast_hours: number;
  missing_actual_hours: number;
  invalid_hours: number;
  expected_actual_settlement_periods: number;
  available_actual_settlement_periods: number;
  missing_actual_settlement_periods: number;
  matched_pct: number | null;
};
export type Meta = {
  snapshot_id: string;
  data_retrieved_at: string;
  source_mode: string;
  cutoff_local: string;
  alignment_assumption: string;
  geographic_scope: string;
  publication_from: string;
  publication_to: string;
  warnings: string[];
};
export type Hour = {
  start_time: string;
  end_time: string;
  cutoff_utc: string;
  forecast_mw: number | null;
  actual_mw: number | null;
  error_mw: number | null;
  selected_publish_time: string | null;
  actual_settlement_period_count: number;
  status: string;
};
export type Daily = {
  decision_date: string;
  delivery_date: string;
  cutoff_utc: string;
  forecast_mean_mw: number | null;
  actual_mean_mw: number | null;
  metrics: Metrics;
  coverage: Coverage;
};
export type DayResponse = {
  meta: Meta;
  summary: Daily;
  hours: Hour[];
  selected_publication_from: string | null;
  selected_publication_to: string | null;
  historical_reliability: { as_of: string; metrics: Metrics };
};
export type AccuracyResponse = {
  meta: Meta;
  metrics: Metrics;
  coverage: Coverage;
  worst_days: Daily[];
  error_distribution: {
    lower_mw: number;
    upper_mw: number;
    upper_inclusive: boolean;
    count: number;
  }[];
  scatter: {
    start_time: string;
    forecast_mw: number;
    actual_mw: number;
    error_mw: number;
  }[];
};
export type Revision = {
  publish_time: string;
  forecast_mw: number | null;
  eligible_at_cutoff: boolean;
  selected: boolean;
  valid: boolean;
  invalid_reason: string | null;
};
export type HistoryResponse = {
  meta: Meta;
  hour: Hour;
  revisions: Revision[];
  uncertainty_note: string;
};
export type DailyResponse = { meta: Meta; days: Daily[] };
