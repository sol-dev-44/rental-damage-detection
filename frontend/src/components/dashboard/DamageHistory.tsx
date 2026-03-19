import { useState, useMemo } from "react";
import clsx from "clsx";
import { useQuery } from "@tanstack/react-query";
import { fetchInspections } from "@/lib/api";
import { Card, CardHeader } from "@/components/common/Card";
import { Badge, severityBadgeVariant, findingStatusBadgeVariant } from "@/components/common/Badge";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import type { Finding, DamageSeverity, FindingStatus } from "@/lib/types";
import { format } from "date-fns";

interface DamageHistoryProps {
  assetId?: string;
}

type SeverityFilter = DamageSeverity | "all";
type StatusFilter = FindingStatus | "all";

export function DamageHistory({ assetId }: DamageHistoryProps) {
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const { data: inspectionsData, isLoading } = useQuery({
    queryKey: ["inspections", "completed", assetId],
    queryFn: () =>
      fetchInspections({
        asset_id: assetId,
        status: "completed",
        page_size: 50,
      }),
  });

  // Flatten findings from all inspections
  const allFindings = useMemo(() => {
    if (!inspectionsData?.items) return [];
    return inspectionsData.items.flatMap((inspection) =>
      inspection.findings.map((finding) => ({
        ...finding,
        inspectionDate: inspection.completed_at ?? inspection.created_at,
        assetName: inspection.asset?.name ?? "Unknown",
      })),
    );
  }, [inspectionsData]);

  // Apply filters
  const filteredFindings = useMemo(() => {
    return allFindings.filter((finding) => {
      if (severityFilter !== "all" && finding.severity !== severityFilter) {
        return false;
      }
      if (statusFilter !== "all" && finding.status !== statusFilter) {
        return false;
      }
      return true;
    });
  }, [allFindings, severityFilter, statusFilter]);

  // Statistics
  const stats = useMemo(() => {
    const total = allFindings.length;
    const confirmed = allFindings.filter((f) => f.status === "confirmed").length;
    const bySeverity: Record<string, number> = {};
    const byType: Record<string, number> = {};

    allFindings.forEach((f) => {
      bySeverity[f.severity] = (bySeverity[f.severity] ?? 0) + 1;
      byType[f.damage_type] = (byType[f.damage_type] ?? 0) + 1;
    });

    const topDamageType = Object.entries(byType).sort(
      ([, a], [, b]) => b - a,
    )[0];

    return { total, confirmed, bySeverity, topDamageType };
  }, [allFindings]);

  const formatDamageType = (type: string): string => {
    return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  };

  if (isLoading) {
    return <LoadingSpinner className="py-16" />;
  }

  return (
    <div className="space-y-6">
      {/* Summary statistics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card padding="sm">
          <p className="text-xs text-dock-500 font-medium">Total Findings</p>
          <p className="text-2xl font-bold text-navy-900 mt-1">
            {stats.total}
          </p>
        </Card>
        <Card padding="sm">
          <p className="text-xs text-dock-500 font-medium">Confirmed</p>
          <p className="text-2xl font-bold text-green-600 mt-1">
            {stats.confirmed}
          </p>
        </Card>
        <Card padding="sm">
          <p className="text-xs text-dock-500 font-medium">Most Common</p>
          <p className="text-sm font-semibold text-navy-900 mt-1 truncate">
            {stats.topDamageType
              ? formatDamageType(stats.topDamageType[0])
              : "N/A"}
          </p>
          {stats.topDamageType && (
            <p className="text-xs text-dock-400">
              {stats.topDamageType[1]} occurrences
            </p>
          )}
        </Card>
        <Card padding="sm">
          <p className="text-xs text-dock-500 font-medium">Severe+</p>
          <p className="text-2xl font-bold text-red-600 mt-1">
            {(stats.bySeverity["severe"] ?? 0) +
              (stats.bySeverity["critical"] ?? 0)}
          </p>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1">
            <label className="block text-xs font-medium text-dock-600 mb-1">
              Severity
            </label>
            <div className="flex flex-wrap gap-1">
              {(["all", "none", "minor", "moderate", "severe", "critical"] as SeverityFilter[]).map(
                (sev) => (
                  <button
                    key={sev}
                    onClick={() => setSeverityFilter(sev)}
                    className={clsx(
                      "px-2.5 py-1 rounded-full text-xs font-medium transition-colors",
                      severityFilter === sev
                        ? "bg-navy-600 text-white"
                        : "bg-dock-100 text-dock-600 hover:bg-dock-200",
                    )}
                  >
                    {sev === "all" ? "All" : sev}
                  </button>
                ),
              )}
            </div>
          </div>
          <div className="flex-1">
            <label className="block text-xs font-medium text-dock-600 mb-1">
              Review Status
            </label>
            <div className="flex flex-wrap gap-1">
              {(["all", "pending", "confirmed", "rejected", "corrected"] as StatusFilter[]).map(
                (status) => (
                  <button
                    key={status}
                    onClick={() => setStatusFilter(status)}
                    className={clsx(
                      "px-2.5 py-1 rounded-full text-xs font-medium transition-colors",
                      statusFilter === status
                        ? "bg-navy-600 text-white"
                        : "bg-dock-100 text-dock-600 hover:bg-dock-200",
                    )}
                  >
                    {status === "all" ? "All" : status}
                  </button>
                ),
              )}
            </div>
          </div>
        </div>
      </Card>

      {/* Findings list */}
      <Card padding="none">
        <div className="divide-y divide-dock-100">
          {filteredFindings.map((finding) => (
            <div
              key={finding.id}
              className="flex items-center gap-3 px-4 py-3 sm:px-6"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-navy-900">
                    {formatDamageType(finding.damage_type)}
                  </p>
                  <Badge variant={severityBadgeVariant(finding.severity)} size="sm">
                    {finding.severity}
                  </Badge>
                </div>
                <p className="text-xs text-dock-500 mt-0.5">
                  {finding.location_description}
                </p>
                <p className="text-xs text-dock-400 mt-0.5">
                  {!assetId && <>{finding.assetName} &middot; </>}
                  {format(new Date(finding.inspectionDate), "MMM d, yyyy")}
                </p>
              </div>
              <div className="flex flex-col items-end gap-1">
                <Badge
                  variant={findingStatusBadgeVariant(finding.status)}
                  size="sm"
                  dot
                >
                  {finding.status}
                </Badge>
                <span className="text-[10px] text-dock-400">
                  {Math.round(finding.confidence * 100)}% conf.
                </span>
              </div>
            </div>
          ))}
          {filteredFindings.length === 0 && (
            <div className="py-12 text-center text-dock-400 text-sm">
              No findings match the selected filters.
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
