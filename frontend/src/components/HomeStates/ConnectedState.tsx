import { useState } from "react";
import { ConnectedEmail } from "@/services/gmailService";
import { EmailAccountsList } from "@/components/EmailAccount/EmailAccountsList";
import { ChatInterface } from "@/components/Chat/ChatInterface";

interface ConnectedStateProps {
  connectedEmails: ConnectedEmail[];
}

export const ConnectedState = ({
  connectedEmails: initialEmails,
}: ConnectedStateProps) => {
  const [connectedEmails, setConnectedEmails] =
    useState<ConnectedEmail[]>(initialEmails);

  return (
    <div className="flex flex-col md:flex-row h-[calc(100vh-4rem)]">
      {/* Left panel - Email accounts */}
      <EmailAccountsList
        connectedEmails={connectedEmails}
        onEmailsUpdate={setConnectedEmails}
      />

      {/* Right panel - Chat */}
      <ChatInterface />
    </div>
  );
};
