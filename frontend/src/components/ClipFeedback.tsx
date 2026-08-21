"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, ThumbsDown, ThumbsUp } from "lucide-react";
import { api } from "@/lib/api";

export function ClipFeedback({ clipId }: { clipId: string }) {
  const queryClient = useQueryClient();
  const feedback = useQuery({
    queryKey: ["clip-feedback", clipId],
    queryFn: () => api.getClipFeedback(clipId),
  });
  const rate = useMutation({
    mutationFn: (rating: -1 | 1) => api.rateClip(clipId, rating),
    onSuccess: (data) => {
      queryClient.setQueryData(["clip-feedback", clipId], data);
    },
  });

  const activeRating = feedback.data?.rating;
  return (
    <div className="flex items-center gap-1 border-l border-slate-200 pl-2 dark:border-slate-700">
      <button
        type="button"
        onClick={() => rate.mutate(1)}
        disabled={rate.isPending}
        aria-pressed={activeRating === 1}
        aria-label="Klip relevan"
        title="Klip relevan"
        className={`inline-flex h-9 w-9 items-center justify-center border transition disabled:opacity-60 ${
          activeRating === 1
            ? "border-emerald-500 bg-emerald-50 text-emerald-700 dark:border-emerald-300 dark:bg-emerald-300/10 dark:text-emerald-200"
            : "border-slate-300 bg-white text-slate-600 hover:border-emerald-500 hover:text-emerald-700 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300"
        }`}
      >
        {rate.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ThumbsUp className="h-4 w-4" />}
      </button>
      <button
        type="button"
        onClick={() => rate.mutate(-1)}
        disabled={rate.isPending}
        aria-pressed={activeRating === -1}
        aria-label="Klip tidak relevan"
        title="Klip tidak relevan"
        className={`inline-flex h-9 w-9 items-center justify-center border transition disabled:opacity-60 ${
          activeRating === -1
            ? "border-rose-500 bg-rose-50 text-rose-700 dark:border-rose-300 dark:bg-rose-300/10 dark:text-rose-200"
            : "border-slate-300 bg-white text-slate-600 hover:border-rose-500 hover:text-rose-700 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300"
        }`}
      >
        <ThumbsDown className="h-4 w-4" />
      </button>
      {feedback.data && (
        <span className="ml-1 text-xs tabular-nums text-slate-500 dark:text-slate-400">
          {feedback.data.positive_count}/{feedback.data.negative_count}
        </span>
      )}
    </div>
  );
}
