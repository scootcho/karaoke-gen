"use client"

import { useState, useEffect } from "react"
import { api, Job, getAccessToken } from "@/lib/api"
import { useAutoMode, getAutoModeFromUrl } from "@/lib/auto-mode"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Music2, RefreshCw, Loader2, Zap, ZapOff, KeyRound, Moon, Sun } from "lucide-react"
import { JobCard } from "@/components/job"
import { JobSubmission } from "@/components/job/JobSubmission"
import { AuthStatus } from "@/components/auth"
import { AutoProcessor } from "@/components/AutoProcessor"
import { VersionFooter } from "@/components/version-footer"
import { useTheme } from "@/lib/theme"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

export default function HomePage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [isLoadingJobs, setIsLoadingJobs] = useState(true)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const { enabled: autoModeEnabled, setEnabled: setAutoMode, toggle: toggleAutoMode } = useAutoMode()
  const { isDarkMode, toggleTheme, mounted } = useTheme()

  // Check auth status on mount
  useEffect(() => {
    setIsAuthenticated(!!getAccessToken())
  }, [])

  // Initialize auto-mode from URL parameter on mount
  useEffect(() => {
    const urlAutoMode = getAutoModeFromUrl()
    if (urlAutoMode) {
      setAutoMode(true)
    }
  }, [setAutoMode])

  // Load jobs on mount (only if authenticated)
  useEffect(() => {
    if (!isAuthenticated) {
      setIsLoadingJobs(false)
      return
    }
    loadJobs()
    // Poll for updates every 10 seconds
    const interval = setInterval(loadJobs, 10000)
    return () => clearInterval(interval)
  }, [isAuthenticated])

  async function loadJobs() {
    if (!getAccessToken()) {
      setIsLoadingJobs(false)
      return
    }
    try {
      const data = await api.listJobs({ limit: 20 })
      setJobs(data)
    } catch (err: any) {
      // Don't log auth errors - user just needs to authenticate
      if (err?.status !== 401) {
        console.error("Failed to load jobs:", err)
      }
    } finally {
      setIsLoadingJobs(false)
    }
  }

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg)' }}>
      {/* AutoProcessor - handles non-interactive mode */}
      <AutoProcessor jobs={jobs} onJobsChanged={loadJobs} />

      {/* Header */}
      <header className="border-b backdrop-blur-sm sticky top-0 z-10" style={{ borderColor: 'var(--card-border)', backgroundColor: 'var(--card)' }}>
        <div className="px-3 sm:px-4 py-2 sm:py-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <img src="/nomad-karaoke-logo.svg" alt="Nomad Karaoke" className="h-8 sm:h-10 shrink-0" />
            <div className="min-w-0">
              <h1 className="text-base sm:text-xl font-bold truncate" style={{ color: 'var(--text)' }}>Karaoke Generator</h1>
            </div>
          </div>
          <div className="flex items-center gap-1 sm:gap-2 shrink-0">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={toggleAutoMode}
                    className={`min-h-[40px] px-2 sm:px-3 ${autoModeEnabled ? "text-amber-400 hover:text-amber-300 bg-amber-500/10" : ""}`}
                    style={!autoModeEnabled ? { color: 'var(--text-muted)' } : undefined}
                  >
                    {autoModeEnabled ? (
                      <Zap className="w-4 h-4 sm:mr-2" />
                    ) : (
                      <ZapOff className="w-4 h-4 sm:mr-2" />
                    )}
                    <span className="hidden sm:inline">Auto</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-xs">
                  <p className="font-medium">
                    {autoModeEnabled ? "Auto Mode Enabled" : "Auto Mode Disabled"}
                  </p>
                  <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
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
              disabled={isLoadingJobs || !isAuthenticated}
              className="min-h-[40px] px-2 sm:px-3"
              style={{ color: 'var(--text-muted)' }}
            >
              <RefreshCw className={`w-4 h-4 sm:mr-2 ${isLoadingJobs ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">Refresh</span>
            </Button>
            <AuthStatus />
            {mounted && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={toggleTheme}
                      className="min-h-[40px] px-2 sm:px-3"
                      style={{ color: 'var(--text-muted)' }}
                    >
                      {isDarkMode ? (
                        <Sun className="w-4 h-4" />
                      ) : (
                        <Moon className="w-4 h-4" />
                      )}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom">
                    <p>{isDarkMode ? "Switch to light mode" : "Switch to dark mode"}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>
        </div>
      </header>

      <main className="px-4 py-8 space-y-6">
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

        {/* Unauthenticated state */}
        {!isAuthenticated && (
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-6 text-center">
            <KeyRound className="w-8 h-8 text-amber-400 mx-auto mb-3" />
            <h3 className="text-lg font-medium mb-2" style={{ color: 'var(--text)' }}>Authentication Required</h3>
            <p className="text-sm mb-4" style={{ color: 'var(--text-muted)' }}>
              Click the Login button in the header to enter your access token
            </p>
          </div>
        )}

        <div className="grid lg:grid-cols-2 gap-8">
          {/* Submit Job Card */}
          <Card className="backdrop-blur" style={{ borderColor: 'var(--card-border)', backgroundColor: 'var(--card)' }}>
            <CardHeader>
              <CardTitle style={{ color: 'var(--text)' }}>Create Karaoke Video</CardTitle>
              <CardDescription style={{ color: 'var(--text-muted)' }}>
                Upload an audio file, provide a YouTube URL, or search for audio by artist & title
              </CardDescription>
            </CardHeader>
            <CardContent>
              <JobSubmission onJobCreated={loadJobs} />
            </CardContent>
          </Card>

          {/* Jobs List Card */}
          <Card className="backdrop-blur" style={{ borderColor: 'var(--card-border)', backgroundColor: 'var(--card)' }}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between" style={{ color: 'var(--text)' }}>
                Recent Jobs
                {isLoadingJobs && <Loader2 className="w-4 h-4 animate-spin" style={{ color: 'var(--text-muted)' }} />}
              </CardTitle>
              <CardDescription style={{ color: 'var(--text-muted)' }}>
                {jobs.length} job{jobs.length !== 1 ? 's' : ''} found
              </CardDescription>
            </CardHeader>
            <CardContent>
              {jobs.length === 0 ? (
                <div className="text-center py-8" style={{ color: 'var(--text-muted)' }}>
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

      <VersionFooter />
    </div>
  )
}
