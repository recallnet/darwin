import { Brain } from "lucide-react"

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/50">
      <div className="w-full max-w-md space-y-8 px-4">
        <div className="text-center">
          <div className="flex justify-center">
            <Brain className="h-12 w-12 text-primary" />
          </div>
          <h1 className="mt-4 text-3xl font-bold">Darwin</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            AI-Powered Trading Strategy Research
          </p>
        </div>
        {children}
      </div>
    </div>
  )
}
