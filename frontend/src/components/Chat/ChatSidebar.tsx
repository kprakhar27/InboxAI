import { useState, useEffect } from "react";
import { PlusCircle, MessageSquare, Loader } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/components/ui/use-toast";
import { gmailService, ChatHistory } from "@/services/gmailService";
import { formatDistanceToNow } from "date-fns";

interface ChatSidebarProps {
  onChatSelect: (chatId: string) => void;
  onNewChat: () => void;
  currentChatId?: string;
}

export const ChatSidebar = ({
  onChatSelect,
  onNewChat,
  currentChatId,
}: ChatSidebarProps) => {
  const { toast } = useToast();
  const [chats, setChats] = useState<ChatHistory[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchChats = async () => {
    try {
      setIsLoading(true);
      const chatHistory = await gmailService.getChats();
      setChats(chatHistory);
    } catch (error) {
      console.error("Failed to fetch chat history:", error);
      toast({
        title: "Error",
        description: "Failed to load chat history. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchChats();
  }, []);

  return (
    <div className="w-64 border-r flex flex-col h-full bg-muted/20">
      <div className="p-4 border-b">
        <Button onClick={onNewChat} className="w-full" variant="outline">
          <PlusCircle className="h-4 w-4 mr-2" />
          New Chat
        </Button>
      </div>

      <ScrollArea className="flex-1">
        {isLoading ? (
          <div className="flex justify-center items-center h-20">
            <Loader className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : chats.length === 0 ? (
          <div className="p-4 text-sm text-muted-foreground text-center">
            No chat history found
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {chats.map((chat) => (
              <button
                key={chat.id}
                onClick={() => onChatSelect(chat.id)}
                className={`w-full text-left p-2 rounded-md transition-colors text-sm ${
                  currentChatId === chat.id
                    ? "bg-accent text-accent-foreground"
                    : "hover:bg-accent/50"
                }`}
              >
                <div className="flex items-center">
                  <MessageSquare className="h-4 w-4 mr-2 shrink-0" />
                  <div className="truncate flex-1">
                    {chat.name ||
                      `Chat ${formatDistanceToNow(new Date(chat.createdAt), {
                        addSuffix: true,
                      })}`}
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
};
