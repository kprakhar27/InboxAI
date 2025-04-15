import { ConnectedState } from "@/components/HomeStates/ConnectedState";
import { UnconnectedState } from "@/components/HomeStates/UnconnectedState";
import { TopNav } from "@/components/TopNav";
import { useToast } from "@/components/ui/use-toast";
import { authService } from "@/services/authService";
import { ConnectedEmail, gmailService } from "@/services/gmailService";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

const Home = () => {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [isValidating, setIsValidating] = useState(true);
  const [hasConnectedEmails, setHasConnectedEmails] = useState(false);
  const [connectedEmails, setConnectedEmails] = useState<ConnectedEmail[]>([]);
  const token = localStorage.getItem("token");

  const fetchConnectedAccounts = async () => {
    try {
      const emailsData = await gmailService.getConnectedAccounts();
      setConnectedEmails(emailsData.accounts);
      setHasConnectedEmails(emailsData.accounts.length > 0);
      return emailsData;
    } catch (error) {
      console.error("Error fetching connected accounts:", error);
      toast({
        title: "Error",
        description:
          "Failed to load your connected accounts. Please try again.",
        variant: "destructive",
      });
      return null;
    }
  };

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
          return;
        }
        await fetchConnectedAccounts();
      } catch (error) {
        console.error("Error occurred:", error);
        toast({
          title: "Error",
          description:
            "Failed to load your account data. Please try loging in again.",
          variant: "destructive",
        });
        localStorage.removeItem("token");
        navigate("/inbox-ai");
      } finally {
        setIsValidating(false);
      }
    };
    validateToken();
  }, [token, navigate, toast]);

  if (!token || isValidating) return null;

  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      {hasConnectedEmails ? (
        <ConnectedState connectedEmails={connectedEmails} />
      ) : (
        <UnconnectedState />
      )}
    </div>
  );
};

export default Home;
