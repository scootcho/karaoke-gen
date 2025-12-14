"use client"

import { useParams, useRouter } from "next/navigation"
import { useState, useEffect, useCallback } from "react"
import { AppHeader } from "@/components/app-header"
import { ProtectedRoute } from "@/components/protected-route"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import {
  WaveformDisplay,
  AudioPlayer,
  RegionSelector,
} from "@/components/instrumental-review"
import {
  ArrowLeft,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Music,
  VolumeX,
  Volume2,
} from "lucide-react"

interface AudibleSegment {
  start_seconds: number
  end_seconds: number
  duration_seconds: number
  avg_amplitude_db: number
  peak_amplitude_db?: number
}

interface MuteRegion {
  start_seconds: number
  end_seconds: number
}

interface AnalysisData {
  has_audible_content: boolean
  total_duration_seconds: number
  audible_segments: AudibleSegment[]
  recommended_selection: string
  total_audible_duration_seconds: number
  audible_percentage: number
  silence_threshold_db: number
}

interface InstrumentalAnalysisResponse {
  job_id: string
  artist: string
  title: string
  status: string
  analysis: AnalysisData
  audio_urls: {
    clean_instrumental: string | null
    backing_vocals: string | null
    with_backing: string | null
    custom_instrumental: string | null
  }
  waveform_url: string | null
  has_custom_instrumental: boolean
}

// Get API base URL from environment or default to relative path
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api"

