"use client"

import type React from "react"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/lib/auth"
import { Logo } from "@/components/logo"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Mic2, Sparkles, Zap, Globe } from "lucide-react"

export default function LandingPage() {
  const [token, setToken] = useState("")
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const { login } = useAuth()
  const router = useRouter()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setIsLoading(true)

    if (!token.trim()) {
      setError("Please enter your access token")
      setIsLoading(false)
      return
    }

    const success = await login(token)
    setIsLoading(false)

    if (success) {
      router.push("/dashboard")
    } else {
      setError("Invalid token. Please try again.")
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-background via-background to-card">
      {/* Animated background effects */}
      <div className="fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-secondary/10 rounded-full blur-3xl animate-pulse delay-1000" />
      </div>

      <div className="container mx-auto px-4 py-12">
        {/* Header */}
        <header className="flex justify-center mb-20">
          <Logo className="scale-150" />
        </header>

        {/* Hero Section */}
        <div className="max-w-4xl mx-auto text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-8">
            <Sparkles className="w-4 h-4 text-primary" />
            <span className="text-sm text-primary font-medium">AI-Powered Karaoke Generation</span>
          </div>

          <h1 className="text-5xl md:text-7xl font-bold mb-6 text-balance leading-tight">
            Wherever you are,
            <br />
            <span className="text-primary">sing!</span>
          </h1>

          <p className="text-xl text-muted-foreground mb-12 text-pretty max-w-2xl mx-auto leading-relaxed">
            Transform any song into professional karaoke videos with AI-powered vocal separation, synchronized lyrics,
            and stunning visuals.
          </p>

          {/* Login Card */}
          <Card className="max-w-md mx-auto border-border/50 backdrop-blur">
            <CardHeader>
              <CardTitle className="text-2xl">Get Started</CardTitle>
              <CardDescription>Enter your access token to begin creating karaoke videos</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleLogin} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="token">Access Token</Label>
                  <Input
                    id="token"
                    type="text"
                    placeholder="Enter your token"
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                    className="bg-background"
                  />
                  {error && <p className="text-sm text-destructive">{error}</p>}
                </div>

                <Button type="submit" className="w-full bg-primary hover:bg-primary/90" disabled={isLoading}>
                  {isLoading ? "Logging in..." : "Login"}
                </Button>

                <div className="text-center text-sm text-muted-foreground">
                  Don't have access?{" "}
                  <a href="#" className="text-primary hover:underline">
                    Request a token
                  </a>{" "}
                  or{" "}
                  <a href="#" className="text-primary hover:underline">
                    purchase access
                  </a>
                </div>

                <div className="pt-4 border-t border-border">
                  <p className="text-xs text-muted-foreground mb-2">Demo tokens:</p>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="flex-1 text-xs bg-transparent"
                      onClick={() => setToken("demo-user-token")}
                    >
                      User Demo
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="flex-1 text-xs bg-transparent"
                      onClick={() => setToken("demo-admin-token")}
                    >
                      Admin Demo
                    </Button>
                  </div>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Features Grid */}
        <div className="max-w-5xl mx-auto mt-24">
          <div className="grid md:grid-cols-3 gap-8">
            <Card className="bg-card/50 backdrop-blur border-border/50">
              <CardHeader>
                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                  <Mic2 className="w-6 h-6 text-primary" />
                </div>
                <CardTitle className="text-xl">AI Vocal Separation</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground leading-relaxed">
                  Advanced AI removes vocals from any track, creating perfect instrumental versions for karaoke.
                </p>
              </CardContent>
            </Card>

            <Card className="bg-card/50 backdrop-blur border-border/50">
              <CardHeader>
                <div className="w-12 h-12 rounded-lg bg-secondary/10 flex items-center justify-center mb-4">
                  <Zap className="w-6 h-6 text-secondary" />
                </div>
                <CardTitle className="text-xl">Instant Generation</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground leading-relaxed">
                  From YouTube URL or audio file to finished karaoke video in minutes, not hours.
                </p>
              </CardContent>
            </Card>

            <Card className="bg-card/50 backdrop-blur border-border/50">
              <CardHeader>
                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                  <Globe className="w-6 h-6 text-primary" />
                </div>
                <CardTitle className="text-xl">Cloud-Based</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground leading-relaxed">
                  Access your karaoke library anywhere, anytime. No downloads or installations required.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
