import { Button } from "@/components/ui/button";
import { useState, useEffect } from "react";
import { Link } from "react-router-dom";

export const Navbar = () => {
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 10);
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        isScrolled ? "glass py-4" : "bg-transparent py-6"
      }`}
    >
      <div className="container mx-auto flex items-center justify-between">
        <Link to="/" className="flex items-center space-x-2">
          <span className="text-2xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
            InboxAI
          </span>
        </Link>
        <div className="flex items-center space-x-4">
          <Link to="/login">
            <Button variant="ghost" className="text-foreground">
              Login
            </Button>
          </Link>
          <Link to="/login" state={{ register: true }}>
            <Button className="bg-primary hover:bg-primary/90">
              Get Started
            </Button>
          </Link>
        </div>
      </div>
    </nav>
  );
};
