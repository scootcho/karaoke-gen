"use client"

import { useState, useEffect } from "react"
import { api, Job } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Music2, RefreshCw, Loader2 } from "lucide-react"
import { JobCard } from "@/components/job"
import { JobSubmission } from "@/components/job/JobSubmission"

export default function HomePage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [isLoadingJobs, setIsLoadingJobs] = useState(true)

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
