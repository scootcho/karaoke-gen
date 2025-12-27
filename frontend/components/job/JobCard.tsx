"use client"

import { useState } from "react"
import { Job } from "@/lib/api"
import { useAutoMode } from "@/lib/auto-mode"
import { Button } from "@/components/ui/button"
import { Loader2, ExternalLink, Zap } from "lucide-react"
import { JobActions } from "./JobActions"
import { JobLogs } from "./JobLogs"
import { OutputLinks } from "./OutputLinks"
import { InstrumentalSelector } from "./InstrumentalSelector"
import { AudioSearchDialog } from "../audio-search/AudioSearchDialog"

// Status text styling (subtle colored text instead of badges)
const statusConfig: Record<string, { textColor: string; label: string }> = {
  pending: { textColor: "text-slate-400", label: "Pending" },
  searching_audio: { textColor: "text-blue-400", label: "Searching..." },
  awaiting_audio_selection: { textColor: "text-amber-400", label: "Needs audio" },
  downloading: { textColor: "text-blue-400", label: "Downloading..." },
  downloading_audio: { textColor: "text-blue-400", label: "Downloading..." },
  separating_stage1: { textColor: "text-purple-400", label: "Separating 1/2..." },
  separating_stage2: { textColor: "text-purple-400", label: "Separating 2/2..." },
  audio_complete: { textColor: "text-purple-400", label: "Audio ready" },
  transcribing: { textColor: "text-blue-400", label: "Transcribing..." },
  correcting: { textColor: "text-blue-400", label: "Correcting..." },
  lyrics_complete: { textColor: "text-teal-400", label: "Lyrics ready" },
  generating_screens: { textColor: "text-cyan-400", label: "Generating screens..." },
  awaiting_review: { textColor: "text-amber-400", label: "Needs review" },
  in_review: { textColor: "text-blue-400", label: "In review..." },
  review_complete: { textColor: "text-teal-400", label: "Review complete" },
  rendering_video: { textColor: "text-indigo-400", label: "Rendering..." },
  awaiting_instrumental_selection: { textColor: "text-amber-400", label: "Needs instrumental" },
  instrumental_selected: { textColor: "text-pink-400", label: "Instrumental selected" },
  generating_video: { textColor: "text-violet-400", label: "Generating video..." },
  encoding: { textColor: "text-violet-400", label: "Encoding..." },
  packaging: { textColor: "text-violet-400", label: "Packaging..." },
  uploading: { textColor: "text-green-400", label: "Uploading..." },
  complete: { textColor: "text-green-400", label: "Complete" },
  failed: { textColor: "text-red-400", label: "Failed" },
  cancelled: { textColor: "text-slate-500", label: "Cancelled" },
}

function StatusText({ status }: { status: string }) {
  const config = statusConfig[status] || { textColor: "text-slate-400", label: status }
  return <span className={config.textColor}>{config.label}</span>
}

interface JobCardProps {
  job: Job
  onRefresh: () => void
}

