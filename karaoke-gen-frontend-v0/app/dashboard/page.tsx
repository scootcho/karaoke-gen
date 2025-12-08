"use client"

import { useRouter } from "next/navigation"
import { useAuth } from "@/lib/auth"
import { useJobs } from "@/lib/jobs"
import { AppHeader } from "@/components/app-header"
import { ProtectedRoute } from "@/components/protected-route"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { StatusBadge } from "@/components/status-badge"
import { Plus, FileVideo, Clock, CheckCircle2, Loader2 } from "lucide-react"
import Link from "next/link"

function DashboardContent() {
  const { user } = useAuth()
  const { jobs, getUserJobs } = useJobs()
  const router = useRouter()

  if (!user) return null

  const userJobs = getUserJobs(user.token.includes("demo") ? "demo" : user.token)
  const completedJobs = userJobs.filter((j) => j.status === "completed").length
  const inProgressJobs = userJobs.filter((j) => j.status === "processing" || j.status === "queued").length
  const totalJobs = userJobs.length
  const recentJobs = userJobs.slice(0, 5)

  return (
    <div className="min-h-screen bg-background">
      <AppHeader />

      <main className="container mx-auto px-4 py-8">
        {/* Welcome Section */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-2">
            Welcome back<span className="text-primary">!</span>
          </h1>
          <p className="text-muted-foreground">Manage your karaoke video projects</p>
        </div>

        {/* Stats Grid */}
        <div className="grid gap-4 md:grid-cols-4 mb-8">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total Jobs</CardTitle>
              <FileVideo className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{totalJobs}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Completed</CardTitle>
              <CheckCircle2 className="w-4 h-4 text-green-400" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-green-400">{completedJobs}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">In Progress</CardTitle>
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-blue-400">{inProgressJobs}</div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-primary/10 to-secondary/10 border-primary/20">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Credits Remaining</CardTitle>
              <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-primary">{user.credits}</div>
              <p className="text-xs text-muted-foreground mt-1">
                <Link href="#" className="hover:text-primary transition-colors">
                  Purchase more
                </Link>
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Create New Job CTA */}
        <Card className="mb-8 bg-gradient-to-r from-primary/5 via-card to-secondary/5 border-primary/20">
          <CardHeader>
            <CardTitle className="text-2xl">Create New Karaoke Video</CardTitle>
            <CardDescription>
              Transform any song into a professional karaoke video with synchronized lyrics
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button size="lg" className="bg-primary hover:bg-primary/90" onClick={() => router.push("/jobs/new")}>
              <Plus className="w-5 h-5 mr-2" />
              Create New Job
            </Button>
          </CardContent>
        </Card>

        {/* Recent Jobs */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Recent Jobs</CardTitle>
              <CardDescription>Your latest karaoke video projects</CardDescription>
            </div>
            <Button variant="outline" size="sm" asChild>
              <Link href="/jobs">View All</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {recentJobs.length === 0 ? (
              <div className="text-center py-12">
                <FileVideo className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                <p className="text-muted-foreground mb-4">No jobs yet</p>
                <Button onClick={() => router.push("/jobs/new")}>
                  <Plus className="w-4 h-4 mr-2" />
                  Create Your First Job
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {recentJobs.map((job) => (
                  <Link
                    key={job.id}
                    href={`/jobs/${job.id}`}
                    className="flex items-center justify-between p-4 rounded-lg border border-border hover:border-primary/50 hover:bg-card/50 transition-all cursor-pointer group"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="font-medium group-hover:text-primary transition-colors">
                          {job.artist} - {job.title}
                        </h3>
                        <StatusBadge status={job.status} size="sm" />
                      </div>
                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {new Date(job.createdAt).toLocaleDateString()}
                        </span>
                        {job.status === "processing" && <span>{job.progress}% complete</span>}
                      </div>
                    </div>

                    {job.status === "completed" && (
                      <Button size="sm" variant="outline" className="ml-4 bg-transparent">
                        Download
                      </Button>
                    )}
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  )
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  )
}
