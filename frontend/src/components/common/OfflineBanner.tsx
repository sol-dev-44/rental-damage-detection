import { useState, useEffect } from "react";
import clsx from "clsx";
import { getOfflineQueueCount, flushOfflineQueue } from "@/lib/api";

export function OfflineBanner() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [queueCount, setQueueCount] = useState(getOfflineQueueCount());
  const [isFlushing, setIsFlushing] = useState(false);

  useEffect(() => {
    function handleOnline() {
      setIsOnline(true);
      setQueueCount(getOfflineQueueCount());
    }
    function handleOffline() {
      setIsOnline(false);
    }

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    // Periodically check queue count
    const interval = setInterval(() => {
      setQueueCount(getOfflineQueueCount());
    }, 5000);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      clearInterval(interval);
    };
  }, []);

  async function handleRetry() {
    setIsFlushing(true);
    try {
      await flushOfflineQueue();
      setQueueCount(getOfflineQueueCount());
    } finally {
      setIsFlushing(false);
    }
  }

  // Nothing to show if online and no queued operations
  if (isOnline && queueCount === 0) {
    return null;
  }

  return (
    <div
      className={clsx(
        "px-4 py-2 text-sm font-medium flex items-center justify-between gap-3",
        !isOnline
          ? "bg-amber-50 text-amber-800 border-b border-amber-200"
          : "bg-marine-50 text-marine-800 border-b border-marine-200",
      )}
      role="alert"
    >
      <div className="flex items-center gap-2">
        {!isOnline ? (
          <>
            <svg
              className="w-4 h-4 flex-shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M18.364 5.636a9 9 0 11-12.728 0M12 9v4m0 4h.01"
              />
            </svg>
            <span>
              You are offline.
              {queueCount > 0 && (
                <span className="ml-1">
                  {queueCount} operation{queueCount !== 1 ? "s" : ""} queued.
                </span>
              )}
            </span>
          </>
        ) : (
          <>
            <svg
              className="w-4 h-4 flex-shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            <span>
              Back online. {queueCount} queued operation
              {queueCount !== 1 ? "s" : ""} pending.
            </span>
          </>
        )}
      </div>

      {isOnline && queueCount > 0 && (
        <button
          onClick={() => void handleRetry()}
          disabled={isFlushing}
          className={clsx(
            "px-3 py-1 rounded-md text-xs font-semibold",
            "bg-marine-600 text-white hover:bg-marine-700",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            "transition-colors",
          )}
        >
          {isFlushing ? "Syncing..." : "Sync now"}
        </button>
      )}
    </div>
  );
}
