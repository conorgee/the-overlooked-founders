import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

export function LoginPage() {
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [confirmMessage, setConfirmMessage] = useState("");

  const { signIn, signUp } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setConfirmMessage("");
    setSubmitting(true);

    if (isSignUp) {
      const { error } = await signUp(email, password, fullName);
      if (error) {
        setError(error.message);
      } else {
        setConfirmMessage("Check your email for a confirmation link, then sign in.");
        setIsSignUp(false);
      }
    } else {
      const { error } = await signIn(email, password);
      if (error) {
        setError(error.message);
      } else {
        navigate("/dashboard");
      }
    }

    setSubmitting(false);
  }

  return (
    <div className="min-h-screen bg-black flex items-center justify-center px-6 pt-20">
      <div className="w-full max-w-md">
        <h1 className="text-3xl sm:text-4xl font-light tracking-tight text-white mb-2">
          {isSignUp ? "Create Account" : "Sign In"}
        </h1>
        <p className="text-text-muted text-sm mb-10">
          {isSignUp
            ? "Join The Overlooked Founders programme"
            : "Welcome back to your dashboard"}
        </p>

        {error && (
          <div className="mb-6 text-sm text-red-400 bg-red-400/10 border border-red-400/20 px-4 py-3">
            {error}
          </div>
        )}

        {confirmMessage && (
          <div className="mb-6 text-sm text-accent bg-accent/10 border border-accent/20 px-4 py-3">
            {confirmMessage}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {isSignUp && (
            <div>
              <label className="block text-[10px] uppercase tracking-[0.2em] text-text-muted mb-2">
                Full Name
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                className="w-full bg-transparent border-b border-white/20 text-white text-sm py-3 focus:border-accent focus:outline-none transition-colors"
              />
            </div>
          )}

          <div>
            <label className="block text-[10px] uppercase tracking-[0.2em] text-text-muted mb-2">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full bg-transparent border-b border-white/20 text-white text-sm py-3 focus:border-accent focus:outline-none transition-colors"
            />
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-[0.2em] text-text-muted mb-2">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              className="w-full bg-transparent border-b border-white/20 text-white text-sm py-3 focus:border-accent focus:outline-none transition-colors"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-accent text-black text-xs uppercase tracking-[0.15em] font-medium py-3.5 hover:bg-accent-hover transition-all duration-300 disabled:opacity-50"
          >
            {submitting ? "..." : isSignUp ? "Create Account" : "Sign In"}
          </button>
        </form>

        <p className="mt-8 text-center text-sm text-text-muted">
          {isSignUp ? "Already have an account?" : "Don't have an account?"}{" "}
          <button
            onClick={() => {
              setIsSignUp(!isSignUp);
              setError("");
              setConfirmMessage("");
            }}
            className="text-accent hover:underline"
          >
            {isSignUp ? "Sign in" : "Create one"}
          </button>
        </p>
      </div>
    </div>
  );
}
