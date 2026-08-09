import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ClipResponse, ClipUpdateRequest } from "@/types/api";

export function useClips(jobId: string | undefined, jobStatus: string | undefined) {
  return useQuery<ClipResponse[]>({
    queryKey: ["clips", jobId],
    queryFn: () => api.getClipsByJob(jobId as string),
    enabled: !!jobId && jobStatus === "done",
  });
}

export function useUpdateClip(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ clipId, data }: { clipId: string; data: ClipUpdateRequest }) =>
      api.updateClip(clipId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clips", jobId] });
    },
  });
}

export function useDeleteClip(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (clipId: string) => api.deleteClip(clipId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clips", jobId] });
    },
  });
}
