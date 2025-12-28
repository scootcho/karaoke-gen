"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Loader2, CheckCircle, XCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth"

type VerifyState = "loading" | "success" | "error"

function VerifyMagicLinkContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [state, setState] = useState<VerifyState>("loading")
  const [errorMessage, setErrorMessage] = useState("")

  const { verifyMagicLink, user, error } = useAuth()

  useEffect(() => {
    const token = searchParams.get("token")

    if (!token) {
      setState("error")
      setErrorMessage("No verification token provided")
      return
    }

    // Verify the token
    const verify = async () => {
      const success = await verifyMagicLink(token)
      if (success) {
        setState("success")
        // Redirect to main app after short delay
        setTimeout(() => {
          router.push("/")
        }, 2000)
      } else {
        setState("error")
        setErrorMessage(error || "Invalid or expired link")
      }
    }

    verify()
  }, [searchParams, verifyMagicLink, router, error])

  return (
    <div className="max-w-md w-full bg-slate-900 border border-slate-700 rounded-xl p-8 text-center">
      {state === "loading" && (
        <>
          <Loader2 className="w-12 h-12 text-blue-400 animate-spin mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-white mb-2">
            Verifying your sign-in link...
          </h1>
          <p className="text-slate-400">
            Please wait while we sign you in.
          </p>
        </>
      )}

      {state === "success" && (
        <>
          <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-white mb-2">
            Successfully signed in!
          </h1>
          <p className="text-slate-400 mb-4">
            Welcome back{user?.email ? `, ${user.email}` : ""}!
          </p>
          <p className="text-sm text-slate-500">
            Redirecting you to the app...
          </p>
        </>
      )}

      {state === "error" && (
        <>
          <XCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-white mb-2">
            Sign-in failed
          </h1>
          <p className="text-slate-400 mb-6">
            {errorMessage || "The link may have expired or already been used."}
          </p>
          <div className="space-y-2">
            <Button
              onClick={() => router.push("/")}
              className="w-full bg-blue-600 hover:bg-blue-500"
            >
              Go to App
            </Button>
            <p className="text-xs text-slate-500">
              You can request a new sign-in link from the app.
            </p>
          </div>
        </>
      )}
    </div>
  )
}

function VerifyLoadingFallback() {
  return (
    <div className="max-w-md w-full bg-slate-900 border border-slate-700 rounded-xl p-8 text-center">
      <Loader2 className="w-12 h-12 text-blue-400 animate-spin mx-auto mb-4" />
      <h1 className="text-xl font-semibold text-white mb-2">
        Loading...
      </h1>
      <p className="text-slate-400">
        Please wait.
      </p>
    </div>
  )
}

export default function VerifyMagicLinkPage() {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <Suspense fallback={<VerifyLoadingFallback />}>
        <VerifyMagicLinkContent />
      </Suspense>
    </div>
  )
}
