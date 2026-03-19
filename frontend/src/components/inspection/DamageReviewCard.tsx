import { useState } from "react";
import clsx from "clsx";
import type { Finding, DamageSeverity, FindingReview } from "@/lib/types";
import { Badge, severityBadgeVariant, findingStatusBadgeVariant } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";

interface DamageReviewCardProps {
  finding: Finding;
  onReview: (findingId: string, review: FindingReview) => void;
  isSubmitting?: boolean;
}

const DAMAGE_TYPES = [
  "scratch",
  "dent",
  "crack",
  "tear",
  "discoloration",
  "corrosion",
  "missing_part",
  "structural",
  "gelcoat_damage",
  "hull_breach",
  "propeller_damage",
  "upholstery_damage",
  "electrical",
  "other",
];

const SEVERITY_OPTIONS: DamageSeverity[] = [
  "none",
  "minor",
  "moderate",
  "severe",
  "critical",
];

export function DamageReviewCard({
  finding,
  onReview,
  isSubmitting = false,
}: DamageReviewCardProps) {
  const [showCorrectionForm, setShowCorrectionForm] = useState(false);
  const [correctedSeverity, setCorrectedSeverity] = useState<DamageSeverity>(
    finding.severity,
  );
  const [correctedType, setCorrectedType] = useState(finding.damage_type);
  const [correctedLocation, setCorrectedLocation] = useState(
    finding.location_description,
  );
  const [notes, setNotes] = useState("");

  const isReviewed = finding.status !== "pending";

  const handleConfirm = () => {
    onReview(finding.id, {
      status: "confirmed",
      reviewer_notes: notes || undefined,
    });
  };

  const handleReject = () => {
    onReview(finding.id, {
      status: "rejected",
      reviewer_notes: notes || undefined,
    });
  };

  const handleCorrect = () => {
    onReview(finding.id, {
      status: "corrected",
      severity: correctedSeverity,
      damage_type: correctedType,
      location_description: correctedLocation,
      reviewer_notes: notes || undefined,
    });
    setShowCorrectionForm(false);
  };

  // Confidence level indicator
  const confidenceLevel =
    finding.confidence >= 0.9
      ? "high"
      : finding.confidence >= 0.7
        ? "medium"
        : "low";

  const confidenceColor =
    confidenceLevel === "high"
      ? "text-green-600"
      : confidenceLevel === "medium"
        ? "text-amber-600"
        : "text-red-600";

  const confidenceBarColor =
    confidenceLevel === "high"
      ? "bg-green-500"
      : confidenceLevel === "medium"
        ? "bg-amber-500"
        : "bg-red-500";

  const formatDamageType = (type: string): string => {
    return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  };

  return (
    <Card
      className={clsx(
        isReviewed && "opacity-75",
        finding.status === "rejected" && "bg-dock-50",
      )}
    >
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h4 className="text-sm font-semibold text-navy-900">
              {formatDamageType(finding.damage_type)}
            </h4>
            <p className="text-xs text-dock-500 mt-0.5">
              {finding.location_description}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={severityBadgeVariant(finding.severity)}>
              {finding.severity}
            </Badge>
            {isReviewed && (
              <Badge variant={findingStatusBadgeVariant(finding.status)} dot>
                {finding.status}
              </Badge>
            )}
          </div>
        </div>

        {/* Confidence indicator */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs text-dock-500">AI Confidence</span>
            <span className={clsx("text-xs font-medium", confidenceColor)}>
              {Math.round(finding.confidence * 100)}%
            </span>
          </div>
          <div className="h-1.5 bg-dock-100 rounded-full overflow-hidden">
            <div
              className={clsx("h-full rounded-full transition-all", confidenceBarColor)}
              style={{ width: `${finding.confidence * 100}%` }}
            />
          </div>
        </div>

        {/* Reviewer notes (if already reviewed) */}
        {finding.reviewer_notes && (
          <div className="bg-dock-50 rounded-lg p-2.5 text-xs text-dock-600">
            <span className="font-medium">Review note:</span>{" "}
            {finding.reviewer_notes}
          </div>
        )}

        {/* Correction form */}
        {showCorrectionForm && (
          <div className="border border-dock-200 rounded-lg p-3 space-y-3 bg-dock-50">
            <h5 className="text-xs font-semibold text-navy-800 uppercase tracking-wide">
              Correction Details
            </h5>

            {/* Severity */}
            <div>
              <label className="block text-xs font-medium text-dock-600 mb-1">
                Severity
              </label>
              <div className="flex flex-wrap gap-1">
                {SEVERITY_OPTIONS.map((sev) => (
                  <button
                    key={sev}
                    onClick={() => setCorrectedSeverity(sev)}
                    className={clsx(
                      "px-2.5 py-1 rounded-md text-xs font-medium border transition-colors",
                      correctedSeverity === sev
                        ? "border-navy-500 bg-navy-50 text-navy-700"
                        : "border-dock-200 bg-white text-dock-600 hover:border-dock-300",
                    )}
                  >
                    {sev}
                  </button>
                ))}
              </div>
            </div>

            {/* Damage type */}
            <div>
              <label className="block text-xs font-medium text-dock-600 mb-1">
                Damage Type
              </label>
              <select
                value={correctedType}
                onChange={(e) => setCorrectedType(e.target.value)}
                className="w-full px-2.5 py-1.5 text-sm border border-dock-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              >
                {DAMAGE_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {formatDamageType(type)}
                  </option>
                ))}
              </select>
            </div>

            {/* Location */}
            <div>
              <label className="block text-xs font-medium text-dock-600 mb-1">
                Location Description
              </label>
              <input
                type="text"
                value={correctedLocation}
                onChange={(e) => setCorrectedLocation(e.target.value)}
                className="w-full px-2.5 py-1.5 text-sm border border-dock-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
            </div>
          </div>
        )}

        {/* Notes */}
        {!isReviewed && (
          <div>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add review notes (optional)"
              className="w-full px-3 py-2 text-sm border border-dock-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              rows={2}
            />
          </div>
        )}

        {/* Action buttons */}
        {!isReviewed && (
          <div className="flex items-center gap-2 pt-1">
            <Button
              variant="primary"
              size="sm"
              onClick={handleConfirm}
              isLoading={isSubmitting}
              className="flex-1"
            >
              Confirm
            </Button>

            {showCorrectionForm ? (
              <Button
                variant="secondary"
                size="sm"
                onClick={handleCorrect}
                isLoading={isSubmitting}
                className="flex-1"
              >
                Submit Correction
              </Button>
            ) : (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowCorrectionForm(true)}
                className="flex-1"
              >
                Correct
              </Button>
            )}

            <Button
              variant="danger"
              size="sm"
              onClick={handleReject}
              isLoading={isSubmitting}
              className="flex-1"
            >
              Reject
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}
