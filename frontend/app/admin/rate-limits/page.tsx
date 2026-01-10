"use client"

import { useEffect, useState } from "react"
import {
  adminApi,
  RateLimitStatsResponse,
  BlocklistsResponse,
  UserOverridesListResponse,
  UserOverride,
} from "@/lib/api"
import { StatsCard, StatsGrid } from "@/components/admin/stats-card"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import {
  ShieldAlert,
  Youtube,
  Briefcase,
  Globe,
  Mail,
  Server,
  UserCheck,
  RefreshCw,
  Loader2,
  Plus,
  Trash2,
  Search,
} from "lucide-react"
import { useToast } from "@/hooks/use-toast"

export default function AdminRateLimitsPage() {
  const { toast } = useToast()
  const [stats, setStats] = useState<RateLimitStatsResponse | null>(null)
  const [blocklists, setBlocklists] = useState<BlocklistsResponse | null>(null)
  const [overrides, setOverrides] = useState<UserOverridesListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState("overview")

  // Form states
  const [newDomain, setNewDomain] = useState("")
  const [newEmail, setNewEmail] = useState("")
  const [newIP, setNewIP] = useState("")
  const [searchDomain, setSearchDomain] = useState("")
  const [searchEmail, setSearchEmail] = useState("")
  const [searchIP, setSearchIP] = useState("")

  // Override form
  const [overrideEmail, setOverrideEmail] = useState("")
  const [overrideBypass, setOverrideBypass] = useState(false)
  const [overrideCustomLimit, setOverrideCustomLimit] = useState("")
  const [overrideReason, setOverrideReason] = useState("")
  const [overrideDialogOpen, setOverrideDialogOpen] = useState(false)

  const loadData = async () => {
    try {
      setLoading(true)
      const [statsData, blocklistsData, overridesData] = await Promise.all([
        adminApi.getRateLimitStats(),
        adminApi.getBlocklists(),
        adminApi.getUserOverrides(),
      ])
      setStats(statsData)
      setBlocklists(blocklistsData)
      setOverrides(overridesData)
    } catch (err: any) {
      console.error("Failed to load rate limits data:", err)
      toast({
        title: "Error",
        description: err.message || "Failed to load rate limits data",
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  // Blocklist actions
  const handleAddDomain = async () => {
    if (!newDomain.trim()) return
    try {
      await adminApi.addDisposableDomain(newDomain.trim())
      toast({ title: "Success", description: `Domain "${newDomain}" added to blocklist` })
      setNewDomain("")
      loadData()
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" })
    }
  }

  const handleRemoveDomain = async (domain: string) => {
    try {
      await adminApi.removeDisposableDomain(domain)
      toast({ title: "Success", description: `Domain "${domain}" removed from blocklist` })
      loadData()
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" })
    }
  }

  const handleAddEmail = async () => {
    if (!newEmail.trim()) return
    try {
      await adminApi.addBlockedEmail(newEmail.trim())
      toast({ title: "Success", description: `Email "${newEmail}" added to blocklist` })
      setNewEmail("")
      loadData()
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" })
    }
  }

  const handleRemoveEmail = async (email: string) => {
    try {
      await adminApi.removeBlockedEmail(email)
      toast({ title: "Success", description: `Email "${email}" removed from blocklist` })
      loadData()
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" })
    }
  }

  const handleAddIP = async () => {
    if (!newIP.trim()) return
    try {
      await adminApi.addBlockedIP(newIP.trim())
      toast({ title: "Success", description: `IP "${newIP}" added to blocklist` })
      setNewIP("")
      loadData()
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" })
    }
  }

  const handleRemoveIP = async (ip: string) => {
    try {
      await adminApi.removeBlockedIP(ip)
      toast({ title: "Success", description: `IP "${ip}" removed from blocklist` })
      loadData()
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" })
    }
  }

  // Override actions
  const handleAddOverride = async () => {
    if (!overrideEmail.trim() || !overrideReason.trim()) {
      toast({ title: "Error", description: "Email and reason are required", variant: "destructive" })
      return
    }
    try {
      await adminApi.setUserOverride(overrideEmail.trim(), {
        bypass_job_limit: overrideBypass,
        custom_daily_job_limit: overrideCustomLimit ? parseInt(overrideCustomLimit) : undefined,
        reason: overrideReason.trim(),
      })
      toast({ title: "Success", description: `Override set for "${overrideEmail}"` })
      setOverrideEmail("")
      setOverrideBypass(false)
      setOverrideCustomLimit("")
      setOverrideReason("")
      setOverrideDialogOpen(false)
      loadData()
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" })
    }
  }

  const handleRemoveOverride = async (email: string) => {
    try {
      await adminApi.removeUserOverride(email)
      toast({ title: "Success", description: `Override removed for "${email}"` })
      loadData()
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" })
    }
  }

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return "—"
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return "—"
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  // Filter functions
  const filteredDomains = blocklists?.disposable_domains.filter(d =>
    d.toLowerCase().includes(searchDomain.toLowerCase())
  ) || []

  const filteredEmails = blocklists?.blocked_emails.filter(e =>
    e.toLowerCase().includes(searchEmail.toLowerCase())
  ) || []

  const filteredIPs = blocklists?.blocked_ips.filter(ip =>
    ip.includes(searchIP)
  ) || []

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Rate Limits</h1>
          <p className="text-muted-foreground">
            Manage rate limiting, blocklists, and user overrides
          </p>
        </div>
        <Button onClick={loadData} variant="outline" disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="blocklists">Blocklists</TabsTrigger>
          <TabsTrigger value="overrides">User Overrides</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          {/* Configuration Stats */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldAlert className="w-5 h-5" />
                Rate Limit Configuration
              </CardTitle>
              <CardDescription>Current rate limiting settings</CardDescription>
            </CardHeader>
            <CardContent>
              <StatsGrid columns={4}>
                <StatsCard
                  title="Jobs Per Day"
                  value={stats?.jobs_per_day_limit ?? 0}
                  description="Per user limit"
                  icon={Briefcase}
                />
                <StatsCard
                  title="YouTube Uploads"
                  value={stats?.youtube_uploads_per_day_limit ?? 0}
                  description="System-wide limit"
                  icon={Youtube}
                />
                <StatsCard
                  title="Beta IP Limit"
                  value={stats?.beta_ip_per_day_limit ?? 0}
                  description="Enrollments per IP/day"
                  icon={Globe}
                />
                <StatsCard
                  title="Status"
                  value={stats?.rate_limiting_enabled ? "Enabled" : "Disabled"}
                  description="Rate limiting"
                  icon={ShieldAlert}
                  valueClassName={stats?.rate_limiting_enabled ? "text-green-600" : "text-red-600"}
                />
              </StatsGrid>
            </CardContent>
          </Card>

          {/* Current Usage Stats */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Youtube className="w-5 h-5" />
                Today&apos;s Usage
              </CardTitle>
              <CardDescription>Current rate limit usage</CardDescription>
            </CardHeader>
            <CardContent>
              <StatsGrid columns={3}>
                <StatsCard
                  title="YouTube Uploads Today"
                  value={stats?.youtube_uploads_today ?? 0}
                  description={`${stats?.youtube_uploads_remaining ?? 0} remaining`}
                  icon={Youtube}
                />
                <StatsCard
                  title="Blocked Domains"
                  value={stats?.disposable_domains_count ?? 0}
                  description="Disposable email domains"
                  icon={Globe}
                />
                <StatsCard
                  title="User Overrides"
                  value={stats?.total_overrides ?? 0}
                  description="Active whitelist entries"
                  icon={UserCheck}
                />
              </StatsGrid>
            </CardContent>
          </Card>

          {/* Blocklist Summary */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mail className="w-5 h-5" />
                Blocklist Summary
              </CardTitle>
            </CardHeader>
            <CardContent>
              <StatsGrid columns={3}>
                <StatsCard
                  title="Disposable Domains"
                  value={stats?.disposable_domains_count ?? 0}
                  icon={Globe}
                />
                <StatsCard
                  title="Blocked Emails"
                  value={stats?.blocked_emails_count ?? 0}
                  icon={Mail}
                />
                <StatsCard
                  title="Blocked IPs"
                  value={stats?.blocked_ips_count ?? 0}
                  icon={Server}
                />
              </StatsGrid>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Blocklists Tab */}
        <TabsContent value="blocklists" className="space-y-6">
          {/* Disposable Domains */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Globe className="w-5 h-5" />
                Disposable Email Domains
              </CardTitle>
              <CardDescription>
                Domains blocked from beta enrollment ({filteredDomains.length} of {blocklists?.disposable_domains.length || 0})
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    placeholder="Search domains..."
                    value={searchDomain}
                    onChange={(e) => setSearchDomain(e.target.value)}
                    className="pl-9"
                  />
                </div>
                <Input
                  placeholder="Add domain (e.g., tempmail.com)"
                  value={newDomain}
                  onChange={(e) => setNewDomain(e.target.value)}
                  className="w-64"
                  onKeyDown={(e) => e.key === "Enter" && handleAddDomain()}
                />
                <Button onClick={handleAddDomain} disabled={!newDomain.trim()}>
                  <Plus className="w-4 h-4 mr-2" />
                  Add
                </Button>
              </div>
              <div className="max-h-64 overflow-y-auto border rounded-md">
                <div className="flex flex-wrap gap-2 p-3">
                  {filteredDomains.slice(0, 100).map((domain) => (
                    <Badge key={domain} variant="secondary" className="flex items-center gap-1">
                      {domain}
                      <button
                        onClick={() => handleRemoveDomain(domain)}
                        className="ml-1 hover:text-destructive"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </Badge>
                  ))}
                  {filteredDomains.length > 100 && (
                    <span className="text-muted-foreground text-sm">
                      +{filteredDomains.length - 100} more
                    </span>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Blocked Emails */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mail className="w-5 h-5" />
                Blocked Emails
              </CardTitle>
              <CardDescription>
                Specific email addresses blocked ({filteredEmails.length})
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    placeholder="Search emails..."
                    value={searchEmail}
                    onChange={(e) => setSearchEmail(e.target.value)}
                    className="pl-9"
                  />
                </div>
                <Input
                  placeholder="Add email address"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  className="w-64"
                  onKeyDown={(e) => e.key === "Enter" && handleAddEmail()}
                />
                <Button onClick={handleAddEmail} disabled={!newEmail.trim()}>
                  <Plus className="w-4 h-4 mr-2" />
                  Add
                </Button>
              </div>
              {filteredEmails.length === 0 ? (
                <p className="text-muted-foreground text-sm py-4 text-center">
                  No blocked emails
                </p>
              ) : (
                <div className="max-h-48 overflow-y-auto border rounded-md">
                  <div className="flex flex-wrap gap-2 p-3">
                    {filteredEmails.map((email) => (
                      <Badge key={email} variant="destructive" className="flex items-center gap-1">
                        {email}
                        <button
                          onClick={() => handleRemoveEmail(email)}
                          className="ml-1 hover:text-white"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Blocked IPs */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Server className="w-5 h-5" />
                Blocked IP Addresses
              </CardTitle>
              <CardDescription>
                IP addresses blocked from all operations ({filteredIPs.length})
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    placeholder="Search IPs..."
                    value={searchIP}
                    onChange={(e) => setSearchIP(e.target.value)}
                    className="pl-9"
                  />
                </div>
                <Input
                  placeholder="Add IP address"
                  value={newIP}
                  onChange={(e) => setNewIP(e.target.value)}
                  className="w-64"
                  onKeyDown={(e) => e.key === "Enter" && handleAddIP()}
                />
                <Button onClick={handleAddIP} disabled={!newIP.trim()}>
                  <Plus className="w-4 h-4 mr-2" />
                  Add
                </Button>
              </div>
              {filteredIPs.length === 0 ? (
                <p className="text-muted-foreground text-sm py-4 text-center">
                  No blocked IPs
                </p>
              ) : (
                <div className="max-h-48 overflow-y-auto border rounded-md">
                  <div className="flex flex-wrap gap-2 p-3">
                    {filteredIPs.map((ip) => (
                      <Badge key={ip} variant="destructive" className="flex items-center gap-1">
                        {ip}
                        <button
                          onClick={() => handleRemoveIP(ip)}
                          className="ml-1 hover:text-white"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* User Overrides Tab */}
        <TabsContent value="overrides" className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <UserCheck className="w-5 h-5" />
                    User Overrides
                  </CardTitle>
                  <CardDescription>
                    Users with custom rate limits or bypass permissions
                  </CardDescription>
                </div>
                <Dialog open={overrideDialogOpen} onOpenChange={setOverrideDialogOpen}>
                  <DialogTrigger asChild>
                    <Button>
                      <Plus className="w-4 h-4 mr-2" />
                      Add Override
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Add User Override</DialogTitle>
                      <DialogDescription>
                        Grant a user custom rate limits or bypass permissions
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Label htmlFor="email">User Email</Label>
                        <Input
                          id="email"
                          placeholder="user@example.com"
                          value={overrideEmail}
                          onChange={(e) => setOverrideEmail(e.target.value)}
                        />
                      </div>
                      <div className="flex items-center space-x-2">
                        <Switch
                          id="bypass"
                          checked={overrideBypass}
                          onCheckedChange={setOverrideBypass}
                        />
                        <Label htmlFor="bypass">Bypass all job limits</Label>
                      </div>
                      {!overrideBypass && (
                        <div className="space-y-2">
                          <Label htmlFor="customLimit">Custom Daily Job Limit (optional)</Label>
                          <Input
                            id="customLimit"
                            type="number"
                            placeholder="Leave empty for default"
                            value={overrideCustomLimit}
                            onChange={(e) => setOverrideCustomLimit(e.target.value)}
                          />
                        </div>
                      )}
                      <div className="space-y-2">
                        <Label htmlFor="reason">Reason</Label>
                        <Textarea
                          id="reason"
                          placeholder="Reason for this override..."
                          value={overrideReason}
                          onChange={(e) => setOverrideReason(e.target.value)}
                        />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setOverrideDialogOpen(false)}>
                        Cancel
                      </Button>
                      <Button onClick={handleAddOverride}>Add Override</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              {!overrides?.overrides.length ? (
                <p className="text-muted-foreground text-sm py-8 text-center">
                  No user overrides configured
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Email</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Reason</TableHead>
                      <TableHead>Created By</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead className="w-[100px]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {overrides.overrides.map((override) => (
                      <TableRow key={override.email}>
                        <TableCell className="font-mono text-sm">{override.email}</TableCell>
                        <TableCell>
                          {override.bypass_job_limit ? (
                            <Badge variant="default">Bypass All</Badge>
                          ) : override.custom_daily_job_limit ? (
                            <Badge variant="secondary">
                              Custom: {override.custom_daily_job_limit}/day
                            </Badge>
                          ) : (
                            <Badge variant="outline">Default</Badge>
                          )}
                        </TableCell>
                        <TableCell className="max-w-[200px] truncate" title={override.reason}>
                          {override.reason}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {override.created_by}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDate(override.created_at)}
                        </TableCell>
                        <TableCell>
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button variant="ghost" size="sm" className="text-destructive">
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Remove Override</AlertDialogTitle>
                                <AlertDialogDescription>
                                  Remove rate limit override for {override.email}? They will be subject
                                  to normal rate limits.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Cancel</AlertDialogCancel>
                                <AlertDialogAction
                                  onClick={() => handleRemoveOverride(override.email)}
                                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                >
                                  Remove
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
