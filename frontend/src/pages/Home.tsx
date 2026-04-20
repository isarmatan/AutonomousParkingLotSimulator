import { Link } from "react-router-dom";
import bg from "../assets/HomePage.webp";
import "./Home.css";

export default function Home() {
  return (
    <div className="homeX" dir="rtl">
      {/* Background image */}
      <div
        className="homeX__bg"
        style={{ backgroundImage: `url(${bg})` }}
        aria-hidden="true"
      />

      {/* Dark overlay + blur layer */}
      <div className="homeX__overlay" aria-hidden="true" />

      <main className="homeX__content">
        <h1 className="homeX__title">Autonomous Parking Simulator</h1>

      <div className="homeX__menu" role="navigation" aria-label="Main menu">
        <Link className="menuBtn menuBtn--primary" to="/config">
          <span className="menuBtn__icon" aria-hidden="true">▶</span>
          <span className="menuBtn__label">Start Simulation</span>
        </Link>

        <Link className="menuBtn menuBtn--primary" to="/editor">
          <span className="menuBtn__icon" aria-hidden="true">▦</span>
          <span className="menuBtn__label">Parking Lot Editor</span>
        </Link>

        <Link className="menuBtn menuBtn--secondary" to="/stats">
          <span className="menuBtn__icon" aria-hidden="true">↗</span>
          <span className="menuBtn__label">Statistics Dashboard</span>
        </Link>
      </div>

      <div className="homeX__aboutWrap">
        <Link to="/about" className="homeX__about">
          About the Project
        </Link>
      </div>


        <div className="homeX__underline" aria-hidden="true" />
      </main>
    </div>
  );
}
