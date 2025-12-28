"use client"

import { useState } from "react"
import { Job, api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { 
  Loader2, RotateCcw, XCircle, Trash2, FileText
} from "lucide-react"

interface JobActionsProps {
  job: Job
  onRefresh: () => void
  showLogs: boolean
  onToggleLogs: () => void
}

export function JobActions({ job, onRefresh, showLogs, onToggleLogs }: JobActionsProps) {
  const [isRetrying, setIsRetrying] = useState(false)
  const [isCancelling, setIsCancelling] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  const canRetry = job.status === "failed" || job.status === "cancelled"
  const canCancel = !["complete", "failed", "cancelled"].includes(job.status)
  const canDelete = ["complete", "failed", "cancelled"].includes(job.status)

  async function handleRetry() {
    setIsRetrying(true)
    try {
      await api.retryJob(job.job_id)
      onRefresh()
    } catch (error) {
      console.error("Failed to retry job:", error)
    } finally {
      setIsRetrying(false)
    }
  }

  async function handleCancel() {
    if (!confirm("Are you sure you want to cancel this job?")) return
    
    setIsCancelling(true)
    try {
      await api.cancelJob(job.job_id)
      onRefresh()
    } catch (error) {
      console.error("Failed to cancel job:", error)
    } finally {
      setIsCancelling(false)
    }
  }

  async function handleDelete() {
    if (!confirm("Are you sure you want to delete this job? This will remove all associated files.")) return
    
    setIsDeleting(true)
    try {
      await api.deleteJob(job.job_id, true)
      onRefresh()
    } catch (error) {
      console.error("Failed to delete job:", error)
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <div className="flex flex-wrap gap-2" onClick={(e) => e.stopPropagation()}>
      {/* Cancel button first (red) */}
      {canCancel && (
        <Button
          size="sm"
          variant="ghost"
          onClick={handleCancel}
          disabled={isCancelling}
          className="text-xs text-red-400 hover:text-red-300"
        >
          {isCancelling ? (
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
          ) : (
            <XCircle className="w-3 h-3 mr-1" />
          )}
          Cancel
        </Button>
      )}

      {/* Delete button (red) */}
      {canDelete && (
        <Button
          size="sm"
          variant="ghost"
          onClick={handleDelete}
          disabled={isDeleting}
          className="text-xs text-red-400 hover:text-red-300"
        >
          {isDeleting ? (
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
          ) : (
            <Trash2 className="w-3 h-3 mr-1" />
          )}
          Delete
        </Button>
      )}

      {/* Retry button */}
      {canRetry && (
        <Button
          size="sm"
          variant="ghost"
          onClick={handleRetry}
          disabled={isRetrying}
          className="text-xs text-blue-400 hover:text-blue-300"
        >
          {isRetrying ? (
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
          ) : (
            <RotateCcw className="w-3 h-3 mr-1" />
          )}
          Retry
        </Button>
      )}

      {/* Show/Hide Logs */}
      <Button
        size="sm"
        variant="ghost"
        onClick={onToggleLogs}
        className="text-xs"
        style={{ color: 'var(--text-muted)' }}
      >
        <FileText className="w-3 h-3 mr-1" />
        {showLogs ? "Hide" : "Show"} Logs
      </Button>
    </div>
  )
}

