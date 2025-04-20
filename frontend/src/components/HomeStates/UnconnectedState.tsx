import { Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { gmailService } from "@/services/gmailService";
import { useToast } from "../ui/use-toast";
import { popupCenter } from "@/libs/utils";

const emailProviders = [
  {
    name: "Gmail",
    description: "Connect your Google Mail account",
    icon: Mail,
    disabled: false,
  },
  // {
  //   name: "Outlook",
  //   description: "Connect your Microsoft Outlook account",
  //   icon: Mail,
  //   disabled: true,
  // },
];

export const UnconnectedState = () => {
  const { toast } = useToast();

  const handleConnect = async (provider: string) => {
    if (provider === "Gmail") {
      try {
        const { authorization_url } = await gmailService.getGmailAuthLink();
        const popup = popupCenter(
          authorization_url,
          "Gmail Authentication",
          400,
          600
        );

        // Check if popup was blocked
        if (!popup) {
          toast({
            title: "Error",
            description: "Please allow popups to connect your Gmail account.",
            variant: "destructive",
          });
        }
      } catch (error) {
        console.error("Error getting Gmail auth link:", error);
        toast({
          title: "Error",
          description: "Failed to initiate Gmail connection. Please try again.",
          variant: "destructive",
        });
      }
    } else {
      // Handle other providers
      console.log(`Connecting to ${provider}`);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold mb-4">Welcome to InboxAI</h1>
        <p className="text-xl text-muted-foreground mb-8">
          Connect your email accounts to get started with RAG-powered email
          management
        </p>
      </div>

      <div className="grid md:grid-cols-1 gap-6 max-w-2xl mx-auto">
        {emailProviders.map((provider) => (
          <Card
            key={provider.name}
            className="hover:shadow-lg transition-shadow"
          >
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <provider.icon className="h-6 w-6" />
                {provider.name}
              </CardTitle>
              <CardDescription>{provider.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                className="w-full"
                onClick={() => handleConnect(provider.name)}
                disabled={provider.disabled}
              >
                Connect {provider.name}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
};
