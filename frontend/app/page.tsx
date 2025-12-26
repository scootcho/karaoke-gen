"use client"

import { useState, useEffect } from "react"
import { api, Job } from "@/lib/api"
import { useAutoMode, getAutoModeFromUrl } from "@/lib/auto-mode"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Music2, RefreshCw, Loader2, Zap, ZapOff } from "lucide-react"
import { JobCard } from "@/components/job"
import { JobSubmission } from "@/components/job/JobSubmission"
import { AuthBanner } from "@/components/auth-banner"
import { AutoProcessor } from "@/components/AutoProcessor"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

export default function HomePage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [isLoadingJobs, setIsLoadingJobs] = useState(true)
  const { enabled: autoModeEnabled, setEnabled: setAutoMode, toggle: toggleAutoMode } = useAutoMode()

  // Initialize auto-mode from URL parameter on mount
  useEffect(() => {
    const urlAutoMode = getAutoModeFromUrl()
    if (urlAutoMode) {
      setAutoMode(true)
    }
  }, [setAutoMode])

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

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* AutoProcessor - handles non-interactive mode */}
      <AutoProcessor jobs={jobs} onJobsChanged={loadJobs} />

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
          <div className="flex items-center gap-2">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={toggleAutoMode}
                    className={`${
                      autoModeEnabled
                        ? "text-amber-400 hover:text-amber-300 bg-amber-500/10"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    {autoModeEnabled ? (
                      <Zap className="w-4 h-4 mr-2" />
                    ) : (
                      <ZapOff className="w-4 h-4 mr-2" />
                    )}
                    Auto
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-xs">
                  <p className="font-medium">
                    {autoModeEnabled ? "Auto Mode Enabled" : "Auto Mode Disabled"}
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    {autoModeEnabled
                      ? "Jobs will auto-complete review and select clean instrumental (like -y flag)"
                      : "Click to enable non-interactive mode"}
                  </p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
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
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 max-w-5xl space-y-6">
        {/* Auto Mode Banner */}
        {autoModeEnabled && (
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 flex items-center gap-3">
            <Zap className="w-5 h-5 text-amber-400 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm text-amber-200 font-medium">Non-Interactive Mode Active</p>
              <p className="text-xs text-amber-200/70 mt-0.5">
                Jobs will automatically accept lyrics and select clean instrumental (equivalent to -y flag)
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleAutoMode}
              className="text-amber-200 hover:text-amber-100 hover:bg-amber-500/20"
            >
              Disable
            </Button>
          </div>
        )}

        {/* Authentication Banner */}
        <AuthBanner />

        <div className="grid lg:grid-cols-2 gap-8">
          {/* Submit Job Card */}
          <Card className="border-slate-800 bg-slate-900/50 backdrop-blur">
            <CardHeader>
              <CardTitle className="text-white">Create Karaoke Video</CardTitle>
              <CardDescription className="text-slate-400">
                Upload an audio file, provide a YouTube URL, or search for audio by artist & title
              </CardDescription>
            </CardHeader>
            <CardContent>
              <JobSubmission onJobCreated={loadJobs} />
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
