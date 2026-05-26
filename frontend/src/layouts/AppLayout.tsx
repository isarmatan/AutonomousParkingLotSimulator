import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import "./AppLayout.css";
import logo from "../assets/logo.png";


type Props = {
  children: ReactNode;
  variant?: "cinematic" | "workspace" | "dashboard" | "editor";
  /** Optional blurred background image for cinematic variant */
  bgImage?: string;
};

export default function AppLayout({ children, variant = "workspace", bgImage }: Props) {
  const isCinematicBg = variant === "cinematic" && !!bgImage;

  return (
    <div className={`appLayout appLayout--${variant}`}>
      {/* Cinematic background layers (behind everything) */}
      {isCinematicBg && (
        <>
          <div
            className="appLayout__cinematicBg"
            style={{ backgroundImage: `url(${bgImage})` }}
            aria-hidden="true"
          />
          <div className="appLayout__cinematicOverlay" aria-hidden="true" />
        </>
      )}

      <header className="appLayout__header">
        <div className="appLayout__headerInner">
          <Link to="/" className="appLayout__home" aria-label="Go to Home">
            ← <span>Home</span>
          </Link>

          <span className="appLayout__divider" aria-hidden="true" />

          <span className="appLayout__title">
            Autonomous Parking Simulator
          </span>

          <img
            src={logo}
            alt="Autonomous Parking Simulator logo"
            className="appLayout__logo appLayout__logo--right"
          />


        </div>
      </header>

      <main className="appLayout__content">{children}</main>
    </div>
  );
}
