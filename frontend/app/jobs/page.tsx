"use client"

import { useState } from "react"
import { useAuth } from "@/lib/auth"
import { useJobs } from "@/lib/jobs"
import type { JobStatus } from "@/lib/types"
import { AppHeader } from "@/components/app-header"
import { ProtectedRoute } from "@/components/protected-route"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { StatusBadge } from "@/components/status-badge"
import { Plus, Search, Clock, Download, ChevronRight } from "lucide-react"
import Link from "next/link"

function JobsListContent() {
  const { user } = useAuth()
  const { jobs, getUserJobs } = useJobs()

  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<JobStatus | "all">("all")

  if (!user) return null

  const userJobs = getUserJobs(user.token.includes("demo") ? "demo" : user.token)

  const filteredJobs = userJobs.filter((job) => {
    const matchesSearch =
      searchQuery === "" ||
      job.artist.toLowerCase().includes(searchQuery.toLowerCase()) ||
      job.title.toLowerCase().includes(searchQuery.toLowerCase())

    const matchesStatus = statusFilter === "all" || job.status === statusFilter

    return matchesSearch && matchesStatus
  })

  return (
    <div className="min-h-screen bg-background">
      <AppHeader />

      <main className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-4xl font-bold mb-2">My Jobs</h1>
            <p className="text-muted-foreground">Manage and track your karaoke video projects</p>
          </div>

          <Button asChild className="bg-primary hover:bg-primary/90">
            <Link href="/jobs/new">
              <Plus className="w-4 h-4 mr-2" />
              New Job
            </Link>
          </Button>
        </div>

        {/* Filters */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="Search by artist or title..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>

              <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as JobStatus | "all")}>
                <SelectTrigger className="w-full sm:w-[200px]">
                  <SelectValue placeholder="Filter by status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="queued">Queued</SelectItem>
                  <SelectItem value="processing">Processing</SelectItem>
                  <SelectItem value="awaiting_review">Awaiting Review</SelectItem>
                  <SelectItem value="awaiting_instrumental">Select Instrumental</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="failed">Failed</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Results count */}
        <div className="mb-4">
          <p className="text-sm text-muted-foreground">
            Showing {filteredJobs.length} of {userJobs.length} jobs
          </p>
        </div>

        {/* Jobs List */}
        {filteredJobs.length === 0 ? (
          <Card>
            <CardContent className="text-center py-12">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-muted flex items-center justify-center">
                <Search className="w-8 h-8 text-muted-foreground" />
              </div>
              <h3 className="font-semibold mb-2">No jobs found</h3>
              <p className="text-muted-foreground mb-4">
                {searchQuery || statusFilter !== "all"
                  ? "Try adjusting your filters"
                  : "Create your first karaoke video to get started"}
              </p>
              {!searchQuery && statusFilter === "all" && (
                <Button asChild>
                  <Link href="/jobs/new">
                    <Plus className="w-4 h-4 mr-2" />
                    Create Job
                  </Link>
                </Button>
              )}
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {filteredJobs.map((job) => (
              <Link key={job.id} href={`/jobs/${job.id}`}>
                <Card className="hover:border-primary/50 hover:bg-card/80 transition-all group cursor-pointer">
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="font-semibold text-lg group-hover:text-primary transition-colors truncate">
                            {job.artist} - {job.title}
                          </h3>
                          <StatusBadge status={job.status} />
                        </div>

                        <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                          <span className="flex items-center gap-1.5">
                            <Clock className="w-3.5 h-3.5" />
                            {new Date(job.createdAt).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                            })}
                          </span>

                          <span className="text-xs">
                            {job.sourceType === "youtube" ? "From YouTube" : "Uploaded File"}
                          </span>

                          {(job.status === "processing" || job.status === "queued") && (
                            <span className="text-xs font-medium">{job.progress}% complete</span>
                          )}
                        </div>

                        {(job.status === "processing" || job.status === "queued") && (
                          <div className="mt-3 w-full max-w-xs">
                            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                              <div
                                className="h-full bg-primary transition-all duration-300"
                                style={{ width: `${job.progress}%` }}
                              />
                            </div>
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        {job.status === "completed" && (
                          <Button size="sm" variant="outline" onClick={(e) => e.preventDefault()}>
                            <Download className="w-4 h-4 mr-2" />
                            Download
                          </Button>
                        )}
                        <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

export default function JobsPage() {
  return (
    <ProtectedRoute>
      <JobsListContent />
    </ProtectedRoute>
  )
}
