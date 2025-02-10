import { authService } from "@/services/authService";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

const Home = () => {
  const navigate = useNavigate();
  const [isValidating, setIsValidating] = useState(true);
  const token = localStorage.getItem("token");

  useEffect(() => {
    const validateToken = async () => {
      if (!token) {
        navigate("/inbox-ai");
        return;
      }
      try {
        const response = await authService.validateToken();
        if (!response?.ok) {
          localStorage.removeItem("token");
          navigate("/inbox-ai");
        }
      } catch (error) {
        console.error("Token validation failed:", error);
        localStorage.removeItem("token");
        navigate("/inbox-ai");
      } finally {
        setIsValidating(false);
      }
    };
    validateToken();
  }, [token, navigate]);

  if (!token || isValidating) return null;

  return <div className="min-h-screen bg-background">Loggedin</div>;
};

export default Home;
