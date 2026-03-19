import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { fetchAccuracyMetrics } from "@/lib/api";
import { Card, CardHeader } from "@/components/common/Card";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import type { AssetType, DamageSeverity } from "@/lib/types";

function assetTypeLabel(type: string): string {
  switch (type) {
    case "jet_ski":
      return "Jet Ski";
    case "boat":
      return "Boat";
    case "parasail":
      return "Parasail";
    default:
      return type;
  }
}

function formatDamageType(type: string): string {
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function accuracyColor(accuracy: number): string {
  if (accuracy >= 0.9) return "text-green-600";
  if (accuracy >= 0.75) return "text-amber-600";
  return "text-red-600";
}

function accuracyBarColor(accuracy: number): string {
  if (accuracy >= 0.9) return "bg-green-500";
  if (accuracy >= 0.75) return "bg-amber-500";
  return "bg-red-500";
}

export function AccuracyDashboard() {
  const {
    data: metrics,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["metrics", "accuracy"],
    queryFn: fetchAccuracyMetrics,
    refetchInterval: 60000, // Refresh every minute
  });

  if (isLoading) {
    return <LoadingSpinner className="py-16" />;
  }

  if (error) {
    return (
      <Card>
        <div className="text-center py-8 text-red-600 text-sm">
          Failed to load accuracy metrics. Please try again later.
        </div>
      </Card>
    );
  }

  if (!metrics) {
    return null;
  }

  const confirmedRate =
    metrics.total_findings > 0
      ? (metrics.confirmed_count / metrics.total_findings) * 100
      : 0;
  const rejectedRate =
    metrics.total_findings > 0
      ? (metrics.rejected_count / metrics.total_findings) * 100
      : 0;
  const correctedRate =
    metrics.total_findings > 0
      ? (metrics.corrected_count / metrics.total_findings) * 100
      : 0;

  return (
    <div className="space-y-6">
      {/* Overall accuracy */}
      <Card>
        <CardHeader
          title="Overall AI Accuracy"
          subtitle="Based on human-reviewed findings"
        />
        <div className="mt-6 flex flex-col items-center">
          {/* Circular gauge */}
          <div className="relative w-32 h-32">
            <svg className="w-full h-full -rotate-90" viewBox="0 0 128 128">
              <circle
                cx="64"
                cy="64"
                r="56"
                fill="none"
                stroke="currentColor"
                className="text-dock-100"
                strokeWidth="12"
              />
              <circle
                cx="64"
                cy="64"
                r="56"
                fill="none"
                stroke="currentColor"
                className={accuracyBarColor(metrics.overall_accuracy)}
                strokeWidth="12"
                strokeDasharray={`${metrics.overall_accuracy * 351.86} 351.86`}
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span
                className={clsx(
                  "text-3xl font-bold",
                  accuracyColor(metrics.overall_accuracy),
                )}
              >
                {Math.round(metrics.overall_accuracy * 100)}%
              </span>
            </div>
          </div>
          <p className="text-xs text-dock-500 mt-3">
            {metrics.total_findings} total findings reviewed
          </p>
        </div>

        {/* Breakdown bars */}
        <div className="mt-6 grid grid-cols-3 gap-4">
          <div className="text-center">
            <p className="text-xs text-dock-500 mb-1">Confirmed</p>
            <p className="text-lg font-bold text-green-600">
              {metrics.confirmed_count}
            </p>
            <p className="text-[10px] text-dock-400">
              {confirmedRate.toFixed(1)}%
            </p>
          </div>
          <div className="text-center">
            <p className="text-xs text-dock-500 mb-1">Corrected</p>
            <p className="text-lg font-bold text-amber-600">
              {metrics.corrected_count}
            </p>
            <p className="text-[10px] text-dock-400">
              {correctedRate.toFixed(1)}%
            </p>
          </div>
          <div className="text-center">
            <p className="text-xs text-dock-500 mb-1">Rejected</p>
            <p className="text-lg font-bold text-red-600">
              {metrics.rejected_count}
            </p>
            <p className="text-[10px] text-dock-400">
              {rejectedRate.toFixed(1)}%
            </p>
          </div>
        </div>
      </Card>

      {/* Accuracy by asset type */}
      <Card>
        <CardHeader title="Accuracy by Equipment Type" />
        <div className="mt-4 space-y-3">
          {Object.entries(metrics.accuracy_by_asset_type).map(
            ([type, data]) => (
              <div key={type} className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-navy-800">
                    {assetTypeLabel(type)}
                  </span>
                  <div className="flex items-center gap-2">
                    <span
                      className={clsx(
                        "text-sm font-semibold",
                        accuracyColor(data.accuracy),
                      )}
                    >
                      {Math.round(data.accuracy * 100)}%
                    </span>
                    <span className="text-xs text-dock-400">
                      ({data.total})
                    </span>
                  </div>
                </div>
                <div className="h-2 bg-dock-100 rounded-full overflow-hidden">
                  <div
                    className={clsx(
                      "h-full rounded-full transition-all",
                      accuracyBarColor(data.accuracy),
                    )}
                    style={{ width: `${data.accuracy * 100}%` }}
                  />
                </div>
              </div>
            ),
          )}
          {Object.keys(metrics.accuracy_by_asset_type).length === 0 && (
            <p className="text-sm text-dock-400 text-center py-4">
              No data available yet
            </p>
          )}
        </div>
      </Card>

      {/* Accuracy by damage type */}
      <Card>
        <CardHeader title="Accuracy by Damage Type" />
        <div className="mt-4 space-y-2.5">
          {Object.entries(metrics.accuracy_by_damage_type)
            .sort(([, a], [, b]) => b.total - a.total)
            .map(([type, data]) => (
              <div
                key={type}
                className="flex items-center justify-between py-1.5"
              >
                <span className="text-sm text-navy-800">
                  {formatDamageType(type)}
                </span>
                <div className="flex items-center gap-3">
                  <div className="w-24 h-1.5 bg-dock-100 rounded-full overflow-hidden">
                    <div
                      className={clsx(
                        "h-full rounded-full",
                        accuracyBarColor(data.accuracy),
                      )}
                      style={{ width: `${data.accuracy * 100}%` }}
                    />
                  </div>
                  <span
                    className={clsx(
                      "text-xs font-medium w-10 text-right",
                      accuracyColor(data.accuracy),
                    )}
                  >
                    {Math.round(data.accuracy * 100)}%
                  </span>
                  <span className="text-[10px] text-dock-400 w-6 text-right">
                    ({data.total})
                  </span>
                </div>
              </div>
            ))}
          {Object.keys(metrics.accuracy_by_damage_type).length === 0 && (
            <p className="text-sm text-dock-400 text-center py-4">
              No data available yet
            </p>
          )}
        </div>
      </Card>

      {/* Confidence calibration */}
      <Card>
        <CardHeader
          title="Confidence Calibration"
          subtitle="Expected confidence vs actual accuracy"
        />
        <div className="mt-4">
          <div className="space-y-2">
            {metrics.confidence_calibration.map((bucket) => (
              <div key={bucket.confidence_bucket} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-dock-600">
                    {bucket.confidence_bucket}
                  </span>
                  <div className="flex items-center gap-2">
                    <span
                      className={clsx(
                        "font-semibold",
                        accuracyColor(bucket.actual_accuracy),
                      )}
                    >
                      {Math.round(bucket.actual_accuracy * 100)}% actual
                    </span>
                    <span className="text-dock-400">
                      ({bucket.count} findings)
                    </span>
                  </div>
                </div>
                <div className="relative h-2 bg-dock-100 rounded-full overflow-hidden">
                  <div
                    className={clsx(
                      "absolute h-full rounded-full",
                      accuracyBarColor(bucket.actual_accuracy),
                    )}
                    style={{ width: `${bucket.actual_accuracy * 100}%` }}
                  />
                </div>
              </div>
            ))}
            {metrics.confidence_calibration.length === 0 && (
              <p className="text-sm text-dock-400 text-center py-4">
                Not enough data for calibration
              </p>
            )}
          </div>
        </div>
      </Card>

      {/* Accuracy trend */}
      {metrics.trend.length > 0 && (
        <Card>
          <CardHeader title="Accuracy Trend" />
          <div className="mt-4 space-y-2">
            {metrics.trend.map((period, index) => {
              const prevAccuracy = metrics.trend[index - 1]?.accuracy;
              const trendDirection =
                prevAccuracy !== undefined
                  ? period.accuracy > prevAccuracy
                    ? "up"
                    : period.accuracy < prevAccuracy
                      ? "down"
                      : "flat"
                  : "flat";

              return (
                <div
                  key={period.period}
                  className="flex items-center justify-between py-1.5"
                >
                  <span className="text-sm text-dock-600">{period.period}</span>
                  <div className="flex items-center gap-2">
                    <span
                      className={clsx(
                        "text-sm font-semibold",
                        accuracyColor(period.accuracy),
                      )}
                    >
                      {Math.round(period.accuracy * 100)}%
                    </span>
                    {trendDirection === "up" && (
                      <svg
                        className="w-4 h-4 text-green-500"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M4.5 15.75l7.5-7.5 7.5 7.5"
                        />
                      </svg>
                    )}
                    {trendDirection === "down" && (
                      <svg
                        className="w-4 h-4 text-red-500"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M19.5 8.25l-7.5 7.5-7.5-7.5"
                        />
                      </svg>
                    )}
                    <span className="text-xs text-dock-400">
                      ({period.total})
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}
