import { useState, useEffect, useCallback, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getDetectionStatus } from "@/lib/api";
import type { DetectionResponse, Finding } from "@/lib/types";
import { inspectionKeys } from "./useInspection";

interface UseDamageDetectionOptions {
  pollInterval?: number;
  timeout?: number;
}

interface UseDamageDetectionReturn {
  status: DetectionResponse["status"] | "idle" | "timed_out";
  findings: Finding[];
  findingsCount: number | null;
  error: string | null;
  isPolling: boolean;
  startPolling: (jobId: string, inspectionId: string) => void;
  stopPolling: () => void;
  reset: () => void;
}

export function useDamageDetection(
  options: UseDamageDetectionOptions = {},
): UseDamageDetectionReturn {
  const { pollInterval = 2000, timeout = 120000 } = options;

  const queryClient = useQueryClient();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inspectionIdRef = useRef<string | null>(null);

  const [status, setStatus] = useState<
    DetectionResponse["status"] | "idle" | "timed_out"
  >("idle");
  const [findings, setFindings] = useState<Finding[]>([]);
  const [findingsCount, setFindingsCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  const cleanup = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setIsPolling(false);
  }, []);

  const stopPolling = useCallback(() => {
    cleanup();
  }, [cleanup]);

  const startPolling = useCallback(
    (jobId: string, inspectionId: string) => {
      cleanup();
      setStatus("queued");
      setError(null);
      setFindings([]);
      setFindingsCount(null);
      setIsPolling(true);
      inspectionIdRef.current = inspectionId;

      // Set up timeout
      timeoutRef.current = setTimeout(() => {
        cleanup();
        setStatus("timed_out");
        setError("Detection timed out. Please try again.");
      }, timeout);

      // Poll for status
      const poll = async () => {
        try {
          const response = await getDetectionStatus(jobId);
          setStatus(response.status);
          setFindingsCount(response.findings_count);

          if (response.status === "completed") {
            cleanup();
            // Invalidate the inspection query to fetch updated findings
            if (inspectionIdRef.current) {
              void queryClient.invalidateQueries({
                queryKey: inspectionKeys.detail(inspectionIdRef.current),
              });
            }
          } else if (response.status === "failed") {
            cleanup();
            setError(
              response.error_message ?? "Detection failed. Please try again.",
            );
          }
        } catch (err) {
          // Don't stop polling on network errors -- might be temporary
          if (!navigator.onLine) {
            // Pause polling, will resume when back online
            cleanup();
            setError("You are offline. Detection will resume when reconnected.");
          }
        }
      };

      // Initial poll
      void poll();

      // Set up interval
      intervalRef.current = setInterval(() => {
        void poll();
      }, pollInterval);
    },
    [cleanup, pollInterval, timeout, queryClient],
  );

  const reset = useCallback(() => {
    cleanup();
    setStatus("idle");
    setFindings([]);
    setFindingsCount(null);
    setError(null);
    inspectionIdRef.current = null;
  }, [cleanup]);

  // Cleanup on unmount
  useEffect(() => {
    return cleanup;
  }, [cleanup]);

  return {
    status,
    findings,
    findingsCount,
    error,
    isPolling,
    startPolling,
    stopPolling,
    reset,
  };
}
