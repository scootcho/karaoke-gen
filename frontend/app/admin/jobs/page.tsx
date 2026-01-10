"use client"

import { useEffect, useState, useCallback, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { adminApi, api, Job, FileInfo, JobFilesResponse, JobUpdateRequest, JobResetResponse, DeleteOutputsResponse } from "@/lib/api"
import { useAdminSettings } from "@/lib/admin-settings"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  Search,
  RefreshCw,
  Loader2,
  Trash2,
  ExternalLink,
  ArrowLeft,
  User,
  Clock,
  FileText,
  XCircle,
  Globe,
  Upload,
  Download,
  FolderOpen,
  Pencil,
  Check,
  X,
  Settings,
  RotateCcw,
  Wrench,
  CloudOff,
} from "lucide-react"
import { useToast } from "@/hooks/use-toast"

const statusOptions = [
  { value: "all", label: "All Statuses" },
  { value: "pending", label: "Pending" },
  { value: "downloading", label: "Downloading" },
  { value: "searching_audio", label: "Searching Audio" },
  { value: "awaiting_audio_selection", label: "Awaiting Audio Selection" },
  { value: "separating_stage1", label: "Separating (Stage 1)" },
  { value: "separating_stage2", label: "Separating (Stage 2)" },
  { value: "transcribing", label: "Transcribing" },
  { value: "correcting", label: "Correcting" },
  { value: "awaiting_review", label: "Awaiting Review" },
  { value: "in_review", label: "In Review" },
  { value: "rendering_video", label: "Rendering Video" },
  { value: "awaiting_instrumental_selection", label: "Awaiting Instrumental" },
  { value: "generating_video", label: "Generating Video" },
  { value: "encoding", label: "Encoding" },
  { value: "complete", label: "Complete" },
  { value: "prep_complete", label: "Prep Complete" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
]

// Inner component that uses useSearchParams
function AdminJobsPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { toast } = useToast()
  const { showTestData } = useAdminSettings()

  // Get jobId from query params for detail view
  const selectedJobId = searchParams.get("id")

  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState("all")
  const [userEmailFilter, setUserEmailFilter] = useState("")
  const [searchInput, setSearchInput] = useState("")

  // Detail view state
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const [logs, setLogs] = useState<any[]>([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [logsLoading, setLogsLoading] = useState(false)
  const [files, setFiles] = useState<FileInfo[]>([])
  const [filesLoading, setFilesLoading] = useState(false)

  // Delete dialog
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [jobToDelete, setJobToDelete] = useState<Job | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Editing state
  const [editingField, setEditingField] = useState<string | null>(null)
  const [editValue, setEditValue] = useState("")
  const [saving, setSaving] = useState(false)

  // Reset state
  const [resetDialogOpen, setResetDialogOpen] = useState(false)
  const [resetTarget, setResetTarget] = useState<string | null>(null)
  const [resetting, setResetting] = useState(false)

  // Delete outputs state
  const [deleteOutputsDialogOpen, setDeleteOutputsDialogOpen] = useState(false)
  const [deletingOutputs, setDeletingOutputs] = useState(false)

  const loadJobs = useCallback(async () => {
    try {
      setLoading(true)
      const data = await adminApi.listAllJobs({
        status: statusFilter !== "all" ? statusFilter : undefined,
        user_email: userEmailFilter || undefined,
        limit: 100,
        exclude_test: !showTestData,
      })
      setJobs(data)
    } catch (err: any) {
      console.error("Failed to load jobs:", err)
      toast({
        title: "Error",
        description: err.message || "Failed to load jobs",
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }, [statusFilter, userEmailFilter, showTestData, toast])

  const loadJobDetail = useCallback(async (jobId: string) => {
    try {
      setDetailLoading(true)
      const data = await api.getJob(jobId)
      setSelectedJob(data)
    } catch (err: any) {
      console.error("Failed to load job:", err)
      toast({
        title: "Error",
        description: err.message || "Failed to load job",
        variant: "destructive",
      })
      setSelectedJob(null)
    } finally {
      setDetailLoading(false)
    }
  }, [toast])

  const loadLogs = useCallback(async (jobId: string) => {
    try {
      setLogsLoading(true)
      const data = await api.getJobLogs(jobId, 200)
      setLogs(data)
    } catch (err: any) {
      console.error("Failed to load logs:", err)
    } finally {
      setLogsLoading(false)
    }
  }, [])

  const loadFiles = useCallback(async (jobId: string) => {
    try {
      setFilesLoading(true)
      const data = await adminApi.getJobFiles(jobId)
      setFiles(data.files)
    } catch (err: any) {
      console.error("Failed to load files:", err)
      setFiles([])
    } finally {
      setFilesLoading(false)
    }
  }, [])

  useEffect(() => {
    loadJobs()
  }, [loadJobs])

  useEffect(() => {
    if (selectedJobId) {
      loadJobDetail(selectedJobId)
      loadLogs(selectedJobId)
      loadFiles(selectedJobId)
    } else {
      setSelectedJob(null)
      setLogs([])
      setFiles([])
    }
  }, [selectedJobId, loadJobDetail, loadLogs, loadFiles])

  const handleSearch = () => {
    setUserEmailFilter(searchInput)
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSearch()
    }
  }

  // Start editing a field
  const startEditing = (field: string, currentValue: string) => {
    setEditingField(field)
    setEditValue(currentValue || "")
  }

  // Cancel editing
  const cancelEditing = () => {
    setEditingField(null)
    setEditValue("")
  }

  // Save edited field
  const saveField = async (field: string) => {
    if (!selectedJobId || !selectedJob) return

    try {
      setSaving(true)
      const updates: JobUpdateRequest = { [field]: editValue }
      await adminApi.updateJob(selectedJobId, updates)

      // Update local state
      setSelectedJob({ ...selectedJob, [field]: editValue })

      toast({
        title: "Updated",
        description: `${field} has been updated`,
      })

      setEditingField(null)
      setEditValue("")
    } catch (err: any) {
      toast({
        title: "Error",
        description: err.message || `Failed to update ${field}`,
        variant: "destructive",
      })
    } finally {
      setSaving(false)
    }
  }

  // Handle key press in edit input
  const handleEditKeyPress = (e: React.KeyboardEvent, field: string) => {
    if (e.key === "Enter") {
      saveField(field)
    } else if (e.key === "Escape") {
      cancelEditing()
    }
  }

  const handleDelete = async () => {
    if (!jobToDelete) return

    try {
      setDeleting(true)
      await adminApi.deleteJob(jobToDelete.job_id)
      toast({
        title: "Job Deleted",
        description: `Job ${jobToDelete.job_id} has been deleted`,
      })
      setDeleteDialogOpen(false)
      setJobToDelete(null)
      // If we were viewing this job, go back to list
      if (selectedJobId === jobToDelete.job_id) {
        router.push("/admin/jobs")
      }
      loadJobs()
    } catch (err: any) {
      toast({
        title: "Error",
        description: err.message || "Failed to delete job",
        variant: "destructive",
      })
    } finally {
      setDeleting(false)
    }
  }

  // Open the reset confirmation dialog
  const openResetDialog = (targetState: string) => {
    setResetTarget(targetState)
    setResetDialogOpen(true)
  }

  // Handle job reset
  const handleReset = async () => {
    if (!selectedJobId || !resetTarget) return

    try {
      setResetting(true)
      const result = await adminApi.resetJob(selectedJobId, resetTarget)
      toast({
        title: "Job Reset",
        description: result.message,
      })
      setResetDialogOpen(false)
      setResetTarget(null)
      // Refresh job details
      loadJobDetail(selectedJobId)
      loadLogs(selectedJobId)
    } catch (err: any) {
      toast({
        title: "Error",
        description: err.message || "Failed to reset job",
        variant: "destructive",
      })
    } finally {
      setResetting(false)
    }
  }

  // Handle delete outputs
  const handleDeleteOutputs = async () => {
    if (!selectedJobId) return

    try {
      setDeletingOutputs(true)
      const result = await adminApi.deleteJobOutputs(selectedJobId)
      toast({
        title: "Outputs Deleted",
        description: `${result.message}. Cleared: ${result.cleared_state_data.join(", ") || "none"}`,
      })
      setDeleteOutputsDialogOpen(false)
      // Refresh job details
      loadJobDetail(selectedJobId)
      loadLogs(selectedJobId)
    } catch (err: any) {
      toast({
        title: "Error",
        description: err.message || "Failed to delete outputs",
        variant: "destructive",
      })
    } finally {
      setDeletingOutputs(false)
    }
  }

  // Get reset target display info
  const getResetTargetInfo = (targetState: string) => {
    const info: Record<string, { label: string; description: string }> = {
      pending: {
        label: "Pending",
        description: "Restart from the beginning. Clears all processing data.",
      },
      awaiting_audio_selection: {
        label: "Audio Selection",
        description: "Re-select audio source. Preserves search results.",
      },
      awaiting_review: {
        label: "Lyrics Review",
        description: "Re-review lyrics. Preserves audio stems.",
      },
      awaiting_instrumental_selection: {
        label: "Instrumental Selection",
        description: "Re-select instrumental. Preserves lyrics review.",
      },
    }
    return info[targetState] || { label: targetState, description: "" }
  }

  const getStatusVariant = (status: string) => {
    if (status === "complete" || status === "prep_complete") return "default"
    if (status === "failed") return "destructive"
    if (status === "cancelled") return "outline"
    if (status.includes("awaiting")) return "secondary"
    return "secondary"
  }

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return "—"
    return new Date(dateStr).toLocaleString()
  }

  const getLogLevelColor = (level: string) => {
    switch (level?.toUpperCase()) {
      case "ERROR":
        return "text-red-500"
      case "WARNING":
        return "text-yellow-500"
      case "INFO":
        return "text-blue-500"
      case "DEBUG":
        return "text-muted-foreground"
      default:
        return "text-foreground"
    }
  }

  // Determine job source
  const getJobSource = (job: Job) => {
    if (job?.url) return { type: "url", icon: Globe, label: "YouTube URL" }
    if (job?.audio_search_artist || job?.audio_search_title) return { type: "search", icon: Search, label: "Audio Search" }
    if (job?.filename) return { type: "upload", icon: Upload, label: "File Upload" }
    return { type: "unknown", icon: FileText, label: "Unknown" }
  }

  // Calculate stage durations from timeline
  const getStageDurations = (job: Job) => {
    if (!job?.timeline || job.timeline.length < 2) return []

    const durations: { status: string; duration: number; startTime: string }[] = []
    for (let i = 0; i < job.timeline.length - 1; i++) {
      const current = job.timeline[i]
      const next = job.timeline[i + 1]
      const start = new Date(current.timestamp).getTime()
      const end = new Date(next.timestamp).getTime()
      const durationMs = end - start
      durations.push({
        status: current.status,
        duration: durationMs,
        startTime: current.timestamp,
      })
    }
    // Add current/final state
    if (job.timeline.length > 0) {
      const last = job.timeline[job.timeline.length - 1]
      durations.push({
        status: last.status,
        duration: 0,
        startTime: last.timestamp,
      })
    }
    return durations
  }

  const formatDuration = (ms: number) => {
    if (ms === 0) return "—"
    if (ms < 1000) return `${ms}ms`
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
    const mins = Math.floor(ms / 60000)
    const secs = Math.floor((ms % 60000) / 1000)
    return `${mins}m ${secs}s`
  }

  // Get timeline stage color based on status
  const getTimelineStageColor = (status: string) => {
    if (status === "complete" || status === "prep_complete") {
      return "bg-green-500"
    }
    if (status === "failed") {
      return "bg-red-500"
    }
    if (status === "cancelled") {
      return "bg-gray-400"
    }
    if (status.includes("awaiting") || status === "in_review") {
      return "bg-orange-500"
    }
    // Processing stages
    return "bg-blue-500"
  }

  // Get timeline border color
  const getTimelineBorderColor = (status: string) => {
    if (status === "complete" || status === "prep_complete") {
      return "border-green-500"
    }
    if (status === "failed") {
      return "border-red-500"
    }
    if (status === "cancelled") {
      return "border-gray-400"
    }
    if (status.includes("awaiting") || status === "in_review") {
      return "border-orange-500"
    }
    return "border-blue-500"
  }

  // Group files by category for display
  const groupFilesByCategory = (files: FileInfo[]) => {
    const groups: Record<string, FileInfo[]> = {}
    for (const file of files) {
      const category = file.category || "input"
      if (!groups[category]) {
        groups[category] = []
      }
      groups[category].push(file)
    }
    // Sort categories in logical order
    const categoryOrder = ["input", "stems", "lyrics", "screens", "videos", "finals", "packages"]
    const sortedGroups: Record<string, FileInfo[]> = {}
    for (const cat of categoryOrder) {
      if (groups[cat]) {
        sortedGroups[cat] = groups[cat]
      }
    }
    // Add any remaining categories not in the order
    for (const cat of Object.keys(groups)) {
      if (!sortedGroups[cat]) {
        sortedGroups[cat] = groups[cat]
      }
    }
    return sortedGroups
  }

  // Get a friendly label for file categories
  const getCategoryLabel = (category: string) => {
    const labels: Record<string, string> = {
      input: "Input",
      stems: "Audio Stems",
      lyrics: "Lyrics",
      screens: "Screen Images",
      videos: "Preview Videos",
      finals: "Final Outputs",
      packages: "Download Packages",
    }
    return labels[category] || category.charAt(0).toUpperCase() + category.slice(1)
  }

  // If a job is selected, show detail view
  if (selectedJobId) {
    if (detailLoading) {
      return (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      )
    }

    if (!selectedJob) {
      return (
        <div className="text-center py-12">
          <p className="text-muted-foreground">Job not found</p>
          <Button variant="outline" className="mt-4" onClick={() => router.push("/admin/jobs")}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Jobs
          </Button>
        </div>
      )
    }

    const jobSource = getJobSource(selectedJob)
    const stageDurations = getStageDurations(selectedJob)
    const SourceIcon = jobSource.icon

    return (
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" onClick={() => router.push("/admin/jobs")}>
              <ArrowLeft className="w-4 h-4" />
            </Button>
            <div>
              <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
                Job {selectedJob.job_id}
                <Badge variant={getStatusVariant(selectedJob.status)}>
                  {selectedJob.status.replace(/_/g, " ")}
                </Badge>
                {selectedJob.outputs_deleted_at && (
                  <Badge variant="outline" className="text-orange-600 border-orange-600">
                    <CloudOff className="w-3 h-3 mr-1" />
                    Outputs Deleted
                  </Badge>
                )}
              </h1>
              {selectedJob.artist && selectedJob.title && (
                <p className="text-muted-foreground">{selectedJob.artist} - {selectedJob.title}</p>
              )}
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                loadJobDetail(selectedJobId)
                loadLogs(selectedJobId)
                loadFiles(selectedJobId)
              }}
              disabled={detailLoading}
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${detailLoading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => {
                setJobToDelete(selectedJob)
                setDeleteDialogOpen(true)
              }}
            >
              <Trash2 className="w-4 h-4 mr-2" />
              Delete
            </Button>
          </div>
        </div>

        {/* Overview Cards */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <User className="w-4 h-4" />
                User
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm truncate">{selectedJob.user_email || "Unknown"}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <SourceIcon className="w-4 h-4" />
                Source
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm">{jobSource.label}</p>
              {selectedJob.url && (
                <p className="text-xs text-muted-foreground truncate">{selectedJob.url}</p>
              )}
              {selectedJob.audio_search_artist && (
                <p className="text-xs text-muted-foreground truncate">
                  {selectedJob.audio_search_artist} - {selectedJob.audio_search_title}
                </p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Clock className="w-4 h-4" />
                Created
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm">{formatDate(selectedJob.created_at)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Clock className="w-4 h-4" />
                Updated
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm">{formatDate(selectedJob.updated_at)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                Progress
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary transition-all"
                    style={{ width: `${selectedJob.progress}%` }}
                  />
                </div>
                <span className="text-sm font-medium">{selectedJob.progress}%</span>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Error Message */}
        {selectedJob.error_message && (
          <Card className="border-destructive">
            <CardHeader>
              <CardTitle className="text-destructive flex items-center gap-2">
                <XCircle className="w-5 h-5" />
                Error
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm">{selectedJob.error_message}</p>
              {selectedJob.error_details && (
                <pre className="mt-2 text-xs bg-muted p-2 rounded overflow-x-auto">
                  {JSON.stringify(selectedJob.error_details, null, 2)}
                </pre>
              )}
            </CardContent>
          </Card>
        )}

        {/* Accordion Sections */}
        <Accordion type="multiple" className="w-full" defaultValue={["timeline", "logs"]}>
          {/* Stage Timeline */}
          <AccordionItem value="timeline">
            <AccordionTrigger>
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4" />
                Timeline ({selectedJob.timeline?.length || 0} events)
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div className="max-h-[400px] overflow-y-auto pr-2">
                {stageDurations.length > 0 ? (
                  <div className="relative">
                    {stageDurations.map((stage, i) => {
                      const isLast = i === stageDurations.length - 1
                      const stageColor = getTimelineStageColor(stage.status)
                      const borderColor = getTimelineBorderColor(stage.status)

                      return (
                        <div key={i} className="relative pl-6 pb-4">
                          {/* Vertical line */}
                          {!isLast && (
                            <div
                              className={`absolute left-[9px] top-4 bottom-0 w-0.5 ${
                                stage.duration > 0 ? "bg-muted" : "bg-muted/50"
                              }`}
                            />
                          )}
                          {/* Dot */}
                          <div
                            className={`absolute left-0 top-1 w-5 h-5 rounded-full border-2 ${stageColor} ${borderColor} flex items-center justify-center`}
                          >
                            {isLast && (
                              <div className="w-2 h-2 rounded-full bg-white" />
                            )}
                          </div>
                          {/* Content */}
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <Badge
                                  variant="outline"
                                  className={`text-xs ${borderColor} border-current`}
                                >
                                  {stage.status.replace(/_/g, " ")}
                                </Badge>
                                {stage.duration > 0 && (
                                  <span className="text-xs text-muted-foreground">
                                    {formatDuration(stage.duration)}
                                  </span>
                                )}
                              </div>
                              {selectedJob.timeline?.[i]?.message && (
                                <p className="text-xs text-muted-foreground mt-1 truncate">
                                  {selectedJob.timeline[i].message}
                                </p>
                              )}
                            </div>
                            <span className="text-xs text-muted-foreground whitespace-nowrap shrink-0">
                              {new Date(stage.startTime).toLocaleTimeString()}
                            </span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <p className="text-muted-foreground text-sm">No timeline events</p>
                )}
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* Worker Logs */}
          <AccordionItem value="logs">
            <AccordionTrigger>
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Worker Logs ({logs.length} entries)
                {logsLoading && <Loader2 className="w-4 h-4 animate-spin ml-2" />}
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-1 max-h-[500px] overflow-y-auto font-mono text-xs">
                {logs.length > 0 ? (
                  logs.map((log, i) => (
                    <div key={i} className="flex gap-2 py-0.5 border-b border-muted/50">
                      <span className="text-muted-foreground whitespace-nowrap">
                        {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : "—"}
                      </span>
                      <span className={`w-16 ${getLogLevelColor(log.level)}`}>
                        [{log.level}]
                      </span>
                      <span className="text-muted-foreground w-20">
                        {log.worker || "—"}
                      </span>
                      <span className="flex-1 break-all">{log.message}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-muted-foreground">No logs available</p>
                )}
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* Request Metadata */}
          {selectedJob.request_metadata && Object.keys(selectedJob.request_metadata).length > 0 && (
            <AccordionItem value="metadata">
              <AccordionTrigger>
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4" />
                  Request Metadata
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  {selectedJob.request_metadata.environment && (
                    <>
                      <span className="text-muted-foreground">Environment:</span>
                      <span>{selectedJob.request_metadata.environment}</span>
                    </>
                  )}
                  {selectedJob.request_metadata.client_ip && (
                    <>
                      <span className="text-muted-foreground">Client IP:</span>
                      <span>{selectedJob.request_metadata.client_ip}</span>
                    </>
                  )}
                  {selectedJob.request_metadata.user_agent && (
                    <>
                      <span className="text-muted-foreground">User Agent:</span>
                      <span className="truncate">{selectedJob.request_metadata.user_agent}</span>
                    </>
                  )}
                  {selectedJob.request_metadata.server_version && (
                    <>
                      <span className="text-muted-foreground">Server Version:</span>
                      <span>{selectedJob.request_metadata.server_version}</span>
                    </>
                  )}
                  {selectedJob.request_metadata.created_from && (
                    <>
                      <span className="text-muted-foreground">Created From:</span>
                      <span>{selectedJob.request_metadata.created_from}</span>
                    </>
                  )}
                </div>
              </AccordionContent>
            </AccordionItem>
          )}

          {/* Admin Actions (Reset) */}
          <AccordionItem value="actions">
            <AccordionTrigger>
              <div className="flex items-center gap-2">
                <Wrench className="w-4 h-4" />
                Admin Actions
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-medium mb-2">Reset Job State</h4>
                  <p className="text-xs text-muted-foreground mb-4">
                    Reset the job to a previous checkpoint for re-processing. State data will be
                    cleared based on the selected target state.
                  </p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {[
                      { state: "pending", icon: RotateCcw },
                      { state: "awaiting_audio_selection", icon: Search },
                      { state: "awaiting_review", icon: FileText },
                      { state: "awaiting_instrumental_selection", icon: Settings },
                    ].map(({ state, icon: Icon }) => {
                      const info = getResetTargetInfo(state)
                      return (
                        <Button
                          key={state}
                          variant="outline"
                          className="justify-start h-auto py-2 px-3"
                          onClick={() => openResetDialog(state)}
                          disabled={resetting}
                        >
                          <Icon className="w-4 h-4 mr-2 shrink-0" />
                          <div className="text-left">
                            <div className="font-medium">{info.label}</div>
                            <div className="text-xs text-muted-foreground font-normal">
                              {info.description}
                            </div>
                          </div>
                        </Button>
                      )
                    })}
                  </div>
                </div>

                {/* Delete Outputs Section */}
                <div className="mt-6 pt-4 border-t">
                  <h4 className="text-sm font-medium mb-2">Delete Distributed Outputs</h4>
                  <p className="text-xs text-muted-foreground mb-4">
                    Delete YouTube video, Dropbox folder, and Google Drive files.
                    The job record is preserved. Use this to fix quality issues before re-processing.
                  </p>

                  {selectedJob.outputs_deleted_at ? (
                    <div className="p-3 bg-orange-50 dark:bg-orange-950 rounded-md">
                      <p className="text-sm text-orange-700 dark:text-orange-300">
                        Outputs were deleted at {formatDate(selectedJob.outputs_deleted_at)}
                        {selectedJob.outputs_deleted_by && ` by ${selectedJob.outputs_deleted_by}`}
                      </p>
                    </div>
                  ) : (
                    <>
                      <Button
                        variant="outline"
                        className="border-orange-500 text-orange-600 hover:bg-orange-50 dark:hover:bg-orange-950"
                        onClick={() => setDeleteOutputsDialogOpen(true)}
                        disabled={
                          deletingOutputs ||
                          !["complete", "prep_complete", "failed", "cancelled"].includes(selectedJob.status)
                        }
                      >
                        <CloudOff className="w-4 h-4 mr-2" />
                        Delete All Outputs
                      </Button>
                      {!["complete", "prep_complete", "failed", "cancelled"].includes(selectedJob.status) && (
                        <p className="text-xs text-muted-foreground mt-2">
                          Only available for jobs in terminal states (complete, prep_complete, failed, cancelled)
                        </p>
                      )}
                    </>
                  )}
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* Configuration (Editable Fields) */}
          <AccordionItem value="config">
            <AccordionTrigger>
              <div className="flex items-center gap-2">
                <Settings className="w-4 h-4" />
                Configuration
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-4">
                {/* Editable Text Fields */}
                {[
                  { key: "artist", label: "Artist", value: selectedJob.artist },
                  { key: "title", label: "Title", value: selectedJob.title },
                  { key: "user_email", label: "User Email", value: selectedJob.user_email },
                ].map(({ key, label, value }) => (
                  <div key={key} className="flex items-center gap-2">
                    <span className="text-sm font-medium w-28">{label}:</span>
                    {editingField === key ? (
                      <div className="flex items-center gap-2 flex-1">
                        <Input
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onKeyDown={(e) => handleEditKeyPress(e, key)}
                          className="h-8 text-sm"
                          autoFocus
                        />
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => saveField(key)}
                          disabled={saving}
                        >
                          {saving ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Check className="w-4 h-4 text-green-600" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={cancelEditing}
                          disabled={saving}
                        >
                          <X className="w-4 h-4 text-red-600" />
                        </Button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 flex-1">
                        <span className="text-sm text-muted-foreground truncate flex-1">
                          {value || "—"}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => startEditing(key, value || "")}
                        >
                          <Pencil className="w-4 h-4" />
                        </Button>
                      </div>
                    )}
                  </div>
                ))}

                {/* Theme and Options - Read-only display with edit hint */}
                <div className="mt-4 pt-4 border-t">
                  <p className="text-xs text-muted-foreground mb-3">
                    Additional settings (click pencil to edit)
                  </p>
                  {[
                    { key: "theme_id", label: "Theme", value: selectedJob.theme_id || "default" },
                    { key: "brand_prefix", label: "Brand Prefix", value: (selectedJob as any).brand_prefix },
                    { key: "customer_email", label: "Customer Email", value: (selectedJob as any).customer_email },
                  ].map(({ key, label, value }) => (
                    <div key={key} className="flex items-center gap-2 mb-2">
                      <span className="text-sm font-medium w-28">{label}:</span>
                      {editingField === key ? (
                        <div className="flex items-center gap-2 flex-1">
                          <Input
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onKeyDown={(e) => handleEditKeyPress(e, key)}
                            className="h-8 text-sm"
                            autoFocus
                          />
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => saveField(key)}
                            disabled={saving}
                          >
                            {saving ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Check className="w-4 h-4 text-green-600" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={cancelEditing}
                            disabled={saving}
                          >
                            <X className="w-4 h-4 text-red-600" />
                          </Button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 flex-1">
                          <span className="text-sm text-muted-foreground truncate flex-1">
                            {value || "—"}
                          </span>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => startEditing(key, value || "")}
                          >
                            <Pencil className="w-4 h-4" />
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* State Data */}
          <AccordionItem value="state">
            <AccordionTrigger>
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4" />
                State Data
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <pre className="text-xs bg-muted p-4 rounded-md overflow-x-auto max-h-[400px]">
                {JSON.stringify(selectedJob.state_data || {}, null, 2)}
              </pre>
            </AccordionContent>
          </AccordionItem>

          {/* Files with Download Links */}
          <AccordionItem value="files">
            <AccordionTrigger>
              <div className="flex items-center gap-2">
                <Download className="w-4 h-4" />
                Files ({files.length} downloadable)
                {filesLoading && <Loader2 className="w-4 h-4 animate-spin ml-2" />}
              </div>
            </AccordionTrigger>
            <AccordionContent>
              {filesLoading ? (
                <div className="flex items-center justify-center py-4">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : files.length === 0 ? (
                <p className="text-muted-foreground text-sm py-2">No files available</p>
              ) : (
                <div className="space-y-4">
                  {Object.entries(groupFilesByCategory(files)).map(([category, categoryFiles]) => (
                    <div key={category} className="space-y-2">
                      <h4 className="text-sm font-medium flex items-center gap-2">
                        <FolderOpen className="w-4 h-4 text-muted-foreground" />
                        {getCategoryLabel(category)}
                        <Badge variant="outline" className="text-xs">
                          {categoryFiles.length}
                        </Badge>
                      </h4>
                      <div className="grid gap-2 pl-6">
                        {categoryFiles.map((file, idx) => (
                          <div
                            key={`${file.path}-${idx}`}
                            className="flex items-center justify-between gap-2 p-2 bg-muted/50 rounded-md"
                          >
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium truncate" title={file.name}>
                                {file.name}
                              </p>
                              <p className="text-xs text-muted-foreground truncate" title={file.file_key}>
                                {file.file_key}
                              </p>
                            </div>
                            <Button
                              variant="outline"
                              size="sm"
                              asChild
                              className="shrink-0"
                            >
                              <a
                                href={file.download_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                download={file.name}
                              >
                                <Download className="w-4 h-4 mr-1" />
                                Download
                              </a>
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </AccordionContent>
          </AccordionItem>

          {/* Raw File URLs (for debugging) */}
          <AccordionItem value="file-urls-raw">
            <AccordionTrigger>
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4" />
                File URLs (Raw)
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <pre className="text-xs bg-muted p-4 rounded-md overflow-x-auto max-h-[400px]">
                {JSON.stringify(selectedJob.file_urls || {}, null, 2)}
              </pre>
            </AccordionContent>
          </AccordionItem>

          {/* Raw Job Data */}
          <AccordionItem value="raw">
            <AccordionTrigger>
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Raw Job Data
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <pre className="text-xs bg-muted p-4 rounded-md overflow-x-auto max-h-[500px]">
                {JSON.stringify(selectedJob, null, 2)}
              </pre>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        {/* Delete Confirmation Dialog */}
        <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete Job</AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to delete job {jobToDelete?.job_id}? This action
                cannot be undone and will also delete all associated files.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDelete}
                disabled={deleting}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                {deleting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Reset Confirmation Dialog */}
        <AlertDialog open={resetDialogOpen} onOpenChange={setResetDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Reset Job</AlertDialogTitle>
              <AlertDialogDescription>
                {resetTarget && (
                  <>
                    Reset job <span className="font-mono">{selectedJobId}</span> to{" "}
                    <span className="font-semibold">{getResetTargetInfo(resetTarget).label}</span>?
                    <br /><br />
                    {getResetTargetInfo(resetTarget).description}
                    <br /><br />
                    This will update the job status and clear relevant state data.
                  </>
                )}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleReset}
                disabled={resetting}
              >
                {resetting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                Reset
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Delete Outputs Confirmation Dialog */}
        <AlertDialog open={deleteOutputsDialogOpen} onOpenChange={setDeleteOutputsDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle className="flex items-center gap-2">
                <CloudOff className="w-5 h-5 text-orange-500" />
                Delete Job Outputs
              </AlertDialogTitle>
              <AlertDialogDescription>
                This will permanently delete:
                <ul className="list-disc list-inside mt-2 space-y-1">
                  <li>YouTube video (if uploaded)</li>
                  <li>Dropbox folder (frees brand code for reuse)</li>
                  <li>Google Drive files (if uploaded)</li>
                </ul>
                <br />
                The job record will be preserved with a timestamp marking when outputs were deleted.
                <br /><br />
                <strong>This action cannot be undone.</strong>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDeleteOutputs}
                disabled={deletingOutputs}
                className="bg-orange-500 hover:bg-orange-600"
              >
                {deletingOutputs && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                Delete Outputs
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    )
  }

  // List view
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Jobs</h1>
          <p className="text-muted-foreground">
            View and manage all jobs in the system
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={loadJobs} disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1 flex gap-2">
          <Input
            placeholder="Filter by user email..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={handleKeyPress}
            className="max-w-sm"
          />
          <Button variant="secondary" onClick={handleSearch}>
            <Search className="w-4 h-4" />
          </Button>
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            {statusOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Job ID</TableHead>
              <TableHead>User</TableHead>
              <TableHead>Artist / Title</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Progress</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin mx-auto text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : jobs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                  No jobs found
                </TableCell>
              </TableRow>
            ) : (
              jobs.map((job) => (
                <TableRow
                  key={job.job_id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => router.push(`/admin/jobs?id=${job.job_id}`)}
                >
                  <TableCell className="font-mono text-sm">{job.job_id}</TableCell>
                  <TableCell className="text-sm text-muted-foreground max-w-[150px] truncate">
                    {job.user_email || "—"}
                  </TableCell>
                  <TableCell>
                    {job.artist && job.title ? (
                      <span className="max-w-[200px] truncate block">
                        {job.artist} - {job.title}
                      </span>
                    ) : job.filename ? (
                      <span className="max-w-[200px] truncate block text-muted-foreground">
                        {job.filename}
                      </span>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant={getStatusVariant(job.status)}>
                      {job.status.replace(/_/g, " ")}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary transition-all"
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {job.progress}%
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-sm">
                    {formatDate(job.created_at)}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => router.push(`/admin/jobs?id=${job.job_id}`)}
                        title="View details"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          setJobToDelete(job)
                          setDeleteDialogOpen(true)
                        }}
                        title="Delete job"
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Summary */}
      <p className="text-sm text-muted-foreground">
        Showing {jobs.length} jobs
        {statusFilter !== "all" && ` with status "${statusFilter}"`}
        {userEmailFilter && ` for user "${userEmailFilter}"`}
      </p>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Job</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete job {jobToDelete?.job_id}? This action
              cannot be undone and will also delete all associated files.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

// Wrap in Suspense for useSearchParams
export default function AdminJobsPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    }>
      <AdminJobsPageContent />
    </Suspense>
  )
}
