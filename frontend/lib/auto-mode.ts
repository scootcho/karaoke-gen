/**
 * Auto-mode state management for non-interactive processing.
 *
 * When auto-mode is enabled (via ?auto=true URL parameter or UI toggle),
 * the frontend automatically:
 * - Completes lyrics review without human intervention
 * - Selects "clean" instrumental automatically
 * - Selects the first/best audio search result automatically
 *
 * This is equivalent to the -y flag in karaoke-gen-remote CLI.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AutoModeState {
  /** Whether auto-mode is enabled */
  enabled: boolean
  /** Jobs currently being auto-processed (to prevent duplicate processing) */
  processingJobs: Set<string>
  /** Enable auto-mode */
  enable: () => void
  /** Disable auto-mode */
  disable: () => void
  /** Toggle auto-mode */
  toggle: () => void
  /** Set auto-mode state directly */
  setEnabled: (enabled: boolean) => void
  /** Mark a job as being processed */
  markProcessing: (jobId: string) => void
  /** Unmark a job as being processed */
  unmarkProcessing: (jobId: string) => void
  /** Check if a job is currently being processed */
  isProcessing: (jobId: string) => boolean
}

export const useAutoMode = create<AutoModeState>()(
  persist(
    (set, get) => ({
      enabled: false,
      processingJobs: new Set<string>(),

      enable: () => set({ enabled: true }),
      disable: () => set({ enabled: false }),
      toggle: () => set((state) => ({ enabled: !state.enabled })),
      setEnabled: (enabled: boolean) => set({ enabled }),

      markProcessing: (jobId: string) => set((state) => {
        const newSet = new Set(state.processingJobs)
        newSet.add(jobId)
        return { processingJobs: newSet }
      }),

      unmarkProcessing: (jobId: string) => set((state) => {
        const newSet = new Set(state.processingJobs)
        newSet.delete(jobId)
        return { processingJobs: newSet }
      }),

      isProcessing: (jobId: string) => get().processingJobs.has(jobId),
    }),
    {
      name: 'karaoke-auto-mode',
      // Only persist the enabled state, not the processing jobs
      partialize: (state) => ({ enabled: state.enabled }),
    }
  )
)

/**
 * Check URL for auto-mode parameter.
 * Returns true if ?auto=true or ?auto=1 is in the URL.
 */
export function getAutoModeFromUrl(): boolean {
  if (typeof window === 'undefined') return false

  const params = new URLSearchParams(window.location.search)
  const autoParam = params.get('auto')
  return autoParam === 'true' || autoParam === '1'
}
