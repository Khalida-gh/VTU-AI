import {
  GraduationCap,
  Bell,
  Moon,
  Sun,
  Search,
  UserCircle2,
  Star,
} from "lucide-react";

import { useEffect, useState } from "react";
import "./Navbar.css";

interface NavbarProps {
  onFavouritesClick?: () => void;
}

export default function Navbar({ onFavouritesClick }: NavbarProps) {
  const [dark, setDark] = useState(
    localStorage.getItem("theme") === "dark"
  );

  useEffect(() => {
    if (dark) {
      document.body.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.body.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  }, [dark]);

  return (
    <header className="navbar">
      <div className="logo-section">
        <div className="logo-box">
          <GraduationCap size={22} />
        </div>

        <div>
          <h2>VTU AI</h2>
          <p>MODEL-ANSWER NOTEBOOK</p>
        </div>
      </div>

      <div className="search-box">
        <Search size={16} />
        <input type="text" placeholder="Search previous questions..." />
      </div>

      <div className="nav-icons">
        <button
          className="nav-button"
          onClick={onFavouritesClick}
          title="Favourites"
        >
          <Star size={19} />
        </button>

        <button className="nav-button" title="Notifications">
          <Bell size={19} />
        </button>

        <button
          className="nav-button"
          onClick={() => setDark(!dark)}
          title={dark ? "Light Mode" : "Dark Mode"}
        >
          {dark ? <Sun size={19} /> : <Moon size={19} />}
        </button>

        <div className="nav-avatar">
          <UserCircle2 size={22} />
        </div>
      </div>
    </header>
  );
}
