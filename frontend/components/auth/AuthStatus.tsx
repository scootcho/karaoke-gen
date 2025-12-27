"use client"

import { useState, useEffect } from "react"
import { KeyRound, LogOut } from "lucide-react"
import { Button } from "@/components/ui/button"
import { getAccessToken, clearAccessToken } from "@/lib/api"
import { AuthDialog } from "./AuthDialog"

interface AuthStatusProps {
  onAuthChange?: () => void
}

export function AuthStatus({ onAuthChange }: AuthStatusProps) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [showAuthDialog, setShowAuthDialog] = useState(false)

  useEffect(() => {
    setIsAuthenticated(!!getAccessToken())
  }, [])

  const handleLogout = () => {
    clearAccessToken()
    setIsAuthenticated(false)
    onAuthChange?.()
    window.location.reload()
  }

  const handleAuthSuccess = () => {
    setIsAuthenticated(true)
    setShowAuthDialog(false)
    onAuthChange?.()
    window.location.reload()
  }

  if (isAuthenticated) {
    return (
      <Button
        variant="ghost"
        size="sm"
        onClick={handleLogout}
        className="text-slate-400 hover:text-white"
      >
        <LogOut className="w-4 h-4 mr-2" />
        Logout
      </Button>
    )
  }

  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setShowAuthDialog(true)}
        className="text-amber-400 hover:text-amber-300"
      >
        <KeyRound className="w-4 h-4 mr-2" />
        Login
      </Button>
      <AuthDialog
        open={showAuthDialog}
        onClose={() => setShowAuthDialog(false)}
        onSuccess={handleAuthSuccess}
      />
    </>
  )
}
