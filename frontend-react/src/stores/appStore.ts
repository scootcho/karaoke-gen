/**
 * Global application store using Zustand
 */
import { create } from 'zustand';

interface AppState {
  currentJobId: string | null;
  setCurrentJobId: (jobId: string | null) => void;
  
  isUploadMode: boolean;
  setUploadMode: (mode: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentJobId: null,
  setCurrentJobId: (jobId) => set({ currentJobId: jobId }),
  
  isUploadMode: false,
  setUploadMode: (mode) => set({ isUploadMode: mode }),
}));

