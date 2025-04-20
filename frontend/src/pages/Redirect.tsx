import { useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { gmailService } from "@/services/gmailService";
import { useToast } from "@/components/ui/use-toast";

const Redirect = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();

  useEffect(() => {
    const handleAuthRedirect = async () => {
      try {
        await gmailService.saveGoogleToken(
          window.location.href.replace("#/", "")
        );
        if (window.opener && window.opener.gmailAuthPopup) {
          window.opener.gmailAuthPopup.close();
          delete window.opener.gmailAuthPopup;

          // Trigger a soft refresh on the parent page
          window.opener.location.reload();
        }
        toast({
          title: "Success",
          description: "Gmail account connected successfully!",
        });
        navigate("/");
      } catch (error) {
        console.error("Error saving Google token:", error);
        toast({
          title: "Error",
          description: "Failed to connect Gmail account. Please try again.",
          variant: "destructive",
        });
        navigate("/");
      }
    };

    handleAuthRedirect();
  }, [navigate, location, toast]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h2 className="text-2xl font-bold mb-4">
          Connecting your Gmail account...
        </h2>
        <p className="text-muted-foreground">
          Please wait while we complete the setup.
        </p>
      </div>
    </div>
  );
};

export default Redirect;
