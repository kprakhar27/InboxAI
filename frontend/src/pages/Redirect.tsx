import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { gmailService } from "@/services/gmailService";
import { useToast } from "@/components/ui/use-toast";

const Redirect = () => {
  const [message, setMessage] = useState("Connecting your Gmail account...");
  const location = useLocation();
  const { toast } = useToast();

  useEffect(() => {
    const handleAuthRedirect = async () => {
      try {
        await gmailService.saveGoogleToken(
          window.location.href.replace("#/", "")
        );

        toast({
          title: "Success",
          description: "Gmail account connected successfully!",
        });
        setMessage("You can close the popup now.");
      } catch (error) {
        console.error("Error saving Google token:", error);
        toast({
          title: "Error",
          description: "Failed to connect Gmail account. Please try again.",
          variant: "destructive",
        });
        setMessage("Failed to connect Gmail account. You can close the popup.");
      } finally {
        if (window.opener && window.opener.gmailAuthPopup) {
          window.opener.gmailAuthPopup.close();
          delete window.opener.gmailAuthPopup;
          window.opener.location.reload();
        }
      }
    };

    handleAuthRedirect();
  }, [location, toast]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h2 className="text-2xl font-bold mb-4">{message} </h2>
        <p className="text-muted-foreground">
          Please wait while we complete the setup.
        </p>
      </div>
    </div>
  );
};

export default Redirect;
