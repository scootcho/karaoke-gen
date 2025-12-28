"use client"

import { useEffect, useRef, useCallback } from 'react'
import type { Job } from '@/lib/api'
import { isBlockingStatus } from '@/lib/job-status'

const TITLE_FLASH_INTERVAL = 1000 // ms between title flashes
const DEFAULT_TITLE = 'Karaoke Generator'

type NotificationReason = 'action_needed' | 'complete' | 'failed'

interface NotificationState {
  jobId: string
  status: string
}

/**
 * Creates a notification sound using Web Audio API.
 * Returns a function that plays the sound when called.
 */
function createNotificationSound(): () => void {
  let audioContext: AudioContext | null = null

  return () => {
    try {
      // Create or reuse AudioContext (lazy init for browser compatibility)
      if (!audioContext) {
        audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
      }

      // Resume context if suspended (browsers require user interaction)
      if (audioContext.state === 'suspended') {
        audioContext.resume()
      }

      const now = audioContext.currentTime

      // Create a pleasant two-tone notification sound
      const oscillator1 = audioContext.createOscillator()
      const oscillator2 = audioContext.createOscillator()
      const gainNode = audioContext.createGain()

      oscillator1.connect(gainNode)
      oscillator2.connect(gainNode)
      gainNode.connect(audioContext.destination)

      // First tone - higher frequency
      oscillator1.frequency.setValueAtTime(880, now) // A5
      oscillator1.type = 'sine'

      // Second tone - lower frequency (harmony)
      oscillator2.frequency.setValueAtTime(659.25, now) // E5
      oscillator2.type = 'sine'

      // Envelope: quick attack, short sustain, fade out
      gainNode.gain.setValueAtTime(0, now)
      gainNode.gain.linearRampToValueAtTime(0.3, now + 0.02) // Quick attack
      gainNode.gain.setValueAtTime(0.3, now + 0.1) // Sustain
      gainNode.gain.linearRampToValueAtTime(0, now + 0.3) // Fade out

      oscillator1.start(now)
      oscillator2.start(now)
      oscillator1.stop(now + 0.3)
      oscillator2.stop(now + 0.3)
    } catch (error) {
      // Silently fail - notifications are non-critical
      console.debug('Notification sound failed:', error)
    }
  }
}

/**
 * Hook to manage browser notifications for job status changes.
 * Handles sound alerts and title bar animations when user attention is needed.
 *
 * @param jobs - Current list of jobs from the API
 */
export function useJobNotifications(jobs: Job[]) {
  const previousStatesRef = useRef<Map<string, NotificationState>>(new Map())
  const titleIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const originalTitleRef = useRef<string>(DEFAULT_TITLE)
  const playSoundRef = useRef<() => void>(createNotificationSound())
  const isFlashingRef = useRef<boolean>(false)
  const hasInteractedRef = useRef<boolean>(false)

  // Track user interaction to enable sounds (browser requirement)
  useEffect(() => {
    const markInteracted = () => {
      hasInteractedRef.current = true
    }

    // Listen for any user interaction
    document.addEventListener('click', markInteracted, { once: true })
    document.addEventListener('keydown', markInteracted, { once: true })

    return () => {
      document.removeEventListener('click', markInteracted)
      document.removeEventListener('keydown', markInteracted)
    }
  }, [])

  /**
   * Start flashing the document title to attract attention.
   */
  const startTitleFlash = useCallback((message: string) => {
    // Don't start if already flashing
    if (isFlashingRef.current) return

    isFlashingRef.current = true
    originalTitleRef.current = document.title
    let showMessage = true

    titleIntervalRef.current = setInterval(() => {
      document.title = showMessage ? message : originalTitleRef.current
      showMessage = !showMessage
    }, TITLE_FLASH_INTERVAL)
  }, [])

  /**
   * Stop the title flash animation.
   */
  const stopTitleFlash = useCallback(() => {
    if (titleIntervalRef.current) {
      clearInterval(titleIntervalRef.current)
      titleIntervalRef.current = null
    }
    isFlashingRef.current = false
    document.title = originalTitleRef.current || DEFAULT_TITLE
  }, [])

  /**
   * Trigger a notification with sound and optional title flash.
   */
  const notify = useCallback((reason: NotificationReason, jobTitle?: string) => {
    // Play sound if user has interacted with the page
    if (hasInteractedRef.current) {
      playSoundRef.current()
    }

    // Start title flash based on notification type
    const displayTitle = jobTitle ? `${jobTitle} - ` : ''
    switch (reason) {
      case 'action_needed':
        startTitleFlash(`${displayTitle}Action Needed`)
        break
      case 'complete':
        startTitleFlash(`${displayTitle}Complete!`)
        break
      case 'failed':
        startTitleFlash(`${displayTitle}Failed`)
        break
    }
  }, [startTitleFlash])

  // Stop title flash when page becomes visible (user returned)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && isFlashingRef.current) {
        stopTitleFlash()
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [stopTitleFlash])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopTitleFlash()
    }
  }, [stopTitleFlash])

  // Watch for job status changes that require notifications
  useEffect(() => {
    const currentStates = new Map<string, NotificationState>()

    for (const job of jobs) {
      const previousState = previousStatesRef.current.get(job.job_id)
      const currentStatus = job.status

      currentStates.set(job.job_id, {
        jobId: job.job_id,
        status: currentStatus,
      })

      // Skip if this is the first time we're seeing this job or status hasn't changed
      if (!previousState || previousState.status === currentStatus) {
        continue
      }

      const jobTitle = job.artist && job.title
        ? `${job.artist} - ${job.title}`
        : undefined

      // Check for status transitions that need notifications
      const wasBlocking = isBlockingStatus(previousState.status)
      const isNowBlocking = isBlockingStatus(currentStatus)

      // Notify when entering a blocking state (from non-blocking)
      if (!wasBlocking && isNowBlocking) {
        notify('action_needed', jobTitle)
      }

      // Notify when job completes
      if (currentStatus === 'complete' || currentStatus === 'prep_complete') {
        notify('complete', jobTitle)
      }

      // Notify when job fails
      if (currentStatus === 'failed') {
        notify('failed', jobTitle)
      }
    }

    // Update previous states reference
    previousStatesRef.current = currentStates
  }, [jobs, notify])

  return {
    stopTitleFlash,
  }
}

/**
 * Hook to refresh jobs when the page becomes visible.
 * This ensures the UI updates immediately when returning from review/instrumental UIs.
 *
 * @param loadJobs - Function to refresh the jobs list
 * @param isAuthenticated - Whether the user is authenticated
 */
export function useVisibilityRefresh(loadJobs: () => void, isAuthenticated: boolean) {
  const lastVisibleTimeRef = useRef<number>(Date.now())

  useEffect(() => {
    if (!isAuthenticated) return

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        const timeSinceLastVisible = Date.now() - lastVisibleTimeRef.current

        // Refresh if we were hidden for at least 1 second
        // This catches returning from review UIs while avoiding unnecessary refreshes
        if (timeSinceLastVisible > 1000) {
          loadJobs()
        }
      } else {
        lastVisibleTimeRef.current = Date.now()
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [loadJobs, isAuthenticated])
}
