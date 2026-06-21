import { Loader2, PenLine, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";

export function LoginView({
  authError,
  isConfigured,
  isLoading,
  signInWithGoogle,
}: {
  authError: string;
  isConfigured: boolean;
  isLoading: boolean;
  signInWithGoogle: () => Promise<void>;
}) {
  return (
    <main className="grid min-h-screen place-items-center bg-[radial-gradient(circle_at_50%_-10%,hsl(214_100%_96%),transparent_42%),linear-gradient(180deg,hsl(0_0%_100%),hsl(210_40%_98%))] px-5">
      <section className="grid w-full max-w-5xl overflow-hidden rounded-lg border bg-background shadow-2xl shadow-slate-950/10 lg:grid-cols-[1fr_420px]">
        <div className="relative min-h-[520px] overflow-hidden bg-slate-950 p-8 text-white md:p-12">
          <div className="absolute inset-0 bg-[linear-gradient(135deg,hsl(213_94%_68%/.22),transparent_42%),radial-gradient(circle_at_18%_18%,hsl(38_92%_55%/.3),transparent_28%)]" />
          <div className="relative z-10 flex h-full flex-col justify-between">
            <div className="flex items-center gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-lg bg-white text-slate-950">
                <PenLine className="h-5 w-5" />
              </div>
              <div>
                <div className="text-2xl font-black tracking-tight">SecondBrain</div>
                <div className="text-sm text-white/65">Private knowledge graph</div>
              </div>
            </div>

            <div>
              <h1 className="max-w-xl text-5xl font-black leading-[0.95] tracking-tight md:text-7xl">
                Your notes stay tied to you.
              </h1>
              <p className="mt-5 max-w-lg text-lg leading-8 text-white/70">
                Sign in with Gmail to digest notes, papers, and graph context into your own isolated memory.
              </p>
            </div>
          </div>
        </div>

        <div className="flex min-h-[520px] flex-col justify-center p-8 md:p-10">
          <div className="mb-8">
            <Sparkles className="mb-5 h-10 w-10 text-primary" />
            <h2 className="text-3xl font-black tracking-tight">Log in or sign up</h2>
            <p className="mt-2 text-muted-foreground">
              Use your Gmail account to create a private SecondBrain workspace.
            </p>
          </div>

          {!isConfigured && (
            <div className="mb-4 rounded-lg border border-destructive/25 bg-destructive/5 p-3 text-sm text-destructive">
              Firebase is missing. Copy frontend/.env.example to frontend/.env.local, fill in
              your Firebase web app values, then restart npm run dev.
            </div>
          )}
          {authError && (
            <div className="mb-4 rounded-lg border border-destructive/25 bg-destructive/5 p-3 text-sm text-destructive">
              {authError}
            </div>
          )}

          <Button
            className="h-12 w-full gap-3 text-base"
            disabled={!isConfigured || isLoading}
            onClick={() => void signInWithGoogle()}
          >
            {isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <span className="grid h-5 w-5 place-items-center rounded-full bg-white text-sm font-black text-slate-950">
                G
              </span>
            )}
            Continue with Google
          </Button>
        </div>
      </section>
    </main>
  );
}
