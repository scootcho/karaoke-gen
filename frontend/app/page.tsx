"use client"

import { useState, useEffect } from "react"
import { api, Job, ApiError } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { Youtube, Upload, Music2, RefreshCw, ExternalLink, Download, Loader2, CheckCircle2, XCircle, Clock, AlertCircle } from "lucide-react"

// Status badge styling
const statusConfig: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  pending: { color: "bg-slate-500", icon: <Clock className="w-3 h-3" />, label: "Pending" },
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

function StatusBadge({ status }: { status: string }) {
  const config = statusConfig[status] || { color: "bg-gray-500", icon: <Clock className="w-3 h-3" />, label: status }
  return (
    <Badge className={`${config.color} text-white gap-1`}>
      {config.icon}
      {config.label}
    </Badge>
  )
}

export default function HomePage() {
  const [activeTab, setActiveTab] = useState("upload")
  const [jobs, setJobs] = useState<Job[]>([])
  const [isLoadingJobs, setIsLoadingJobs] = useState(true)
  const [error, setError] = useState("")
  
  // Upload form
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadArtist, setUploadArtist] = useState("")
  const [uploadTitle, setUploadTitle] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  
  // URL form
  const [youtubeUrl, setYoutubeUrl] = useState("")
  const [youtubeArtist, setYoutubeArtist] = useState("")
  const [youtubeTitle, setYoutubeTitle] = useState("")

  // Load jobs on mount
  useEffect(() => {
    loadJobs()
    // Poll for updates every 10 seconds
    const interval = setInterval(loadJobs, 10000)
    return () => clearInterval(interval)
  }, [])

  async function loadJobs() {
    try {
      const data = await api.listJobs({ limit: 20 })
      setJobs(data)
    } catch (err) {
      console.error("Failed to load jobs:", err)
    } finally {
      setIsLoadingJobs(false)
    }
  }

  async function handleUploadSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    
    if (!uploadFile) {
      setError("Please select an audio file")
      return
    }
    if (!uploadArtist.trim() || !uploadTitle.trim()) {
      setError("Please enter both artist and title")
      return
    }
    
    setIsSubmitting(true)
    try {
      const result = await api.uploadJob(uploadFile, uploadArtist.trim(), uploadTitle.trim())
      console.log("Job created:", result)
      // Reset form
      setUploadFile(null)
      setUploadArtist("")
      setUploadTitle("")
      // Reload jobs
      await loadJobs()
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError("Failed to create job")
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleUrlSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    
    if (!youtubeUrl.trim()) {
      setError("Please enter a URL")
      return
    }
    
    setIsSubmitting(true)
    try {
      const result = await api.createJobFromUrl(
        youtubeUrl.trim(),
        youtubeArtist.trim() || undefined,
        youtubeTitle.trim() || undefined
      )
      console.log("Job created:", result)
      // Reset form
      setYoutubeUrl("")
      setYoutubeArtist("")
      setYoutubeTitle("")
      // Reload jobs
      await loadJobs()
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError("Failed to create job")
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) {
      setUploadFile(file)
      setError("")
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Music2 className="w-8 h-8 text-amber-500" />
            <div>
              <h1 className="text-xl font-bold text-white">Karaoke Generator</h1>
              <p className="text-xs text-slate-400">by Nomad Karaoke</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={loadJobs}
            disabled={isLoadingJobs}
            className="text-slate-400 hover:text-white"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isLoadingJobs ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 max-w-5xl">
        <div className="grid lg:grid-cols-2 gap-8">
          {/* Submit Job Card */}
          <Card className="border-slate-800 bg-slate-900/50 backdrop-blur">
            <CardHeader>
              <CardTitle className="text-white">Create Karaoke Video</CardTitle>
              <CardDescription className="text-slate-400">
                Upload an audio file or provide a YouTube URL
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="grid w-full grid-cols-2 bg-slate-800">
                  <TabsTrigger value="upload" className="gap-2 data-[state=active]:bg-slate-700">
                    <Upload className="w-4 h-4" />
                    Upload File
                  </TabsTrigger>
                  <TabsTrigger value="url" className="gap-2 data-[state=active]:bg-slate-700">
                    <Youtube className="w-4 h-4" />
                    From URL
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="upload" className="mt-4">
                  <form onSubmit={handleUploadSubmit} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="audio-file" className="text-slate-200">Audio File</Label>
                      <div
                        className={`relative border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer
                          ${uploadFile ? "border-amber-500/50 bg-amber-500/5" : "border-slate-700 hover:border-slate-600 bg-slate-800/50"}`}
                      >
                        <Input
                          id="audio-file"
                          type="file"
                          accept=".mp3,.wav,.flac,.m4a,.ogg,audio/*"
                          onChange={handleFileChange}
                          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                          disabled={isSubmitting}
                        />
                        <Upload className="w-8 h-8 mx-auto mb-2 text-slate-500" />
                        {uploadFile ? (
                          <div>
                            <p className="font-medium text-white">{uploadFile.name}</p>
                            <p className="text-sm text-slate-400">{(uploadFile.size / 1024 / 1024).toFixed(2)} MB</p>
                          </div>
                        ) : (
                          <div>
                            <p className="font-medium text-slate-300 mb-1">Click to upload</p>
                            <p className="text-sm text-slate-500">MP3, WAV, FLAC, M4A, or OGG</p>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="upload-artist" className="text-slate-200">Artist</Label>
                        <Input
                          id="upload-artist"
                          placeholder="Artist name"
                          value={uploadArtist}
                          onChange={(e) => setUploadArtist(e.target.value)}
                          disabled={isSubmitting}
                          className="bg-slate-800 border-slate-700 text-white placeholder:text-slate-500"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="upload-title" className="text-slate-200">Title</Label>
                        <Input
                          id="upload-title"
                          placeholder="Song title"
                          value={uploadTitle}
                          onChange={(e) => setUploadTitle(e.target.value)}
                          disabled={isSubmitting}
                          className="bg-slate-800 border-slate-700 text-white placeholder:text-slate-500"
                        />
                      </div>
                    </div>

                    {error && activeTab === "upload" && (
                      <p className="text-sm text-red-400 bg-red-500/10 rounded p-2">{error}</p>
                    )}

                    <Button
                      type="submit"
                      className="w-full bg-amber-600 hover:bg-amber-500 text-white"
                      disabled={isSubmitting}
                    >
                      {isSubmitting ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Creating Job...
                        </>
                      ) : (
                        "Create Karaoke Video"
                      )}
                    </Button>
                  </form>
                </TabsContent>

                <TabsContent value="url" className="mt-4">
                  <form onSubmit={handleUrlSubmit} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="youtube-url" className="text-slate-200">YouTube URL</Label>
                      <div className="relative">
                        <Youtube className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                        <Input
                          id="youtube-url"
                          type="url"
                          placeholder="https://youtube.com/watch?v=..."
                          value={youtubeUrl}
                          onChange={(e) => setYoutubeUrl(e.target.value)}
                          className="pl-10 bg-slate-800 border-slate-700 text-white placeholder:text-slate-500"
                          disabled={isSubmitting}
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="youtube-artist" className="text-slate-200">Artist (optional)</Label>
                        <Input
                          id="youtube-artist"
                          placeholder="Auto-detected"
                          value={youtubeArtist}
                          onChange={(e) => setYoutubeArtist(e.target.value)}
                          disabled={isSubmitting}
                          className="bg-slate-800 border-slate-700 text-white placeholder:text-slate-500"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="youtube-title" className="text-slate-200">Title (optional)</Label>
                        <Input
                          id="youtube-title"
                          placeholder="Auto-detected"
                          value={youtubeTitle}
                          onChange={(e) => setYoutubeTitle(e.target.value)}
                          disabled={isSubmitting}
                          className="bg-slate-800 border-slate-700 text-white placeholder:text-slate-500"
                        />
                      </div>
                    </div>

                    {error && activeTab === "url" && (
                      <p className="text-sm text-red-400 bg-red-500/10 rounded p-2">{error}</p>
                    )}

                    <Button
                      type="submit"
                      className="w-full bg-amber-600 hover:bg-amber-500 text-white"
                      disabled={isSubmitting}
                    >
                      {isSubmitting ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Creating Job...
                        </>
                      ) : (
                        "Create Karaoke Video"
                      )}
                    </Button>
                  </form>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>

          {/* Jobs List Card */}
          <Card className="border-slate-800 bg-slate-900/50 backdrop-blur">
            <CardHeader>
              <CardTitle className="text-white flex items-center justify-between">
                Recent Jobs
                {isLoadingJobs && <Loader2 className="w-4 h-4 animate-spin text-slate-400" />}
              </CardTitle>
              <CardDescription className="text-slate-400">
                {jobs.length} job{jobs.length !== 1 ? 's' : ''} found
              </CardDescription>
            </CardHeader>
            <CardContent>
              {jobs.length === 0 ? (
                <div className="text-center py-8 text-slate-500">
                  <Music2 className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No jobs yet. Create one to get started!</p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
                  {jobs.map((job) => (
                    <JobCard key={job.job_id} job={job} onRefresh={loadJobs} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 mt-12 py-6">
        <div className="container mx-auto px-4 text-center text-sm text-slate-500">
          <p>
            Powered by{" "}
            <a href="https://github.com/nomadkaraoke/karaoke-gen" className="text-amber-500 hover:underline">
              karaoke-gen
            </a>
          </p>
        </div>
      </footer>
    </div>
  )
}

function JobCard({ job, onRefresh }: { job: Job; onRefresh: () => void }) {
  const [showDetails, setShowDetails] = useState(false)
  const [downloadUrls, setDownloadUrls] = useState<Record<string, any> | null>(null)
  const [isLoadingDownloads, setIsLoadingDownloads] = useState(false)

  async function loadDownloadUrls() {
    if (job.status !== "complete" || downloadUrls) return
    setIsLoadingDownloads(true)
    try {
      const result = await api.getDownloadUrls(job.job_id)
      setDownloadUrls(result.download_urls)
    } catch (err) {
      console.error("Failed to load download URLs:", err)
    } finally {
      setIsLoadingDownloads(false)
    }
  }

  useEffect(() => {
    if (showDetails && job.status === "complete") {
      loadDownloadUrls()
    }
  }, [showDetails, job.status])

  const createdAt = new Date(job.created_at).toLocaleString()
  const isInteractive = job.status === "awaiting_review" || job.status === "awaiting_instrumental_selection"
  const isComplete = job.status === "complete"
  const isFailed = job.status === "failed"

  return (
    <div 
      className={`rounded-lg border p-3 transition-colors cursor-pointer
        ${isInteractive ? "border-orange-500/50 bg-orange-500/5" : "border-slate-700 bg-slate-800/30"}
        ${isComplete ? "border-green-500/30" : ""}
        ${isFailed ? "border-red-500/30" : ""}
        hover:bg-slate-800/50`}
      onClick={() => setShowDetails(!showDetails)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="font-medium text-white truncate">
            {job.artist || "Unknown"} - {job.title || "Unknown"}
          </p>
          <p className="text-xs text-slate-500 mt-1">{createdAt}</p>
          {job.progress > 0 && job.progress < 100 && (
            <div className="mt-2 h-1 rounded-full bg-slate-700 overflow-hidden">
              <div 
                className="h-full bg-amber-500 transition-all duration-500"
                style={{ width: `${job.progress}%` }}
              />
            </div>
          )}
        </div>
        <StatusBadge status={job.status} />
      </div>

      {showDetails && (
        <div className="mt-3 pt-3 border-t border-slate-700 space-y-2">
          <p className="text-xs text-slate-400">
            <span className="text-slate-500">Job ID:</span> {job.job_id}
          </p>
          
          {job.error_message && (
            <p className="text-xs text-red-400 bg-red-500/10 rounded p-2">
              {job.error_message}
            </p>
          )}

          {isInteractive && (
            <div className="flex gap-2 mt-2">
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
              {job.status === "awaiting_instrumental_selection" && (
                <InstrumentalSelector jobId={job.job_id} onComplete={onRefresh} />
              )}
            </div>
          )}

          {isComplete && (
            <div className="space-y-2">
              {isLoadingDownloads ? (
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Loading downloads...
                </div>
              ) : downloadUrls ? (
                <div className="flex flex-wrap gap-2">
                  {downloadUrls.finals?.lossy_720p && (
                    <a
                      href={api.getDownloadUrl(job.job_id, "finals", "lossy_720p")}
                      className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded bg-green-600 hover:bg-green-500 text-white"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Download className="w-3 h-3" />
                      720p Video
                    </a>
                  )}
                  {downloadUrls.finals?.lossy_4k_mp4 && (
                    <a
                      href={api.getDownloadUrl(job.job_id, "finals", "lossy_4k_mp4")}
                      className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded bg-green-600 hover:bg-green-500 text-white"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Download className="w-3 h-3" />
                      4K Video
                    </a>
                  )}
                  {downloadUrls.packages?.cdg_zip && (
                    <a
                      href={api.getDownloadUrl(job.job_id, "packages", "cdg_zip")}
                      className="inline-flex items-center gap-1 text-xs px-2 py-1.5 rounded bg-slate-600 hover:bg-slate-500 text-white"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Download className="w-3 h-3" />
                      CDG
                    </a>
                  )}
                </div>
              ) : (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={(e) => {
                    e.stopPropagation()
                    loadDownloadUrls()
                  }}
                  className="text-xs text-slate-400"
                >
                  Load Downloads
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function InstrumentalSelector({ jobId, onComplete }: { jobId: string; onComplete: () => void }) {
  const [isSelecting, setIsSelecting] = useState(false)

  async function handleSelect(selection: "clean" | "with_backing") {
    setIsSelecting(true)
    try {
      await api.selectInstrumental(jobId, selection)
      onComplete()
    } catch (err) {
      console.error("Failed to select instrumental:", err)
    } finally {
      setIsSelecting(false)
    }
  }

  return (
    <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
      <Button
        size="sm"
        onClick={() => handleSelect("clean")}
        disabled={isSelecting}
        className="text-xs bg-pink-600 hover:bg-pink-500"
      >
        {isSelecting ? <Loader2 className="w-3 h-3 animate-spin" /> : "Clean"}
      </Button>
      <Button
        size="sm"
        onClick={() => handleSelect("with_backing")}
        disabled={isSelecting}
        variant="outline"
        className="text-xs border-pink-500 text-pink-400 hover:bg-pink-500/10"
      >
        With Backing
      </Button>
    </div>
  )
}
