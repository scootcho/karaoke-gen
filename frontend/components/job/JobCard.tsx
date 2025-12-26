"use client"

import { useState } from "react"
import { Job } from "@/lib/api"
import { useAutoMode } from "@/lib/auto-mode"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Loader2, CheckCircle2, XCircle, Clock, AlertCircle,
  ChevronDown, ChevronUp, ExternalLink, Zap
} from "lucide-react"
import { JobActions } from "./JobActions"
import { JobLogs } from "./JobLogs"
import { OutputLinks } from "./OutputLinks"
import { InstrumentalSelector } from "./InstrumentalSelector"
import { AudioSearchDialog } from "../audio-search/AudioSearchDialog"

// Status badge styling
const statusConfig: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  pending: { color: "bg-slate-500", icon: <Clock className="w-3 h-3" />, label: "Pending" },
  searching_audio: { color: "bg-blue-500", icon: <Loader2 className="w-3 h-3 animate-spin" />, label: "Searching Audio" },
  awaiting_audio_selection: { color: "bg-orange-500", icon: <AlertCircle className="w-3 h-3" />, label: "Select Audio" },
  downloading: { color: "bg-blue-500", icon: <Loader2 className="w-3 h-3 animate-spin" />, label: "Downloading" },
  downloading_audio: { color: "bg-blue-500", icon: <Loader2 className="w-3 h-3 animate-spin" />, label: "Downloading" },
  separating_stage1: { color: "bg-purple-500", icon: <Loader2 className="w-3 h-3 animate-spin" />, label: "Separating (1/2)" },
  separating_stage2: { color: "bg-purple-500", icon: <Loader2 className="w-3 h-3 animate-spin" />, label: "Separating (2/2)" },
  audio_complete: { color: "bg-purple-600", icon: <CheckCircle2 className="w-3 h-3" />, label: "Audio Ready" },
  transcribing: { color: "bg-amber-500", icon: <Loader2 className="w-3 h-3 animate-spin" />, label: "Transcribing" },
  correcting: { color: "bg-amber-500", icon: <Loader2 className="w-3 h-3 animate-spin" />, label: "Correcting" },
  lyrics_complete: { color: "bg-amber-600", icon: <CheckCircle2 className="w-3 h-3" />, label: "Lyrics Ready" },
  generating_screens: { color: "bg-cyan-500", icon: <Loader2 className="w-3 h-3 animate-spin" />, label: "Generating Screens" },
  awaiting_review: { color: "bg-orange-500", icon: <AlertCircle className="w-3 h-3" />, label: "Awaiting Review" },
  in_review: { color: "bg-orange-600", icon: <Loader2 className="w-3 h-3 animate-spin" />, label: "In Review" },
  review_complete: { color: "bg-teal-500", icon: <CheckCircle2 className="w-3 h-3" />, label: "Review Complete" },
  rendering_video: { color: "bg-indigo-500", icon: <Loader2 className="w-3 h-3 animate-spin" />, label: "Rendering Video" },
  awaiting_instrumental_selection: { color: "bg-pink-500", icon: <AlertCircle className="w-3 h-3" />, label: "Select Instrumental" },
  instrumental_selected: { color: "bg-pink-600", icon: <CheckCircle2 className="w-3 h-3" />, label: "Instrumental Selected" },
  generating_video: { color: "bg-violet-500", icon: <Loader2 className="w-3 h-3 animate-spin" />, label: "Generating Video" },
  encoding: { color: "bg-violet-600", icon: <Loader2 className="w-3 h-3 animate-spin" />, label: "Encoding" },
  packaging: { color: "bg-violet-700", icon: <Loader2 className="w-3 h-3 animate-spin" />, label: "Packaging" },
  uploading: { color: "bg-green-500", icon: <Loader2 className="w-3 h-3 animate-spin" />, label: "Uploading" },
  complete: { color: "bg-green-600", icon: <CheckCircle2 className="w-3 h-3" />, label: "Complete" },
  failed: { color: "bg-red-600", icon: <XCircle className="w-3 h-3" />, label: "Failed" },
  cancelled: { color: "bg-gray-500", icon: <XCircle className="w-3 h-3" />, label: "Cancelled" },
}

