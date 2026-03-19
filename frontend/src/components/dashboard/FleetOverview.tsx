import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import clsx from "clsx";
import { fetchAssets, fetchInspections } from "@/lib/api";
import { Card, CardHeader } from "@/components/common/Card";
import { Badge, inspectionStatusBadgeVariant } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import type { AssetType } from "@/lib/types";
import { formatDistanceToNow } from "date-fns";

function assetTypeLabel(type: AssetType): string {
  switch (type) {
    case "jet_ski":
      return "Jet Ski";
    case "boat":
      return "Boat";
    case "parasail":
      return "Parasail";
  }
}

function assetTypeIcon(type: AssetType): string {
  switch (type) {
    case "jet_ski":
      return "JS";
    case "boat":
      return "BT";
    case "parasail":
      return "PS";
  }
}

export function FleetOverview() {
  const { data: assetsData, isLoading: assetsLoading } = useQuery({
    queryKey: ["assets", "overview"],
    queryFn: () => fetchAssets({ page_size: 200 }),
  });

  const { data: recentInspections, isLoading: inspectionsLoading } = useQuery({
    queryKey: ["inspections", "recent"],
    queryFn: () => fetchInspections({ page_size: 5 }),
  });

  const { data: pendingReviews } = useQuery({
    queryKey: ["inspections", "pending-review"],
    queryFn: () => fetchInspections({ status: "review", page_size: 1 }),
  });

  const isLoading = assetsLoading || inspectionsLoading;

  // Calculate asset counts by type
  const assetCounts: Record<AssetType, number> = {
    jet_ski: 0,
    boat: 0,
    parasail: 0,
  };
  assetsData?.items.forEach((asset) => {
    assetCounts[asset.asset_type]++;
  });

  const pendingCount = pendingReviews?.total ?? 0;

  if (isLoading) {
    return <LoadingSpinner className="py-16" />;
  }

  return (
    <div className="space-y-6">
      {/* Quick actions */}
      <div className="grid grid-cols-2 gap-3">
        <Link to="/inspections/new">
          <Card hover className="h-full">
            <div className="flex flex-col items-center text-center py-2">
              <div className="w-10 h-10 rounded-full bg-navy-100 flex items-center justify-center mb-2">
                <svg
                  className="w-5 h-5 text-navy-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 4.5v15m7.5-7.5h-15"
                  />
                </svg>
              </div>
              <span className="text-sm font-semibold text-navy-900">
                New Inspection
              </span>
              <span className="text-xs text-dock-500 mt-0.5">
                Start damage check
              </span>
            </div>
          </Card>
        </Link>

        <Link to="/inspections?status=review">
          <Card hover className="h-full">
            <div className="flex flex-col items-center text-center py-2 relative">
              <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center mb-2">
                <svg
                  className="w-5 h-5 text-amber-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15a2.25 2.25 0 012.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z"
                  />
                </svg>
              </div>
              <span className="text-sm font-semibold text-navy-900">
                Review Queue
              </span>
              <span className="text-xs text-dock-500 mt-0.5">
                {pendingCount} pending
              </span>
              {pendingCount > 0 && (
                <span className="absolute top-0 right-0 w-5 h-5 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center">
                  {pendingCount > 9 ? "9+" : pendingCount}
                </span>
              )}
            </div>
          </Card>
        </Link>
      </div>

      {/* Fleet summary */}
      <Card>
        <CardHeader title="Fleet Overview" subtitle={`${assetsData?.total ?? 0} total assets`} />
        <div className="grid grid-cols-3 gap-3 mt-4">
          {(["jet_ski", "boat", "parasail"] as AssetType[]).map((type) => (
            <Link
              key={type}
              to={`/assets?type=${type}`}
              className="flex flex-col items-center p-3 rounded-lg bg-dock-50 hover:bg-dock-100 transition-colors"
            >
              <div
                className={clsx(
                  "w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold mb-1.5",
                  type === "jet_ski" && "bg-marine-500",
                  type === "boat" && "bg-navy-500",
                  type === "parasail" && "bg-amber-500",
                )}
              >
                {assetTypeIcon(type)}
              </div>
              <span className="text-lg font-bold text-navy-900">
                {assetCounts[type]}
              </span>
              <span className="text-xs text-dock-500">
                {assetTypeLabel(type)}s
              </span>
            </Link>
          ))}
        </div>
      </Card>

      {/* Recent inspections */}
      <Card>
        <CardHeader
          title="Recent Inspections"
          action={
            <Link to="/inspections">
              <Button variant="ghost" size="sm">
                View All
              </Button>
            </Link>
          }
        />
        <div className="mt-4 space-y-2">
          {recentInspections?.items.map((inspection) => (
            <Link
              key={inspection.id}
              to={`/inspections/${inspection.id}`}
              className="flex items-center gap-3 p-2.5 -mx-2 rounded-lg hover:bg-dock-50 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-navy-900 truncate">
                  {inspection.asset?.name ?? "Unknown Asset"}
                </p>
                <p className="text-xs text-dock-500">
                  {inspection.inspection_type.replace("_", "-")} &middot;{" "}
                  {formatDistanceToNow(new Date(inspection.created_at), {
                    addSuffix: true,
                  })}
                </p>
              </div>
              <Badge
                variant={inspectionStatusBadgeVariant(inspection.status)}
                dot
              >
                {inspection.status}
              </Badge>
            </Link>
          ))}
          {recentInspections?.items.length === 0 && (
            <p className="text-center py-6 text-dock-400 text-sm">
              No inspections yet. Start your first inspection above.
            </p>
          )}
        </div>
      </Card>
    </div>
  );
}
