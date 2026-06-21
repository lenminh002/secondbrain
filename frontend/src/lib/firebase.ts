import { initializeApp, type FirebaseApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, type Auth } from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export const hasFirebaseConfig = Object.values(firebaseConfig).every(Boolean);

let app: FirebaseApp | null = null;
let authInstance: Auth | null = null;

export function firebaseAuth() {
  if (!hasFirebaseConfig) {
    throw new Error("Firebase auth is not configured.");
  }
  if (!app) {
    app = initializeApp(firebaseConfig);
    authInstance = getAuth(app);
  }
  return authInstance as Auth;
}

export const googleProvider = new GoogleAuthProvider();
