"use client"

import type React from "react"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/lib/auth"
import { useJobs } from "@/lib/jobs"
import { AppHeader } from "@/components/app-header"
import { ProtectedRoute } from "@/components/protected-route"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Youtube, Upload, AlertCircle, Sparkles } from "lucide-react"

function NewJobContent() {
  const { user, updateCredits } = useAuth()
  const { addJob } = useJobs()
  const router = useRouter()

  const [activeTab, setActiveTab] = useState("youtube")

  // YouTube form state
  const [youtubeUrl, setYoutubeUrl] = useState("")
  const [youtubeArtist, setYoutubeArtist] = useState("")
  const [youtubeTitle, setYoutubeTitle] = useState("")

  // Upload form state
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadArtist, setUploadArtist] = useState("")
  const [uploadTitle, setUploadTitle] = useState("")

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState("")

  if (!user) return null

  const insufficientCredits = user.credits < 1

  const handleYoutubeSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    if (!youtubeUrl.trim()) {
      setError("Please enter a YouTube URL")
      return
    }
    if (!youtubeArtist.trim() || !youtubeTitle.trim()) {
      setError("Please enter both artist and title")
      return
    }

    if (insufficientCredits) {
      setError("Insufficient credits. Please purchase more credits to continue.")
      return
    }

    setIsSubmitting(true)

    // Simulate processing
    setTimeout(() => {
      addJob({
        userId: user.token.includes("demo") ? "demo" : user.token,
        artist: youtubeArtist,
        title: youtubeTitle,
        status: "queued",
        sourceType: "youtube",
        sourceUrl: youtubeUrl,
      })

      updateCredits(user.credits - 1)
      setIsSubmitting(false)
      router.push("/jobs")
    }, 1000)
  }

  const handleUploadSubmit = async (e: React.FormEvent) => {
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

    if (insufficientCredits) {
      setError("Insufficient credits. Please purchase more credits to continue.")
      return
    }

    setIsSubmitting(true)

    // Simulate processing
    setTimeout(() => {
      addJob({
        userId: user.token.includes("demo") ? "demo" : user.token,
        artist: uploadArtist,
        title: uploadTitle,
        status: "queued",
        sourceType: "upload",
        fileName: uploadFile.name,
      })

      updateCredits(user.credits - 1)
      setIsSubmitting(false)
      router.push("/jobs")
    }, 1000)
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      const validTypes = ["audio/mpeg", "audio/wav", "audio/flac", "audio/mp4", "audio/ogg"]
      if (!validTypes.includes(file.type) && !file.name.match(/\.(mp3|wav|flac|m4a|ogg)$/i)) {
        setError("Invalid file type. Please upload MP3, WAV, FLAC, M4A, or OGG files.")
        return
      }
      if (file.size > 50 * 1024 * 1024) {
        // 50MB limit
        setError("File too large. Maximum size is 50MB.")
        return
      }
      setUploadFile(file)
      setError("")
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <AppHeader />

      <main className="container mx-auto px-4 py-8 max-w-3xl">
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-2">Create New Karaoke Video</h1>
          <p className="text-muted-foreground">Start from a YouTube URL or upload your own audio file</p>
        </div>

        {insufficientCredits && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              You don't have enough credits to create a new job.{" "}
              <a href="#" className="underline font-medium">
                Purchase more credits
              </a>{" "}
              to continue.
            </AlertDescription>
          </Alert>
        )}

        <Card className="border-border/50">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Source Selection</CardTitle>
                <CardDescription>Choose how you want to provide the audio</CardDescription>
              </div>
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-primary/10 border border-primary/20">
                <Sparkles className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium text-primary">Cost: 1 credit</span>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="youtube" className="gap-2">
                  <Youtube className="w-4 h-4" />
                  From YouTube URL
                </TabsTrigger>
                <TabsTrigger value="upload" className="gap-2">
                  <Upload className="w-4 h-4" />
                  Upload Audio File
                </TabsTrigger>
              </TabsList>

              <TabsContent value="youtube" className="mt-6">
                <form onSubmit={handleYoutubeSubmit} className="space-y-6">
                  <div className="space-y-2">
                    <Label htmlFor="youtube-url">YouTube URL</Label>
                    <div className="relative">
                      <Youtube className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <Input
                        id="youtube-url"
                        type="url"
                        placeholder="https://youtube.com/watch?v=..."
                        value={youtubeUrl}
                        onChange={(e) => setYoutubeUrl(e.target.value)}
                        className="pl-10"
                        disabled={isSubmitting}
                      />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Paste the URL of the YouTube video you want to convert
                    </p>
                  </div>

                  <div className="grid md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="youtube-artist">Artist Name</Label>
                      <Input
                        id="youtube-artist"
                        type="text"
                        placeholder="Artist name"
                        value={youtubeArtist}
                        onChange={(e) => setYoutubeArtist(e.target.value)}
                        disabled={isSubmitting}
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="youtube-title">Song Title</Label>
                      <Input
                        id="youtube-title"
                        type="text"
                        placeholder="Song title"
                        value={youtubeTitle}
                        onChange={(e) => setYoutubeTitle(e.target.value)}
                        disabled={isSubmitting}
                      />
                    </div>
                  </div>

                  {error && (
                    <Alert variant="destructive">
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription>{error}</AlertDescription>
                    </Alert>
                  )}

                  <div className="flex gap-3">
                    <Button
                      type="submit"
                      className="flex-1 bg-primary hover:bg-primary/90"
                      disabled={isSubmitting || insufficientCredits}
                    >
                      {isSubmitting ? "Creating Job..." : "Create Karaoke Video"}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => router.push("/dashboard")}
                      disabled={isSubmitting}
                    >
                      Cancel
                    </Button>
                  </div>
                </form>
              </TabsContent>

              <TabsContent value="upload" className="mt-6">
                <form onSubmit={handleUploadSubmit} className="space-y-6">
                  <div className="space-y-2">
                    <Label htmlFor="audio-file">Audio File</Label>
                    <div
                      className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                        uploadFile
                          ? "border-primary bg-primary/5"
                          : "border-border hover:border-primary/50 hover:bg-card/50"
                      }`}
                    >
                      <Input
                        id="audio-file"
                        type="file"
                        accept=".mp3,.wav,.flac,.m4a,.ogg,audio/*"
                        onChange={handleFileChange}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                        disabled={isSubmitting}
                      />
                      <Upload className="w-8 h-8 mx-auto mb-2 text-muted-foreground" />
                      {uploadFile ? (
                        <div>
                          <p className="font-medium text-foreground">{uploadFile.name}</p>
                          <p className="text-sm text-muted-foreground">
                            {(uploadFile.size / 1024 / 1024).toFixed(2)} MB
                          </p>
                        </div>
                      ) : (
                        <div>
                          <p className="font-medium text-foreground mb-1">Click to upload or drag and drop</p>
                          <p className="text-sm text-muted-foreground">MP3, WAV, FLAC, M4A, or OGG (max 50MB)</p>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="grid md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="upload-artist">
                        Artist Name <span className="text-destructive">*</span>
                      </Label>
                      <Input
                        id="upload-artist"
                        type="text"
                        placeholder="Artist name"
                        value={uploadArtist}
                        onChange={(e) => setUploadArtist(e.target.value)}
                        required
                        disabled={isSubmitting}
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="upload-title">
                        Song Title <span className="text-destructive">*</span>
                      </Label>
                      <Input
                        id="upload-title"
                        type="text"
                        placeholder="Song title"
                        value={uploadTitle}
                        onChange={(e) => setUploadTitle(e.target.value)}
                        required
                        disabled={isSubmitting}
                      />
                    </div>
                  </div>

                  {error && (
                    <Alert variant="destructive">
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription>{error}</AlertDescription>
                    </Alert>
                  )}

                  <div className="flex gap-3">
                    <Button
                      type="submit"
                      className="flex-1 bg-primary hover:bg-primary/90"
                      disabled={isSubmitting || insufficientCredits}
                    >
                      {isSubmitting ? "Creating Job..." : "Create Karaoke Video"}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => router.push("/dashboard")}
                      disabled={isSubmitting}
                    >
                      Cancel
                    </Button>
                  </div>
                </form>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}

export default function NewJobPage() {
  return (
    <ProtectedRoute>
      <NewJobContent />
    </ProtectedRoute>
  )
}
