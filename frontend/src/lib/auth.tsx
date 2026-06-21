import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";
import { onAuthStateChanged, signInWithPopup, signOut, type User } from "firebase/auth";

import { firebaseAuth, googleProvider, hasFirebaseConfig } from "@/lib/firebase";

type AuthContextValue = {
  authError: string;
  getIdToken: () => Promise<string>;
  isConfigured: boolean;
  isLoading: boolean;
  signInWithGoogle: () => Promise<void>;
  signOutUser: () => Promise<void>;
  user: User | null;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(hasFirebaseConfig);
  const [authError, setAuthError] = useState("");

  useEffect(() => {
    if (!hasFirebaseConfig) {
      setIsLoading(false);
      return;
    }
    const unsubscribe = onAuthStateChanged(
      firebaseAuth(),
      (nextUser) => {
        setUser(nextUser);
        setAuthError("");
        setIsLoading(false);
      },
      (error) => {
        setAuthError(error.message);
        setIsLoading(false);
      },
    );
    return unsubscribe;
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      authError,
      getIdToken: async () => {
        if (!user) throw new Error("You need to sign in first.");
        return user.getIdToken();
      },
      isConfigured: hasFirebaseConfig,
      isLoading,
      signInWithGoogle: async () => {
        setAuthError("");
        try {
          await signInWithPopup(firebaseAuth(), googleProvider);
        } catch (error) {
          setAuthError(error instanceof Error ? error.message : "Google sign-in failed.");
        }
      },
      signOutUser: async () => {
        setAuthError("");
        await signOut(firebaseAuth());
      },
      user,
    }),
    [authError, isLoading, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return context;
}
