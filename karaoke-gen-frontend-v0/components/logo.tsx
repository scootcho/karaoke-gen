export function Logo({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="relative">
        <div className="text-2xl font-bold tracking-tight">
          <span className="text-foreground">NOMAD</span>
          <span className="text-primary ml-1">KARAOKE</span>
        </div>
        <div className="absolute inset-0 -z-10 bg-gradient-to-r from-primary/20 to-secondary/20 blur-xl" />
      </div>
    </div>
  )
}
