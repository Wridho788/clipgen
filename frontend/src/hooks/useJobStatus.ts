import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { JobResponse } from "@/types/api";
import { isTerminalJobStatus } from "@/lib/status";

export function useJobStatus(jobId: string | undefined) {
  const query = useQuery<JobResponse>({
    queryKey: ["job", jobId],
    queryFn: () => api.getJobStatus(jobId as string),
    enabled: !!jobId,
    refetchIntervalInBackground: true,
    refetchOnReconnect: true,
    refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      // Stop polling begitu job selesai/gagal/cancelled
      const data = query.state.data;
      if (isTerminalJobStatus(data?.status)) return false;
      return 2000; // poll tiap 2 detik selama masih processing
    },
  });
  const currentStatus = query.data?.status;
  const refetch = query.refetch;

  useEffect(() => {
    if (!jobId || typeof document === "undefined") return;

    const refetchWhenVisible = () => {
      if (!document.hidden && !isTerminalJobStatus(currentStatus)) {
        refetch();
      }
    };

    document.addEventListener("visibilitychange", refetchWhenVisible);
    window.addEventListener("focus", refetchWhenVisible);
    return () => {
      document.removeEventListener("visibilitychange", refetchWhenVisible);
      window.removeEventListener("focus", refetchWhenVisible);
    };
  }, [currentStatus, jobId, refetch]);

  return query;
}
