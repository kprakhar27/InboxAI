import { useState } from "react";
import { ConnectedEmail } from "@/services/gmailService";
import { EmailAccountsList } from "@/components/EmailAccount/EmailAccountsList";
import { ChatInterface } from "@/components/Chat/ChatInterface";
import { ChatSidebar } from "../Chat/ChatSidebar";

interface ConnectedStateProps {
  connectedEmails: ConnectedEmail[];
}

export const ConnectedState = ({
  connectedEmails: initialEmails,
}: ConnectedStateProps) => {
  const [connectedEmails, setConnectedEmails] =
    useState<ConnectedEmail[]>(initialEmails);
  const [currentChatId, setCurrentChatId] = useState<string | undefined>(
    undefined
  );

  const handleChatSelect = (chatId: string) => {
    setCurrentChatId(chatId);
  };

  const handleNewChat = () => {
    setCurrentChatId(undefined);
  };

  const handleChatCreated = (newChatId: string) => {
    setCurrentChatId(newChatId);
  };

  return (
    <div className="flex flex-col md:flex-row h-[calc(100vh-4rem)]">
      {/* Left panel - Email accounts */}
      <EmailAccountsList
        connectedEmails={connectedEmails}
        onEmailsUpdate={setConnectedEmails}
      />

      {/* Middle panel - Chat sidebar */}
      <ChatSidebar
        onChatSelect={handleChatSelect}
        onNewChat={handleNewChat}
        currentChatId={currentChatId}
      />

      {/* Right panel - Chat */}
      <ChatInterface chatId={currentChatId} onChatCreated={handleChatCreated} />
    </div>
  );
};
