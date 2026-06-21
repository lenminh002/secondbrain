import { useState } from "react";
import { LogIn, Brain } from "lucide-react";

interface LoginViewProps {
  onLogin: () => Promise<void>;
}

function googleSignInErrorMessage(error: unknown) {
  if (typeof error === "object" && error !== null && "code" in error) {
    const code = String((error as { code?: unknown }).code);
    if (code === "auth/popup-blocked") {
      return "Your browser blocked the Google sign-in popup. Allow popups for this site and try again.";
    }
    if (code === "auth/unauthorized-domain") {
      return "This local URL is not authorized in Firebase Authentication. Use localhost or add this domain in Firebase.";
    }
    if (code === "auth/popup-closed-by-user") {
      return "Google sign-in was closed before it completed.";
    }
    return `Google sign-in failed: ${code}`;
  }

  return "Failed to sign in with Google. Please try again.";
}

export function LoginView({ onLogin }: LoginViewProps) {
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async () => {
    setIsLoggingIn(true);
    setError(null);
    try {
      await onLogin();
    } catch (err: unknown) {
      console.error(err);
      setError(googleSignInErrorMessage(err));
      setIsLoggingIn(false);
    }
  };

  return (
    <div className="login-container">
      {/* Dynamic Background Blobs */}
      <div className="blob blob-1"></div>
      <div className="blob blob-2"></div>
      <div className="blob blob-3"></div>

      <div className="glass-card animate-fade-in">
        <div className="flex flex-col items-center text-center">
          {/* Logo */}
          <div className="logo-badge mb-6">
            <Brain className="h-10 w-10 text-primary-600 animate-pulse-subtle" />
          </div>

          {/* Title */}
          <h1 className="title-text">SecondBrain</h1>
          <p className="subtitle-text">
            Your personal knowledge graph and AI-powered research assistant.
          </p>

          {error && (
            <div className="error-badge mb-4 animate-shake">
              {error}
            </div>
          )}

          {/* Google Sign In Button */}
          <button
            onClick={handleLogin}
            disabled={isLoggingIn}
            className="google-btn group"
            id="google-signin-btn"
          >
            {isLoggingIn ? (
              <div className="spinner mr-3"></div>
            ) : (
              <svg
                className="mr-3 h-5 w-5 transition-transform duration-300 group-hover:scale-110"
                viewBox="0 0 24 24"
                width="24px"
                height="24px"
              >
                <path
                  fill="#EA4335"
                  d="M5.266,9.765C6.199,6.977,8.813,5,11.897,5c1.868,0,3.51,0.732,4.733,1.92l3.415-3.415 C17.92,1.528,15.08,0,11.897,0C7.234,0,3.228,2.782,1.401,6.809L5.266,9.765z"
                />
                <path
                  fill="#34A853"
                  d="M16.04,18.013c-1.09,0.693-2.454,1.096-4.143,1.096c-3.084,0-5.698-1.977-6.631-4.765l-3.865,2.956 C3.228,21.218,7.234,24,11.897,24c3.344,0,6.299-1.12,8.441-3.052L16.04,18.013z"
                />
                <path
                  fill="#4A90E2"
                  d="M23.518,12.316c0-0.817-0.076-1.604-0.218-2.362H11.897v4.524h6.518c-0.281,1.503-1.125,2.778-2.391,3.633 l4.298,3.298C22.846,19.124,23.518,15.992,23.518,12.316z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.266,9.765L1.401,6.809C0.528,8.74,0,10.902,0,13.191c0,2.29,0.528,4.452,1.401,6.383l3.866-2.956 C5.093,15.421,5,14.322,5,13.191C5,12.06,5.093,10.961,5.266,9.765z"
                />
              </svg>
            )}
            <span>{isLoggingIn ? "Signing in..." : "Sign in with Google"}</span>
          </button>

          <div className="mt-8 flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
            <LogIn className="h-3 w-3" />
            <span>Secure authentication via Google Firebase</span>
          </div>
        </div>
      </div>

      <style>{`
        .login-container {
          position: fixed;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--color-background);
          overflow: hidden;
          font-family: 'Outfit', 'Inter', sans-serif;
          z-index: 9999;
        }

        /* Glowing Orbs */
        .blob {
          position: absolute;
          border-radius: 50%;
          filter: blur(120px);
          opacity: 0.4;
          mix-blend-mode: multiply;
          pointer-events: none;
        }
        
        .blob-1 {
          width: 500px;
          height: 500px;
          background: hsl(213 94% 68%); /* Accent color */
          top: -10%;
          left: -10%;
          animation: float-slow 20s infinite alternate;
        }

        .blob-2 {
          width: 600px;
          height: 600px;
          background: hsl(210 100% 85%);
          bottom: -15%;
          right: -10%;
          animation: float-slow 25s infinite alternate-reverse;
        }

        .blob-3 {
          width: 400px;
          height: 400px;
          background: hsl(220 100% 80%);
          top: 30%;
          left: 50%;
          transform: translate(-50%, -50%);
          animation: pulse-slow 15s infinite ease-in-out;
        }

        /* Glassmorphic Card */
        .glass-card {
          position: relative;
          background: rgba(255, 255, 255, 0.7);
          backdrop-filter: blur(24px);
          -webkit-backdrop-filter: blur(24px);
          border: 1px solid var(--color-border);
          box-shadow: 
            0 8px 32px rgba(0, 0, 0, 0.05),
            inset 0 1px 1px rgba(255, 255, 255, 0.4);
          border-radius: 24px;
          padding: 3rem 2.5rem;
          width: 100%;
          max-width: 440px;
          margin: 1.5rem;
          text-align: center;
        }

        .logo-badge {
          background: var(--color-secondary);
          border: 1px solid var(--color-border);
          padding: 1.25rem;
          border-radius: 20px;
          color: var(--color-primary);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        }

        .title-text {
          font-size: 2.25rem;
          font-weight: 800;
          letter-spacing: -0.025em;
          color: var(--color-foreground);
          margin-bottom: 0.75rem;
        }

        .subtitle-text {
          color: var(--color-muted-foreground);
          font-size: 0.95rem;
          line-height: 1.6;
          margin-bottom: 2rem;
        }

        .error-badge {
          width: 100%;
          background: hsl(0 100% 98%);
          border: 1px solid var(--color-destructive);
          color: var(--color-destructive);
          padding: 0.75rem 1rem;
          border-radius: 12px;
          font-size: 0.85rem;
        }

        /* Premium Sign In Button */
        .google-btn {
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--color-background);
          color: var(--color-foreground);
          font-weight: 600;
          font-size: 0.95rem;
          padding: 0.875rem 1.5rem;
          border-radius: 14px;
          border: 1px solid var(--color-border);
          transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        }

        .google-btn:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 
            0 12px 24px rgba(0, 0, 0, 0.1),
            0 0 0 4px var(--color-muted);
          background: var(--color-background);
        }

        .google-btn:active:not(:disabled) {
          transform: translateY(0);
        }

        .google-btn:disabled {
          opacity: 0.7;
          cursor: not-allowed;
        }

        /* Keyframes & Animations */
        @keyframes float-slow {
          0% { transform: translateY(0px) rotate(0deg); }
          100% { transform: translateY(40px) rotate(15deg); }
        }

        @keyframes pulse-slow {
          0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.3; }
          50% { transform: translate(-50%, -50%) scale(1.1); opacity: 0.5; }
        }

        .animate-pulse-subtle {
          animation: pulse-subtle 3s infinite ease-in-out;
        }

        @keyframes pulse-subtle {
          0%, 100% { transform: scale(1); opacity: 0.8; }
          50% { transform: scale(1.05); opacity: 1; }
        }

        .animate-fade-in {
          animation: fade-in 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        @keyframes fade-in {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }

        .animate-shake {
          animation: shake 0.4s ease-in-out;
        }

        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          25% { transform: translateX(-4px); }
          75% { transform: translateX(4px); }
        }

        /* Loading Spinner */
        .spinner {
          width: 20px;
          height: 20px;
          border: 2px solid rgba(0, 0, 0, 0.1);
          border-top-color: var(--color-primary);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
