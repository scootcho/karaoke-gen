"use client"

import { Suspense, useEffect } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { Spinner } from "@/components/ui/spinner"

/**
 * Compatibility route for legacy instrumental review URLs.
 *
 * Handles URLs like:
 *   /instrumental/?baseApiUrl=https://api.nomadkaraoke.com/api/jobs/{job_id}&instrumentalToken=...
 *
 * Redirects to:
 *   /app/jobs/{job_id}/instrumental
 *
 * This maintains backward compatibility with:
 * - Remote CLI (karaoke-gen-remote)
 * - Email notifications with instrumental selection links
 * - Any existing bookmarks or shared links
 */
function InstrumentalRedirectContent() {
  const searchParams = useSearchParams()
  const router = useRouter()

  useEffect(() => {
    const baseApiUrl = searchParams.get("baseApiUrl")

    if (!baseApiUrl) {
      // No baseApiUrl provided, redirect to dashboard
      router.replace("/app")
      return
    }

    // Extract job ID from baseApiUrl
    // Expected format: https://api.nomadkaraoke.com/api/jobs/{job_id}
    try {
      const url = new URL(baseApiUrl)
      const pathParts = url.pathname.split("/").filter(Boolean)

      // Find the job ID - it's the last segment after /jobs/
      let jobId: string | null = null

      for (let i = 0; i < pathParts.length; i++) {
        if (pathParts[i] === "jobs" && pathParts[i + 1]) {
          jobId = pathParts[i + 1]
          break
        }
      }

      if (jobId) {
        // Redirect to new consolidated route
        router.replace(`/app/jobs/${jobId}/instrumental`)
      } else {
        // Couldn't parse job ID, redirect to dashboard
        console.error("Could not extract job ID from baseApiUrl:", baseApiUrl)
        router.replace("/app")
      }
    } catch (error) {
      console.error("Failed to parse baseApiUrl:", error)
      router.replace("/app")
    }
  }, [searchParams, router])

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        <Spinner className="w-8 h-8 mx-auto mb-4" />
        <p className="text-muted-foreground">Redirecting to instrumental selection...</p>
      </div>
    </div>
  )
}

export default function InstrumentalRedirectPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center">
            <Spinner className="w-8 h-8 mx-auto mb-4" />
            <p className="text-muted-foreground">Loading...</p>
          </div>
        </div>
      }
    >
      <InstrumentalRedirectContent />
    </Suspense>
  )
}
