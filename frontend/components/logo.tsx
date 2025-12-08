import Image from "next/image"

export function Logo({ className = "", size = "sm" }: { className?: string; size?: "sm" | "lg" }) {
  const sizeClasses = size === "lg" ? "max-w-[600px] max-h-[120px]" : "max-w-[200px] max-h-10"

  return (
    <div className={`flex items-center ${className}`}>
      <Image
        src="https://nomadkaraoke.com/wp-content/uploads/2024/07/Nomad-Karaoke-Logo-TextOnly-Cropped-FromSVG-HQ-2048x1088.png"
        alt="Nomad Karaoke"
        width={200}
        height={106}
        className={`w-auto h-auto ${sizeClasses} object-contain`}
        priority
      />
    </div>
  )
}