export function StatusBadge({ status }: { status: string }) {
  const config = statusConfig[status] || { color: "bg-gray-500", icon: <Clock className="w-3 h-3" />, label: status }
  return (
    <Badge className={`${config.color} text-white gap-1`}>
      {config.icon}
      {config.label}
    </Badge>
  )
}

interface JobCardProps {
  job: Job
  onRefresh: () => void
}

export function JobCard({ job, onRefresh }: JobCardProps) {
  const [showDetails, setShowDetails] = useState(false)
  const [showLogs, setShowLogs] = useState(false)
  const [showAudioSearch, setShowAudioSearch] = useState(false)
  const [showInstrumentalSelector, setShowInstrumentalSelector] = useState(false)
  const { enabled: autoModeEnabled, isProcessing: isAutoProcessing } = useAutoMode()

  const createdAt = new Date(job.created_at).toLocaleString()
  const isInteractive = job.status === "awaiting_review" ||
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

  return (
    <div 
      className={`rounded-lg border p-3 transition-colors
        ${isInteractive ? "border-orange-500/50 bg-orange-500/5" : "border-slate-700 bg-slate-800/30"}
        ${isComplete ? "border-green-500/30" : ""}
        ${isFailed ? "border-red-500/30" : ""}`}
    >
      <div 
        className="flex items-start justify-between gap-3 cursor-pointer"
        onClick={() => setShowDetails(!showDetails)}
      >
        <div className="flex-1 min-w-0">
          <p className="font-medium text-white truncate">
            {job.artist || "Unknown"} - {job.title || "Unknown"}
          </p>
          <p className="text-xs text-slate-500 mt-1">{createdAt}</p>
          {job.progress > 0 && job.progress < 100 && isProcessing && (
            <div className="mt-2 h-1 rounded-full bg-slate-700 overflow-hidden">
              <div 
                className="h-full bg-amber-500 transition-all duration-500"
                style={{ width: `${job.progress}%` }}
              />
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={job.status} />
          {showDetails ? (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          )}
        </div>
      </div>

      {showDetails && (
        <div className="mt-3 pt-3 border-t border-slate-700 space-y-3">
          <p className="text-xs text-slate-400">
            <span className="text-slate-500">Job ID:</span> {job.job_id}
          </p>
          
          {job.error_message && (
            <div className="text-xs text-red-400 bg-red-500/10 rounded p-2 break-words">
              {job.error_message}
            </div>
          )}

          {isInteractive && (
            <div className="flex flex-wrap gap-2">
              {autoModeEnabled ? (
                // Auto-mode indicator
                <div className="flex items-center gap-2 text-xs text-amber-400 bg-amber-500/10 px-3 py-1.5 rounded">
                  {isBeingAutoProcessed ? (
                    <>
                      <Loader2 className="w-3 h-3 animate-spin" />
                      Auto-processing...
                    </>
                  ) : (
                    <>
                      <Zap className="w-3 h-3" />
                      Will auto-{job.status === "awaiting_review" ? "accept" :
                                 job.status === "awaiting_instrumental_selection" ? "select clean" :
                                 "select first"}
                    </>
                  )}
                </div>
              ) : (
                <>
                  {job.status === "awaiting_review" && (
                    <a
                      href={`https://lyrics.nomadkaraoke.com/?job=${job.job_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded bg-orange-600 hover:bg-orange-500 text-white"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <ExternalLink className="w-3 h-3" />
                      Review Lyrics
                    </a>
                  )}
                  {job.status === "awaiting_audio_selection" && (
                    <Button
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        setShowAudioSearch(true)
                      }}
                      className="text-xs bg-blue-600 hover:bg-blue-500"
                    >
                      Select Audio Source
                    </Button>
                  )}
                  {job.status === "awaiting_instrumental_selection" && (
                    <Button
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        setShowInstrumentalSelector(true)
                      }}
                      className="text-xs bg-pink-600 hover:bg-pink-500"
                    >
                      Select Instrumental
                    </Button>
                  )}
                </>
              )}
            </div>
          )}

          {isComplete && (
            <OutputLinks jobId={job.job_id} />
          )}

          <JobActions 
            job={job} 
            onRefresh={onRefresh} 
            showLogs={showLogs}
            onToggleLogs={() => setShowLogs(!showLogs)}
          />

          {showLogs && (
            <JobLogs jobId={job.job_id} />
          )}
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

