import { create } from "zustand";

interface VideoUIState {
  // UI state saja — data dari server (jobs, clips) dikelola TanStack Query, bukan di sini
  selectedClipId: string | null;
  setSelectedClipId: (id: string | null) => void;

  isUploadModalOpen: boolean;
  setUploadModalOpen: (open: boolean) => void;
}

export const useVideoUIStore = create<VideoUIState>((set) => ({
  selectedClipId: null,
  setSelectedClipId: (id) => set({ selectedClipId: id }),

  isUploadModalOpen: false,
  setUploadModalOpen: (open) => set({ isUploadModalOpen: open }),
}));
