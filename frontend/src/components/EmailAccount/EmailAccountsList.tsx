import { useState } from "react";
import { ConnectedEmail, gmailService } from "@/services/gmailService";
import { EmailAccountCard } from "./EmailAccountCard";
import { useToast } from "@/components/ui/use-toast";
import { Button } from "@/components/ui/button";
import { Mail, RefreshCcw, Loader } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { popupCenter } from "@/libs/utils";

interface EmailAccountsListProps {
  connectedEmails: ConnectedEmail[];
  onEmailsUpdate: (emails: ConnectedEmail[]) => void;
}

export const EmailAccountsList = ({
  connectedEmails,
  onEmailsUpdate,
}: EmailAccountsListProps) => {
  const { toast } = useToast();
  const [refreshingEmails, setRefreshingEmails] = useState<string[]>([]);
  const [refreshingAll, setRefreshingAll] = useState(false);

  const handleRefresh = async (email: string) => {
    setRefreshingEmails((prev) => [...prev, email]);

    try {
      const response = await gmailService.fetchAndRefreshEmail([email]);

      if (response && response.accounts) {
        onEmailsUpdate(response.accounts);
      }

      toast({
        title: "Email Refresh triggered",
        description: `${email} has been triggered successfully.`,
      });
    } catch (error) {
      console.error("Failed to refresh email:", error);
      toast({
        title: "Error",
        description: "Failed to refresh email. Please try again.",
        variant: "destructive",
      });
    } finally {
      setRefreshingEmails((prev) => prev.filter((e) => e !== email));
    }
  };

  const handleRefreshAll = async () => {
    if (connectedEmails.length === 0) {
      toast({
        title: "No emails to refresh",
        description: "Please connect an email account first.",
      });
      return;
    }

    setRefreshingAll(true);

    try {
      const emails = connectedEmails.map((account) => account.email);
      const response = await gmailService.fetchAndRefreshEmail(emails);

      if (response && response.accounts) {
        onEmailsUpdate(response.accounts);
      }

      toast({
        title: "All Emails Refreshed",
        description: "All connected emails have been refreshed successfully.",
      });
    } catch (error) {
      console.error("Failed to refresh all emails:", error);
      toast({
        title: "Error",
        description: "Failed to refresh emails. Please try again.",
        variant: "destructive",
      });
    } finally {
      setRefreshingAll(false);
    }
  };

  const handleRemove = async (email: string) => {
    try {
      await gmailService.removeEmail(email);

      // Remove the email from the list
      onEmailsUpdate(connectedEmails.filter((e) => e.email !== email));

      toast({
        title: "Email Removed",
        description: `${email} has been removed successfully.`,
      });
    } catch (error) {
      console.error("Failed to remove email:", error);
      toast({
        title: "Error",
        description: "Failed to remove email. Please try again.",
        variant: "destructive",
      });
    }
  };

  const handleConnectGmail = async () => {
    try {
      const { authorization_url } = await gmailService.getGmailAuthLink();
      const popup = popupCenter(
        authorization_url,
        "Gmail Authentication",
        400,
        600
      );
      if (popup) {
        (window as any).gmailAuthPopup = popup;
      } else {
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
  };

  return (
    <div className="w-full md:w-1/4 p-4 border-r overflow-y-auto flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold">Connected Emails</h2>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefreshAll}
          disabled={refreshingAll}
          className="ml-2"
        >
          {refreshingAll ? (
            <Loader className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <RefreshCcw className="h-4 w-4 mr-2" />
          )}
          <span>Refresh All</span>
        </Button>
      </div>

      <div className="space-y-4 flex-grow">
        {connectedEmails.map((account) => (
          <EmailAccountCard
            key={account.email}
            account={account}
            onRefresh={handleRefresh}
            onRemove={handleRemove}
            isRefreshing={refreshingEmails.includes(account.email)}
          />
        ))}
      </div>

      <Card className="mt-4">
        <CardContent className="p-4">
          <Button
            variant="default"
            className="w-full hover:bg-[#b5adff]"
            onClick={handleConnectGmail}
          >
            <Mail className="h-5 w-5 mr-2" />
            Connect another Gmail account
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};
