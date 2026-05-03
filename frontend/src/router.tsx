import { BrowserRouter, Routes, Route } from "react-router-dom";
import Home from "./pages/Home";
import SimulationConfig from "./pages/SimulationConfig";
import Editor from "./pages/Editor";
import Simulation from "./pages/Simulation";
import Stats from "./pages/Stats";
import About from "./pages/About";
import SavedLayouts from "./pages/SavedLayouts";
import CreateParkingLot from "./pages/CreateParkingLot";
import Layout from "./pages/Layout";

export default function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/config" element={<SimulationConfig />} />
        <Route path="/editor" element={<Editor />} />
        <Route path="/simulation" element={<Simulation />} />
        <Route path="/stats" element={<Stats />} />
        <Route path="/about" element={<About />} />
        <Route path="/layouts" element={<SavedLayouts />} />
        <Route path="/layout" element={<Layout />} />
        <Route path="/layout/new" element={<CreateParkingLot />} />

      </Routes>
    </BrowserRouter>
  );
}
