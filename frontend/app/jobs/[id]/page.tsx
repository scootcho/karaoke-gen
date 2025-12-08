"use client"

import { useParams, useRouter } from "next/navigation"
import { useJobs } from "@/lib/jobs"
import { AppHeader } from "@/components/app-header"
import { ProtectedRoute } from "@/components/protected-route"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { StatusBadge } from "@/components/status-badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  ArrowLeft,
  Download,
  Youtube,
  FileAudio,
  Calendar,
  Clock,
  CheckCircle2,
  Loader2,
  XCircle,
  AlertCircle,
} from "lucide-react"

function JobDetailContent() {
  const params = useParams()
  const router = useRouter()
  const { getJobById } = useJobs()

  const job = getJobById(params.id as string)

  if (!job) {
    return (
      <div className="min-h-screen bg-background">
        <AppHeader />
        <main className="container mx-auto px-4 py-8">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>Job not found</AlertDescription>
          </Alert>
          <Button variant="outline" className="mt-4 bg-transparent" onClick={() => router.push("/jobs")}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Jobs
          </Button>
        </main>
      </div>
    )
  }

  const getStageIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 className="w-5 h-5 text-green-400" />
      case "in_progress":
        return <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
      case "failed":
        return <XCircle className="w-5 h-5 text-destructive" />
      default:
        return <div className="w-5 h-5 rounded-full border-2 border-muted" />
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <AppHeader />

      <main className="container mx-auto px-4 py-8 max-w-5xl">
        <Button variant="ghost" className="mb-6" onClick={() => router.push("/jobs")}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Jobs
        </Button>

        {/* Header */}
        <div className="mb-8">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="flex-1">
              <h1 className="text-4xl font-bold mb-2 text-balance">
                {job.artist} - {job.title}
              </h1>
              <div className="flex flex-wrap items-center gap-4 text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <Calendar className="w-4 h-4" />
                  Created {new Date(job.createdAt).toLocaleDateString()}
                </span>
                <span className="flex items-center gap-1.5">
                  <Clock className="w-4 h-4" />
                  Updated {new Date(job.updatedAt).toLocaleDateString()}
                </span>
              </div>
            </div>
            <StatusBadge status={job.status} size="lg" />
          </div>

          {job.status === "completed" && (
            <Button size="lg" className="bg-primary hover:bg-primary/90">
              <Download className="w-5 h-5 mr-2" />
              Download Karaoke Video
            </Button>
          )}
        </div>

        {/* Source Info */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">Source Information</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              {job.sourceType === "youtube" ? (
                <>
                  <div className="w-10 h-10 rounded-lg bg-red-500/10 flex items-center justify-center">
                    <Youtube className="w-5 h-5 text-red-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">YouTube Video</p>
                    <p className="text-sm text-muted-foreground truncate">{job.sourceUrl}</p>
                  </div>
                </>
              ) : (
                <>
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                    <FileAudio className="w-5 h-5 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">Uploaded Audio File</p>
                    <p className="text-sm text-muted-foreground truncate">{job.fileName}</p>
                  </div>
                </>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Progress Section */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">Processing Pipeline</CardTitle>
            <CardDescription>Track the progress of your karaoke video generation</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {job.stages.map((stage, index) => (
                <div key={index} className="flex items-start gap-4">
                  <div className="pt-1">{getStageIcon(stage.status)}</div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-medium">{stage.name}</h3>
                      {stage.status === "in_progress" && (
                        <span className="text-sm text-muted-foreground">{stage.progress}%</span>
                      )}
                    </div>
                    {stage.status === "in_progress" && <Progress value={stage.progress} className="h-2 bg-muted" />}
                    {stage.message && <p className="text-sm text-muted-foreground mt-1">{stage.message}</p>}
                  </div>
                </div>
              ))}
            </div>

            {job.status === "processing" && (
              <div className="mt-6 pt-6 border-t border-border">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium">Overall Progress</p>
                  <span className="text-sm text-muted-foreground">{job.progress}%</span>
                </div>
                <Progress value={job.progress} className="h-3" />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Error Message */}
        {job.status === "failed" && job.errorMessage && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{job.errorMessage}</AlertDescription>
          </Alert>
        )}

        {/* Action Alerts */}
        {job.status === "awaiting_review" && (
          <Alert className="bg-secondary/10 border-secondary/30">
            <AlertCircle className="h-4 w-4 text-secondary" />
            <AlertDescription className="text-foreground">
              Your karaoke video is ready for review. Please check the lyrics synchronization and approve or request
              changes.
            </AlertDescription>
          </Alert>
        )}

        {job.status === "awaiting_instrumental" && (
          <Alert className="bg-secondary/10 border-secondary/30">
            <AlertCircle className="h-4 w-4 text-secondary" />
            <AlertDescription className="text-foreground">
              Multiple instrumental versions were detected. Please select your preferred version to continue.
            </AlertDescription>
          </Alert>
        )}
      </main>
    </div>
  )
}

export default function JobDetailPage() {
  return (
    <ProtectedRoute>
      <JobDetailContent />
    </ProtectedRoute>
  )
}
