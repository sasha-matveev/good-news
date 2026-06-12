import { initializeApp } from "firebase/app";
import {
  GoogleAuthProvider,
  getAuth,
  onAuthStateChanged,
  signInWithPopup,
  signOut,
  type User
} from "firebase/auth";

// Public web-app identifiers for the good-news-am26 Firebase project.
const firebaseConfig = {
  apiKey: "AIzaSyAF3GCHf9IxZGK3VxWaYiNtifKjGdwRaKU",
  authDomain: "good-news-am26.firebaseapp.com",
  projectId: "good-news-am26",
  appId: "1:446870476468:web:f12c6fc9ab74ae1065e9e1"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);

export function watchUser(callback: (user: User | null) => void): () => void {
  return onAuthStateChanged(auth, callback);
}

export async function signInWithGoogle(): Promise<void> {
  await signInWithPopup(auth, new GoogleAuthProvider());
}

export async function signOutUser(): Promise<void> {
  await signOut(auth);
}

export async function currentIdToken(): Promise<string | null> {
  const user = auth.currentUser;
  if (!user) {
    return null;
  }
  return user.getIdToken();
}
