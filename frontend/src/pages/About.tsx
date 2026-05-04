import AppLayout from "../layouts/AppLayout";
import { Target, Code2, GraduationCap, Users, BrainCircuit, Car, Layers } from "lucide-react";
import "./About.css";

export default function About() {
  return (
    <AppLayout variant="workspace">
      <div className="aboutPage">
        
        {/* Hero Section */}
        <div className="aboutHero">
          <div className="heroBadge">Final Project 2026</div>
          <h1 className="aboutTitle">Autonomous Parking Simulator</h1>
          <p className="aboutIntro">
            An advanced simulation platform designed to analyze and optimize 
            autonomous vehicle behaviors within complex parking environments.
          </p>
        </div>

        {/* Main Grid */}
        <div className="aboutGrid">
          
          {/* Goals Card */}
          <section className="aboutCard goalsCard">
            <div className="cardHeader">
              <Target className="cardIcon" size={24} />
              <h2>Project Goals</h2>
            </div>
            <div className="cardContent">
              <ul className="featureList">
                <li>
                  <Car size={16} />
                  <span>Simulate realistic autonomous parking scenarios</span>
                </li>
                <li>
                  <BrainCircuit size={16} />
                  <span>Evaluate routing & optimization algorithms</span>
                </li>
                <li>
                  <Layers size={16} />
                  <span>Analyze efficiency, congestion, and space utilization</span>
                </li>
              </ul>
            </div>
          </section>

          {/* Tech Stack Card */}
          <section className="aboutCard techCard">
            <div className="cardHeader">
              <Code2 className="cardIcon" size={24} />
              <h2>Tech Stack</h2>
            </div>
            <div className="techGrid">
              <div className="techItem">
                <span className="techLabel">Frontend</span>
                <span className="techValue">React, TS, Three.js</span>
              </div>
              <div className="techItem">
                <span className="techLabel">Simulation</span>
                <span className="techValue">Python (Time-Expanded A*)</span>
              </div>
              <div className="techItem">
                <span className="techLabel">Backend</span>
                <span className="techValue">FastAPI + SQLAlchemy</span>
              </div>
              <div className="techItem">
                <span className="techLabel">UI/UX</span>
                <span className="techValue">Modern Glassmorphism</span>
              </div>
            </div>
          </section>

          {/* Academic Context */}
          <section className="aboutCard academicCard">
            <div className="cardHeader">
              <GraduationCap className="cardIcon" size={24} />
              <h2>Academic Context</h2>
            </div>
            <div className="cardContent">
              <p>
                Developed as a comprehensive final-year project for the 
                <strong> Department of Information Systems Engineering</strong> at 
                <strong> Ben-Gurion University of the Negev</strong>.
              </p>
              <div className="uniTag">BGU 2026</div>
            </div>
          </section>

          {/* Team Card */}
          <section className="aboutCard teamCard">
            <div className="cardHeader">
              <Users className="cardIcon" size={24} />
              <h2>The Team</h2>
            </div>
            <div className="teamGrid">
              <div className="teamMember">
                <div className="avatar">M</div>
                <div className="memberInfo">
                  <span className="name">Matan Isar</span>
                  <span className="role">Developer</span>
                </div>
              </div>
              <div className="teamMember">
                <div className="avatar">O</div>
                <div className="memberInfo">
                  <span className="name">Omer Topzi</span>
                  <span className="role">Developer</span>
                </div>
              </div>
              <div className="teamMember">
                <div className="avatar">N</div>
                <div className="memberInfo">
                  <span className="name">Noa Ioshpe</span>
                  <span className="role">Developer</span>
                </div>
              </div>
              <div className="teamMember">
                <div className="avatar">N</div>
                <div className="memberInfo">
                  <span className="name">Noa Revivo</span>
                  <span className="role">Developer</span>
                </div>
              </div>
              <div className="teamMember">
                <div className="avatar adviser">R</div>
                <div className="memberInfo">
                  <span className="name">Roni Stern</span>
                  <span className="role">Adviser</span>
                </div>
              </div>
              <div className="teamMember">
                <div className="avatar adviser">N</div>
                <div className="memberInfo">
                  <span className="name">Noam Barda</span>
                  <span className="role">Adviser</span>
                </div>
              </div>
            </div>
          </section>

        </div>
      </div>
    </AppLayout>
  );
}