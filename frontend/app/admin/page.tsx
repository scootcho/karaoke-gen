"use client"

import { useState } from "react"
import { useJobs } from "@/lib/jobs"
import type { JobStatus } from "@/lib/types"
import { AppHeader } from "@/components/app-header"
import { ProtectedRoute } from "@/components/protected-route"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { StatusBadge } from "@/components/status-badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { BarChart3, FileVideo, Ticket, TrendingUp, Activity, ChevronRight } from "lucide-react"
import Link from "next/link"

function AdminContent() {
  const { jobs } = useJobs()
  const [promoCode, setPromoCode] = useState("")
  const [promoCredits, setPromoCredits] = useState("5")
  const [generatedCode, setGeneratedCode] = useState("")

  const totalJobs = jobs.length
  const completedJobs = jobs.filter((j) => j.status === "completed").length
  const processingJobs = jobs.filter((j) => j.status === "processing" || j.status === "queued").length
  const failedJobs = jobs.filter((j) => j.status === "failed").length

  const handleGeneratePromo = () => {
    const code = `NOMAD${Math.random().toString(36).substr(2, 6).toUpperCase()}`
    setGeneratedCode(code)
    setPromoCode("")
  }

  const statusCounts = {
    queued: jobs.filter((j) => j.status === "queued").length,
    processing: jobs.filter((j) => j.status === "processing").length,
    awaiting_review: jobs.filter((j) => j.status === "awaiting_review").length,
    awaiting_instrumental: jobs.filter((j) => j.status === "awaiting_instrumental").length,
    completed: completedJobs,
    failed: failedJobs,
  }

  const recentJobs = [...jobs]
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    .slice(0, 10)

  return (
    <div className="min-h-screen bg-background">
      <AppHeader />

      <main className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-2">Admin Dashboard</h1>
          <p className="text-muted-foreground">Manage users, jobs, and system analytics</p>
        </div>

        {/* Stats Grid */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
          <Card className="bg-gradient-to-br from-primary/10 to-transparent border-primary/20">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total Jobs</CardTitle>
              <FileVideo className="w-4 h-4 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-primary">{totalJobs}</div>
              <p className="text-xs text-muted-foreground mt-1">All time</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Completed</CardTitle>
              <TrendingUp className="w-4 h-4 text-green-400" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-green-400">{completedJobs}</div>
              <p className="text-xs text-muted-foreground mt-1">
                {((completedJobs / totalJobs) * 100).toFixed(1)}% success rate
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Processing</CardTitle>
              <Activity className="w-4 h-4 text-blue-400" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-blue-400">{processingJobs}</div>
              <p className="text-xs text-muted-foreground mt-1">Active jobs</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Failed</CardTitle>
              <BarChart3 className="w-4 h-4 text-destructive" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-destructive">{failedJobs}</div>
              <p className="text-xs text-muted-foreground mt-1">
                {((failedJobs / totalJobs) * 100).toFixed(1)}% failure rate
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList className="grid w-full max-w-md grid-cols-3">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="jobs">All Jobs</TabsTrigger>
            <TabsTrigger value="promo">Promo Codes</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            {/* Status Breakdown */}
            <Card>
              <CardHeader>
                <CardTitle>Job Status Breakdown</CardTitle>
                <CardDescription>Current distribution of job statuses</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {Object.entries(statusCounts).map(([status, count]) => (
                    <div
                      key={status}
                      className="flex items-center justify-between p-3 rounded-lg border border-border bg-card"
                    >
                      <div className="flex items-center gap-3">
                        <StatusBadge status={status as JobStatus} size="sm" />
                        <span className="text-sm text-muted-foreground">Jobs</span>
                      </div>
                      <span className="text-lg font-bold">{count}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Recent Activity */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Recent Activity</CardTitle>
                  <CardDescription>Latest jobs across all users</CardDescription>
                </div>
                <Button variant="outline" size="sm" asChild>
                  <Link href="#" onClick={(e) => e.preventDefault()}>
                    View All
                  </Link>
                </Button>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {recentJobs.slice(0, 5).map((job) => (
                    <Link
                      key={job.id}
                      href={`/jobs/${job.id}`}
                      className="flex items-center justify-between p-3 rounded-lg border border-border hover:border-primary/50 hover:bg-card/50 transition-all group"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm truncate group-hover:text-primary transition-colors">
                          {job.artist} - {job.title}
                        </p>
                        <p className="text-xs text-muted-foreground">{new Date(job.createdAt).toLocaleString()}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={job.status} size="sm" />
                        <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
                      </div>
                    </Link>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="jobs" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>All Jobs</CardTitle>
                <CardDescription>Complete list of all karaoke video jobs in the system</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border border-border overflow-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Artist - Title</TableHead>
                        <TableHead>User ID</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Created</TableHead>
                        <TableHead>Progress</TableHead>
                        <TableHead></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {recentJobs.map((job) => (
                        <TableRow key={job.id} className="hover:bg-muted/50">
                          <TableCell className="font-medium">
                            {job.artist} - {job.title}
                          </TableCell>
                          <TableCell className="text-muted-foreground text-sm">{job.userId}</TableCell>
                          <TableCell>
                            <StatusBadge status={job.status} size="sm" />
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {new Date(job.createdAt).toLocaleDateString()}
                          </TableCell>
                          <TableCell className="text-sm">{job.progress}%</TableCell>
                          <TableCell>
                            <Button variant="ghost" size="sm" asChild>
                              <Link href={`/jobs/${job.id}`}>
                                <ChevronRight className="w-4 h-4" />
                              </Link>
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="promo" className="space-y-6">
            <div className="grid gap-6 lg:grid-cols-2">
              {/* Generate Promo Code */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Ticket className="w-5 h-5 text-primary" />
                    Generate Promo Code
                  </CardTitle>
                  <CardDescription>Create promotional codes for users to redeem credits</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="promo-credits">Credit Amount</Label>
                    <Input
                      id="promo-credits"
                      type="number"
                      min="1"
                      max="100"
                      value={promoCredits}
                      onChange={(e) => setPromoCredits(e.target.value)}
                    />
                    <p className="text-xs text-muted-foreground">Number of credits this code will provide</p>
                  </div>

                  <Button onClick={handleGeneratePromo} className="w-full bg-primary hover:bg-primary/90">
                    Generate Code
                  </Button>

                  {generatedCode && (
                    <div className="p-4 rounded-lg bg-primary/10 border border-primary/20">
                      <p className="text-sm text-muted-foreground mb-2">Generated Promo Code:</p>
                      <p className="text-2xl font-mono font-bold text-primary">{generatedCode}</p>
                      <p className="text-xs text-muted-foreground mt-2">Worth {promoCredits} credits</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Active Promo Codes */}
              <Card>
                <CardHeader>
                  <CardTitle>Active Promo Codes</CardTitle>
                  <CardDescription>Currently available promotional codes</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 rounded-lg border border-border bg-card">
                      <div>
                        <p className="font-mono font-medium">NOMADWELCOME</p>
                        <p className="text-xs text-muted-foreground">5 credits • Used 23 times</p>
                      </div>
                      <Button variant="ghost" size="sm" className="text-destructive">
                        Disable
                      </Button>
                    </div>

                    <div className="flex items-center justify-between p-3 rounded-lg border border-border bg-card">
                      <div>
                        <p className="font-mono font-medium">LAUNCH2024</p>
                        <p className="text-xs text-muted-foreground">10 credits • Used 8 times</p>
                      </div>
                      <Button variant="ghost" size="sm" className="text-destructive">
                        Disable
                      </Button>
                    </div>

                    {generatedCode && (
                      <div className="flex items-center justify-between p-3 rounded-lg border border-primary/20 bg-primary/5">
                        <div>
                          <p className="font-mono font-medium text-primary">{generatedCode}</p>
                          <p className="text-xs text-muted-foreground">{promoCredits} credits • Not used yet</p>
                        </div>
                        <Button variant="ghost" size="sm" className="text-destructive">
                          Disable
                        </Button>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Usage Statistics */}
            <Card>
              <CardHeader>
                <CardTitle>Promo Code Statistics</CardTitle>
                <CardDescription>Usage analytics and performance metrics</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">Total Codes</p>
                    <p className="text-3xl font-bold">12</p>
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">Total Redemptions</p>
                    <p className="text-3xl font-bold">156</p>
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">Credits Distributed</p>
                    <p className="text-3xl font-bold text-primary">892</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}

export default function AdminPage() {
  return (
    <ProtectedRoute requireAdmin>
      <AdminContent />
    </ProtectedRoute>
  )
}
