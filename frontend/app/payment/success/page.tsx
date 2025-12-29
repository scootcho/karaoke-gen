"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { CheckCircle, Loader2, Coins } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth"

function PaymentSuccessContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [isLoading, setIsLoading] = useState(true)

  const { user, fetchUser } = useAuth()

  useEffect(() => {
    // Refresh user data to get updated credits
    const refreshUser = async () => {
      await fetchUser()
      setIsLoading(false)
    }
    refreshUser()
  }, [fetchUser])

  const sessionId = searchParams.get("session_id")

  return (
    <div className="max-w-md w-full bg-slate-900 border border-slate-700 rounded-xl p-8 text-center">
      <CheckCircle className="w-16 h-16 text-green-400 mx-auto mb-4" />

      <h1 className="text-2xl font-bold text-white mb-2">
        Payment Successful!
      </h1>

      <p className="text-slate-400 mb-6">
        Thank you for your purchase. Your credits have been added to your account.
      </p>

      {isLoading ? (
        <div className="flex items-center justify-center gap-2 text-slate-400 mb-6">
          <Loader2 className="w-4 h-4 animate-spin" />
          Loading your balance...
        </div>
      ) : user ? (
        <div className="bg-slate-800 rounded-lg p-4 mb-6">
          <div className="flex items-center justify-center gap-2 text-amber-400">
            <Coins className="w-5 h-5" />
            <span className="text-2xl font-bold">{user.credits}</span>
            <span className="text-slate-400">credits available</span>
          </div>
        </div>
      ) : null}

      <div className="space-y-3">
        <Button
          onClick={() => router.push("/app")}
          className="w-full bg-blue-600 hover:bg-blue-500"
        >
          Start Creating Karaoke
        </Button>

        <p className="text-xs text-slate-500">
          A confirmation email has been sent to your email address.
        </p>
      </div>
    </div>
  )
}

export default function PaymentSuccessPage() {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <Suspense
        fallback={
          <div className="max-w-md w-full bg-slate-900 border border-slate-700 rounded-xl p-8 text-center">
            <Loader2 className="w-16 h-16 text-blue-400 mx-auto mb-4 animate-spin" />
            <p className="text-slate-400">Loading...</p>
          </div>
        }
      >
        <PaymentSuccessContent />
      </Suspense>
    </div>
  )
}
