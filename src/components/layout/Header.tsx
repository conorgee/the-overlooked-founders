import { Link, useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import logo from "../../assets/logo-white.png";
import { useAuth } from "../../lib/auth";

const navLinks = [
  { to: "/", label: "Home" },
  { to: "/ask", label: "Ask a Mentor" },
  { to: "/apply", label: "Apply" },
  { to: "/dashboard", label: "Dashboard" },
];

export function Header() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, profile, signOut } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  async function handleSignOut() {
    await signOut();
    navigate("/");
  }

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-black/60 backdrop-blur-sm">
      <div className="max-w-7xl mx-auto px-6 lg:px-12 h-20 flex items-center justify-between">
        <Link to="/" className="flex items-center">
          <img src={logo} alt="The Overlooked Founders" className="w-48 sm:w-56 h-auto" />
        </Link>

        <nav className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className={`text-xs uppercase tracking-[0.15em] transition-colors duration-300 ${
                location.pathname === link.to
                  ? "text-white"
                  : "text-text-muted hover:text-white"
              }`}
            >
              {link.label}
            </Link>
          ))}
          {profile?.role === "admin" && (
            <Link
              to="/admin"
              className={`text-xs uppercase tracking-[0.15em] transition-colors duration-300 ${
                location.pathname === "/admin"
                  ? "text-accent"
                  : "text-accent/60 hover:text-accent"
              }`}
            >
              Admin
            </Link>
          )}
        </nav>

        <div className="hidden md:flex items-center gap-4">
          {user ? (
            <>
              <span className="text-xs text-text-muted tracking-wide">
                {profile?.full_name || user.email}
              </span>
              <button
                onClick={handleSignOut}
                className="text-xs uppercase tracking-[0.15em] text-text-muted hover:text-white transition-colors duration-300"
              >
                Sign Out
              </button>
            </>
          ) : (
            <>
              <Link
                to="/login"
                className="text-xs uppercase tracking-[0.15em] text-text-muted hover:text-white transition-colors duration-300"
              >
                Sign In
              </Link>
              <Link
                to="/apply"
                className="text-xs uppercase tracking-[0.15em] text-black bg-accent px-5 py-2.5 font-medium hover:bg-accent-hover transition-all duration-300"
              >
                Apply Now
              </Link>
            </>
          )}
        </div>

        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="md:hidden text-white"
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {mobileOpen && (
        <div className="md:hidden bg-black border-t border-white/10 px-6 py-8">
          <nav className="flex flex-col gap-6">
            {navLinks.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                onClick={() => setMobileOpen(false)}
                className={`text-sm uppercase tracking-[0.15em] ${
                  location.pathname === link.to ? "text-white" : "text-text-muted"
                }`}
              >
                {link.label}
              </Link>
            ))}
            {profile?.role === "admin" && (
              <Link
                to="/admin"
                onClick={() => setMobileOpen(false)}
                className={`text-sm uppercase tracking-[0.15em] ${
                  location.pathname === "/admin" ? "text-accent" : "text-accent/60"
                }`}
              >
                Admin
              </Link>
            )}
            {user ? (
              <button
                onClick={() => { setMobileOpen(false); handleSignOut(); }}
                className="text-sm uppercase tracking-[0.15em] text-text-muted text-left"
              >
                Sign Out
              </button>
            ) : (
              <>
                <Link
                  to="/login"
                  onClick={() => setMobileOpen(false)}
                  className="text-sm uppercase tracking-[0.15em] text-text-muted"
                >
                  Sign In
                </Link>
                <Link
                  to="/apply"
                  onClick={() => setMobileOpen(false)}
                  className="text-xs uppercase tracking-[0.15em] text-black bg-accent px-5 py-3 font-medium text-center mt-2"
                >
                  Apply Now
                </Link>
              </>
            )}
          </nav>
        </div>
      )}
    </header>
  );
}