export function JobCard({ job, onRefresh }: JobCardProps) {
  const [showLogs, setShowLogs] = useState(false)
  const [showAudioSearch, setShowAudioSearch] = useState(false)
  const [showInstrumentalSelector, setShowInstrumentalSelector] = useState(false)
  const { enabled: autoModeEnabled, isProcessing: isAutoProcessing } = useAutoMode()

  const createdAt = new Date(job.created_at).toLocaleString()
  const isInteractive = job.status === "awaiting_review" ||
                        job.status === "in_review" ||
                        job.status === "awaiting_instrumental_selection" ||
                        job.status === "awaiting_audio_selection"
  const isComplete = job.status === "complete"
  const isFailed = job.status === "failed"
  const isProcessing = !isComplete && !isFailed && job.status !== "cancelled"

  // Check if this job is being auto-processed
  const isBeingAutoProcessed = autoModeEnabled && isInteractive && (
    isAutoProcessing(`${job.job_id}-review`) ||
    isAutoProcessing(`${job.job_id}-instrumental`) ||
    isAutoProcessing(`${job.job_id}-audio`)
  )

  // Build review URL for awaiting_review status
  const getReviewUrl = () => {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.nomadkaraoke.com'
    const reviewUiUrl = process.env.NEXT_PUBLIC_REVIEW_UI_URL || 'https://gen.nomadkaraoke.com/lyrics/'
    const baseApiUrl = `${backendUrl}/api/review/${job.job_id}`
    const encodedApiUrl = encodeURIComponent(baseApiUrl)
    let url = `${reviewUiUrl}/?baseApiUrl=${encodedApiUrl}`
    if (job.audio_hash) {
      url += `&audioHash=${encodeURIComponent(job.audio_hash)}`
    }
    if (job.review_token) {
      url += `&reviewToken=${encodeURIComponent(job.review_token)}`
    }
    return url
  }

  // Render primary action button based on status
  const renderPrimaryAction = () => {
    if (autoModeEnabled && isInteractive) {
      return (
        <div className="flex items-center gap-1 text-xs text-amber-400">
          {isBeingAutoProcessed ? (
            <>
              <Loader2 className="w-3 h-3 animate-spin" />
              Auto-processing...
            </>
          ) : (
            <>
              <Zap className="w-3 h-3" />
              Will auto-{job.status === "awaiting_review" || job.status === "in_review" ? "accept" :
                         job.status === "awaiting_instrumental_selection" ? "select clean" :
                         "select first"}
            </>
          )}
        </div>
      )
    }

    if (job.status === "awaiting_review" || job.status === "in_review") {
      return (
        <a
          href={getReviewUrl()}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white"
        >
          <ExternalLink className="w-3 h-3" />
          Review Lyrics
        </a>
      )
    }

    if (job.status === "awaiting_audio_selection") {
      return (
        <Button
          size="sm"
          onClick={() => setShowAudioSearch(true)}
          className="text-xs h-7 px-3 bg-blue-600 hover:bg-blue-500"
        >
          Select Audio
        </Button>
      )
    }

    if (job.status === "awaiting_instrumental_selection") {
      return (
        <Button
          size="sm"
          onClick={() => setShowInstrumentalSelector(true)}
          className="text-xs h-7 px-3 bg-blue-600 hover:bg-blue-500"
        >
          Select Instrumental
        </Button>
      )
    }

    return null
  }

  return (
    <div
      className={`rounded-lg border p-3 transition-colors border-slate-700 bg-slate-800/30
        ${isComplete ? "border-green-500/30" : ""}
        ${isFailed ? "border-red-500/30" : ""}`}
    >
      {/* Header row with title */}
      <p className="font-medium text-white truncate">
        {job.artist || "Unknown"} - {job.title || "Unknown"}
      </p>

      {/* Meta row: ID, date, status */}
      <p className="text-xs text-slate-500 mt-1">
        <span className="text-slate-600">ID:</span> {job.job_id} <span className="text-slate-600">•</span> {createdAt} <span className="text-slate-600">•</span> <StatusText status={job.status} />
      </p>

      {/* Error message if any */}
      {job.error_message && (
        <div className="mt-2 text-xs text-red-400 bg-red-500/10 rounded p-2 break-words">
          {job.error_message}
        </div>
      )}

      {/* Output links for completed jobs */}
      {isComplete && (
        <div className="mt-2">
          <OutputLinks jobId={job.job_id} />
        </div>
      )}

      {/* Actions row: Cancel/secondary on left, primary action on right */}
      <div className="mt-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <JobActions
            job={job}
            onRefresh={onRefresh}
            showLogs={showLogs}
            onToggleLogs={() => setShowLogs(!showLogs)}
          />
        </div>
        {renderPrimaryAction()}
      </div>

      {/* Expandable logs */}
      {showLogs && (
        <div className="mt-2">
          <JobLogs jobId={job.job_id} />
        </div>
      )}

      <AudioSearchDialog
        jobId={job.job_id}
        open={showAudioSearch}
        onClose={() => setShowAudioSearch(false)}
        onSelect={onRefresh}
      />

      <InstrumentalSelector
        jobId={job.job_id}
        open={showInstrumentalSelector}
        onClose={() => setShowInstrumentalSelector(false)}
        onSelect={onRefresh}
      />
    </div>
  )
}

