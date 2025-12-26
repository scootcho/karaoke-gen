"use client"

import { useEffect, useCallback, useRef } from "react"
import { api, Job } from "@/lib/api"
import { useAutoMode } from "@/lib/auto-mode"

interface AutoProcessorProps {
  /** List of jobs to monitor */
  jobs: Job[]
  /** Callback to refresh jobs list after auto-processing */
  onJobsChanged: () => void
}

/**
 * AutoProcessor component that automatically handles interactive states
 * when auto-mode is enabled.
 *
 * This is equivalent to the -y flag in karaoke-gen-remote CLI:
 * - Auto-completes lyrics review (accepts auto-corrected lyrics)
 * - Auto-selects "clean" instrumental
 * - Auto-selects first/best audio search result
 */
export function AutoProcessor({ jobs, onJobsChanged }: AutoProcessorProps) {
  const { enabled, markProcessing, unmarkProcessing, isProcessing } = useAutoMode()
  const processedRef = useRef<Set<string>>(new Set())

  const processJob = useCallback(async (job: Job, action: string) => {
    const processingKey = `${job.job_id}-${action}`

    // Skip if already being processed
    if (isProcessing(processingKey) || processedRef.current.has(processingKey)) {
      return
    }

    // Mark as processing
    markProcessing(processingKey)
    processedRef.current.add(processingKey)

    console.log(`[AutoProcessor] Auto-processing ${action} for job ${job.job_id}`)

    try {
      switch (action) {
        case 'review':
          // Auto-complete lyrics review
          await api.completeReview(job.job_id)
          console.log(`[AutoProcessor] Auto-completed review for job ${job.job_id}`)
          break

        case 'instrumental':
          // Auto-select "clean" instrumental
          await api.selectInstrumental(job.job_id, 'clean')
          console.log(`[AutoProcessor] Auto-selected clean instrumental for job ${job.job_id}`)
          break

        case 'audio':
          // Auto-select first audio search result (index 0)
          await api.selectAudioResult(job.job_id, 0)
          console.log(`[AutoProcessor] Auto-selected first audio result for job ${job.job_id}`)
          break
      }

      // Refresh jobs to reflect the change
      onJobsChanged()
    } catch (err) {
      console.error(`[AutoProcessor] Failed to auto-process ${action} for job ${job.job_id}:`, err)
      // Remove from processed so it can be retried
      processedRef.current.delete(processingKey)
    } finally {
      unmarkProcessing(processingKey)
    }
  }, [isProcessing, markProcessing, unmarkProcessing, onJobsChanged])

  useEffect(() => {
    if (!enabled) return

    // Find jobs that need auto-processing
    for (const job of jobs) {
      switch (job.status) {
        case 'awaiting_review':
          processJob(job, 'review')
          break
        case 'awaiting_instrumental_selection':
          processJob(job, 'instrumental')
          break
        case 'awaiting_audio_selection':
          processJob(job, 'audio')
          break
      }
    }
  }, [enabled, jobs, processJob])

  // This component doesn't render anything - it's purely for side effects
  return null
}