function InstrumentalReviewContent() {
  const params = useParams()
  const router = useRouter()
  const jobId = params.id as string

  // State
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [analysisData, setAnalysisData] = useState<InstrumentalAnalysisResponse | null>(null)
  const [waveformData, setWaveformData] = useState<{ amplitudes: number[]; duration: number } | null>(null)
  
  const [selectedOption, setSelectedOption] = useState<string>("clean")
  const [muteRegions, setMuteRegions] = useState<MuteRegion[]>([])
  const [isSelectionMode, setIsSelectionMode] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [seekTo, setSeekTo] = useState<number | undefined>(undefined)
  
  const [isCreatingCustom, setIsCreatingCustom] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [activeAudio, setActiveAudio] = useState<"clean" | "backing" | "with_backing" | "custom">("backing")

  // Fetch analysis data
  const fetchAnalysis = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)

      const response = await fetch(`${API_BASE}/jobs/${jobId}/instrumental-analysis`)
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Failed to fetch analysis: ${response.status}`)
      }

      const data: InstrumentalAnalysisResponse = await response.json()
      setAnalysisData(data)

      // Set initial selection based on recommendation
      const recommendation = data.analysis.recommended_selection
      if (recommendation === "clean") {
        setSelectedOption("clean")
      } else if (recommendation === "with_backing") {
        setSelectedOption("with_backing")
      } else {
        // "review_needed" - default to with_backing but user should review
        setSelectedOption("with_backing")
      }

      // Fetch waveform data for interactive display
      const waveformResponse = await fetch(`${API_BASE}/jobs/${jobId}/waveform-data?num_points=600`)
      if (waveformResponse.ok) {
        const waveform = await waveformResponse.json()
        setWaveformData(waveform)
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load analysis data")
    } finally {
      setIsLoading(false)
    }
  }, [jobId])

  useEffect(() => {
    fetchAnalysis()
  }, [fetchAnalysis])

  // Handle seeking from waveform click
  const handleSeek = (time: number) => {
    setSeekTo(time)
    // Reset seekTo after a short delay
    setTimeout(() => setSeekTo(undefined), 100)
  }

  // Handle adding a mute region
  const handleAddRegion = (region: MuteRegion) => {
    setMuteRegions((prev) => {
      // Check for overlaps and merge if needed
      const newRegions = [...prev, region].sort((a, b) => a.start_seconds - b.start_seconds)
      
      // Merge overlapping regions
      const merged: MuteRegion[] = []
      for (const r of newRegions) {
        if (merged.length === 0) {
          merged.push(r)
        } else {
          const last = merged[merged.length - 1]
          if (r.start_seconds <= last.end_seconds) {
            last.end_seconds = Math.max(last.end_seconds, r.end_seconds)
          } else {
            merged.push(r)
          }
        }
      }
      return merged
    })
    setIsSelectionMode(false)
  }

  // Handle removing a mute region
  const handleRemoveRegion = (index: number) => {
    setMuteRegions((prev) => prev.filter((_, i) => i !== index))
  }

  // Handle clearing all mute regions
  const handleClearAll = () => {
    setMuteRegions([])
  }

  // Create custom instrumental
  const handleCreateCustom = async () => {
    if (muteRegions.length === 0) {
      setError("Please select at least one region to mute")
      return
    }

    try {
      setIsCreatingCustom(true)
      setError(null)

      const response = await fetch(`${API_BASE}/jobs/${jobId}/create-custom-instrumental`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mute_regions: muteRegions.map((r) => ({
            start_seconds: r.start_seconds,
            end_seconds: r.end_seconds,
          })),
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || "Failed to create custom instrumental")
      }

      // Refresh analysis to get updated URLs
      await fetchAnalysis()
      setSelectedOption("custom")
      setActiveAudio("custom")

    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create custom instrumental")
    } finally {
      setIsCreatingCustom(false)
    }
  }

  // Submit selection
  const handleSubmit = async () => {
    let selection = selectedOption
    
    // If "review" is selected, determine based on mute regions
    if (selectedOption === "review") {
      if (muteRegions.length > 0 && analysisData?.has_custom_instrumental) {
        selection = "custom"
      } else {
        selection = "with_backing"
      }
    }

    try {
      setIsSubmitting(true)
      setError(null)

      const response = await fetch(`${API_BASE}/jobs/${jobId}/select-instrumental`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selection }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || "Failed to submit selection")
      }

      // Navigate back to job page
      router.push(`/jobs/${jobId}`)

    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit selection")
    } finally {
      setIsSubmitting(false)
    }
  }

  // Get current audio URL based on active selection
  const getCurrentAudioUrl = () => {
    if (!analysisData) return null
    switch (activeAudio) {
      case "clean":
        return analysisData.audio_urls.clean_instrumental
      case "backing":
        return analysisData.audio_urls.backing_vocals
      case "with_backing":
        return analysisData.audio_urls.with_backing
      case "custom":
        return analysisData.audio_urls.custom_instrumental
      default:
        return null
    }
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <AppHeader />
        <main className="container mx-auto px-4 py-8 max-w-5xl">
          <Skeleton className="h-8 w-48 mb-4" />
          <Skeleton className="h-4 w-96 mb-8" />
          <Skeleton className="h-[200px] w-full mb-4" />
          <Skeleton className="h-32 w-full" />
        </main>
      </div>
    )
  }

  // Error state
  if (error && !analysisData) {
    return (
      <div className="min-h-screen bg-background">
        <AppHeader />
        <main className="container mx-auto px-4 py-8 max-w-5xl">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
          <Button variant="outline" className="mt-4" onClick={() => router.push(`/jobs/${jobId}`)}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Job
          </Button>
        </main>
      </div>
    )
  }

  const analysis = analysisData?.analysis

  return (
    <div className="min-h-screen bg-background">
      <AppHeader />

      <main className="container mx-auto px-4 py-8 max-w-6xl">
        {/* Header */}
        <Button variant="ghost" className="mb-6" onClick={() => router.push(`/jobs/${jobId}`)}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Job
        </Button>

        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">
            Select Instrumental Track
          </h1>
          <p className="text-muted-foreground">
            {analysisData?.artist} - {analysisData?.title}
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Analysis Summary */}
        {analysis && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Music className="h-5 w-5" />
                Backing Vocals Analysis
              </CardTitle>
              <CardDescription>
                Automated analysis of the backing vocals stem
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-4">
                <div className="flex items-center gap-2">
                  {analysis.has_audible_content ? (
                    <Volume2 className="h-4 w-4 text-yellow-500" />
                  ) : (
                    <VolumeX className="h-4 w-4 text-green-500" />
                  )}
                  <span className="text-sm">
                    {analysis.has_audible_content
                      ? "Backing vocals detected"
                      : "No backing vocals detected"}
                  </span>
                </div>
                
                {analysis.has_audible_content && (
                  <>
                    <Badge variant="outline">
                      {analysis.audible_segments.length} audible segments
                    </Badge>
                    <Badge variant="outline">
                      {analysis.audible_percentage.toFixed(1)}% of track
                    </Badge>
                    <Badge variant="outline">
                      {analysis.total_audible_duration_seconds.toFixed(1)}s total
                    </Badge>
                  </>
                )}

                <Badge
                  variant={analysis.recommended_selection === "clean" ? "default" : "secondary"}
                >
                  Recommended: {analysis.recommended_selection === "clean" ? "Clean Instrumental" : "Review Needed"}
                </Badge>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Waveform Display */}
        {waveformData && analysis && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg">Backing Vocals Waveform</CardTitle>
              <CardDescription>
                Click to seek • {isSelectionMode ? "Drag to select mute region" : "Click 'Add Region' to start selecting"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <WaveformDisplay
                amplitudes={waveformData.amplitudes}
                duration={waveformData.duration}
                currentTime={currentTime}
                segments={analysis.audible_segments}
                muteRegions={muteRegions}
                onSeek={handleSeek}
                onRegionSelect={handleAddRegion}
                isSelecting={isSelectionMode}
                width={900}
                height={150}
                className="w-full overflow-x-auto"
              />
            </CardContent>
          </Card>
        )}

        <div className="grid lg:grid-cols-2 gap-6 mb-6">
          {/* Audio Players */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Audio Preview</CardTitle>
              <CardDescription>
                Listen to different instrumental options
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Audio source selector */}
              <div className="flex flex-wrap gap-2">
                <Button
                  variant={activeAudio === "backing" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActiveAudio("backing")}
                >
                  Backing Vocals
                </Button>
                <Button
                  variant={activeAudio === "clean" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActiveAudio("clean")}
                >
                  Clean Instrumental
                </Button>
                <Button
                  variant={activeAudio === "with_backing" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActiveAudio("with_backing")}
                >
                  With Backing
                </Button>
                {analysisData?.has_custom_instrumental && (
                  <Button
                    variant={activeAudio === "custom" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setActiveAudio("custom")}
                  >
                    Custom
                  </Button>
                )}
              </div>

              {/* Audio player */}
              {getCurrentAudioUrl() && (
                <AudioPlayer
                  src={getCurrentAudioUrl()!}
                  onTimeUpdate={setCurrentTime}
                  seekTo={seekTo}
                  label={
                    activeAudio === "backing"
                      ? "Backing Vocals Only"
                      : activeAudio === "clean"
                      ? "Clean Instrumental"
                      : activeAudio === "custom"
                      ? "Custom Instrumental"
                      : "Instrumental + Backing Vocals"
                  }
                />
              )}
            </CardContent>
          </Card>

          {/* Region Selector */}
          <RegionSelector
            muteRegions={muteRegions}
            audibleSegments={analysis?.audible_segments}
            onAddRegion={handleAddRegion}
            onRemoveRegion={handleRemoveRegion}
            onClearAll={handleClearAll}
            onSeekTo={handleSeek}
            isSelectionMode={isSelectionMode}
            onToggleSelectionMode={() => setIsSelectionMode(!isSelectionMode)}
          />
        </div>

        {/* Create Custom Button */}
        {muteRegions.length > 0 && !analysisData?.has_custom_instrumental && (
          <Card className="mb-6">
            <CardContent className="py-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Ready to create custom instrumental</p>
                  <p className="text-sm text-muted-foreground">
                    {muteRegions.length} region{muteRegions.length > 1 ? "s" : ""} will be muted
                  </p>
                </div>
                <Button onClick={handleCreateCustom} disabled={isCreatingCustom}>
                  {isCreatingCustom ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    "Create Custom Instrumental"
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Selection Options */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">Final Selection</CardTitle>
            <CardDescription>
              Choose which instrumental to use for your karaoke video
            </CardDescription>
          </CardHeader>
          <CardContent>
            <RadioGroup value={selectedOption} onValueChange={setSelectedOption}>
              <div className="space-y-4">
                <div className="flex items-center space-x-3">
                  <RadioGroupItem value="clean" id="clean" />
                  <Label htmlFor="clean" className="flex-1 cursor-pointer">
                    <div className="font-medium">Clean Instrumental</div>
                    <div className="text-sm text-muted-foreground">
                      Use the instrumental with no backing vocals at all
                    </div>
                  </Label>
                  {analysis?.recommended_selection === "clean" && (
                    <Badge variant="default" className="bg-green-600">
                      <CheckCircle2 className="h-3 w-3 mr-1" />
                      Recommended
                    </Badge>
                  )}
                </div>

                <div className="flex items-center space-x-3">
                  <RadioGroupItem value="with_backing" id="with_backing" />
                  <Label htmlFor="with_backing" className="flex-1 cursor-pointer">
                    <div className="font-medium">Instrumental with Backing Vocals</div>
                    <div className="text-sm text-muted-foreground">
                      Use the instrumental with all backing vocals included
                    </div>
                  </Label>
                </div>

                {analysisData?.has_custom_instrumental && (
                  <div className="flex items-center space-x-3">
                    <RadioGroupItem value="custom" id="custom" />
                    <Label htmlFor="custom" className="flex-1 cursor-pointer">
                      <div className="font-medium">Custom Instrumental</div>
                      <div className="text-sm text-muted-foreground">
                        Use your custom instrumental with {muteRegions.length} muted region{muteRegions.length > 1 ? "s" : ""}
                      </div>
                    </Label>
                    <Badge variant="secondary">Custom</Badge>
                  </div>
                )}
              </div>
            </RadioGroup>
          </CardContent>
        </Card>

        {/* Submit Button */}
        <div className="flex gap-4">
          <Button
            size="lg"
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="flex-1 max-w-md"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Submitting...
              </>
            ) : (
              <>
                <CheckCircle2 className="h-4 w-4 mr-2" />
                Confirm Selection & Continue
              </>
            )}
          </Button>
        </div>
      </main>
    </div>
  )
}

export default function InstrumentalReviewPage() {
  return (
    <ProtectedRoute>
      <InstrumentalReviewContent />
    </ProtectedRoute>
  )
}
