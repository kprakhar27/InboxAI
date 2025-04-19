import { useEffect, useState } from "react";
import { Send, Loader } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { gmailService, RagSource } from "@/services/gmailService";
import { ChatMessage, ChatMessageType } from "./ChatMessage";
import { useToast } from "@/components/ui/use-toast";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card } from "../ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../ui/dialog";
import { Label } from "@/components/ui/label";

interface ChatInterfaceProps {
  chatId?: string;
  onChatCreated?: (newChatId: string) => void;
  onNewChat?: () => void;
}
const INITIAL_MESSAGE = {
  id: "1",
  content: "How can I help with your emails today?",
  sender: "assistant" as const,
};

export const ChatInterface = ({
  chatId,
  onChatCreated,
  onNewChat,
}: ChatInterfaceProps) => {
  const { toast } = useToast();
  const [message, setMessage] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessageType[]>([
    INITIAL_MESSAGE,
  ]);
  const [isWaitingForResponse, setIsWaitingForResponse] = useState(false);

  const [ragSources, setRagSources] = useState<RagSource[]>([]);
  const [selectedRagSource, setSelectedRagSource] = useState<string>("");
  const [isLoadingRagSources, setIsLoadingRagSources] = useState(false);
  const [showNewChatDialog, setShowNewChatDialog] = useState(false);
  const [newChatName, setNewChatName] = useState("");
  const [pendingUserMessage, setPendingUserMessage] = useState("");
  const generateId = () => Math.random().toString(36).substring(2, 11);

  // Fetch RAG sources when component mounts
  useEffect(() => {
    const fetchRagSources = async () => {
      try {
        setIsLoadingRagSources(true);
        const sources = await gmailService.getRagSources();
        setRagSources(sources);
        if (sources.length > 0) {
          setSelectedRagSource(sources[0].rag_id);
        }
      } catch (error) {
        console.error("Failed to fetch RAG sources:", error);
        toast({
          title: "Error",
          description: "Failed to load RAG sources.",
          variant: "destructive",
        });
      } finally {
        setIsLoadingRagSources(false);
      }
    };

    fetchRagSources();
  }, [toast]);

  // Load chat messages if chatId is provided
  useEffect(() => {
    const loadChatMessages = async () => {
      if (!chatId) {
        // If there's no chatId, we should show the initial message
        setChatMessages([INITIAL_MESSAGE]);
        return;
      }

      try {
        setIsWaitingForResponse(true);
        const messages = await gmailService.getMessages(chatId);

        // Find the most recent assistant message with a ragId
        const assistantMessages = messages.filter(
          (msg) => msg.sender === "assistant" && msg.ragId
        );

        if (assistantMessages.length > 0) {
          // Sort by timestamp to get the most recent message
          const sortedMessages = [...assistantMessages].sort(
            (a, b) =>
              new Date(b.timestamp || "").getTime() -
              new Date(a.timestamp || "").getTime()
          );

          const mostRecentMessage = sortedMessages[0];
          if (mostRecentMessage.ragId) {
            setSelectedRagSource(mostRecentMessage.ragId);
          }
        }

        // Only replace messages if we got a valid response
        if (messages.length > 0) {
          setChatMessages(messages);
        } else {
          // If no messages are found for this chat, show the initial message
          setChatMessages([INITIAL_MESSAGE]);
        }
      } catch (error) {
        console.error("Failed to load chat messages:", error);
        toast({
          title: "Error",
          description:
            "Failed to load chat messages. Start a new conversation.",
          variant: "destructive",
        });
        setChatMessages([INITIAL_MESSAGE]);
      } finally {
        setIsWaitingForResponse(false);
      }
    };

    loadChatMessages();
  }, [chatId, toast]);

  useEffect(() => {
    if (onNewChat) {
      // Add a listener for the onNewChat prop
      const handleExternalNewChat = () => {
        handleNewChat();
      };

      // Clean up the listener
      return () => {
        // No cleanup needed for this simple implementation
      };
    }
  }, [onNewChat]);

  const initiateMessage = () => {
    if (!message.trim()) return;
    if (!chatId) {
      // For new chats, show the dialog to get a chat name
      setPendingUserMessage(message);
      setNewChatName(message.substring(0, 30) + "...");
      setShowNewChatDialog(true);
      setMessage("");
    } else {
      // For existing chats, send the message directly
      handleSendToExistingChat(message, chatId);
    }
  };

  const handleSendToExistingChat = async (
    messageText: string,
    chat_id: string
  ) => {
    const userMessageId = generateId();

    // Add user message to chat
    setChatMessages((prev) => [
      ...prev,
      {
        id: userMessageId,
        content: messageText,
        sender: "user",
        timestamp: new Date().toISOString(),
      },
    ]);

    // Add placeholder for assistant's message
    const tempAssistantId = generateId();
    setChatMessages((prev) => [
      ...prev,
      {
        id: tempAssistantId,
        content: "",
        sender: "assistant",
        isLoading: true,
      },
    ]);

    setIsWaitingForResponse(true);
    setMessage("");

    try {
      const response = await gmailService.getInference(
        messageText,
        selectedRagSource || undefined,
        chat_id
      );

      // Update the chat messages - remove the temporary loading message
      setChatMessages((prev) =>
        prev.filter((msg) => msg.id !== tempAssistantId)
      );

      // Add the user message with query hash
      setChatMessages((prev) => [
        ...prev.filter((msg) => msg.id !== userMessageId),
        {
          id: `${response.message_id}-user`,
          content: messageText,
          sender: "user",
          timestamp: new Date().toISOString(),
          queryHash: response.query,
        },
      ]);

      // Add the assistant response
      setChatMessages((prev) => [
        ...prev,
        {
          id: response.message_id,
          content: response.response,
          sender: "assistant",
          responseId: response.message_id,
          timestamp: new Date().toISOString(),
          responseTimeMs: response.response_time_ms,
          queryHash: response.query,
          responseHash: response.response,
          ragId: response.rag_id,
        },
      ]);
    } catch (error) {
      console.error("Failed to get inference:", error);

      // Show error message in chat
      setChatMessages((prev) =>
        prev.map((msg) =>
          msg.id === tempAssistantId
            ? {
                ...msg,
                content: "Sorry, I couldn't process your request.",
                isLoading: false,
              }
            : msg
        )
      );

      toast({
        title: "Error",
        description: "Failed to get a response. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsWaitingForResponse(false);
    }
  };

  const handleFeedback = (messageId: string, feedback: "yes" | "no") => {
    // Update the message to show feedback was given
    setChatMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId ? { ...msg, feedbackGiven: feedback } : msg
      )
    );
  };
  const handleNewChat = () => {
    setChatMessages([INITIAL_MESSAGE]);
    if (onNewChat) {
      onNewChat();
    }
  };

  const createNewChat = async () => {
    setIsWaitingForResponse(true);
    try {
      // First create the chat with the user-provided name
      const chatName = newChatName.trim()
        ? newChatName
        : pendingUserMessage.substring(0, 30) + "...";
      const newChat = await gmailService.createChat(chatName);
      const activeChatId = newChat.chat_id;
      if (onNewChat) {
        onNewChat();
      }
      // Once we have the chat ID, update the parent component
      if (onChatCreated) {
        onChatCreated(activeChatId);
      }
      setShowNewChatDialog(false);

      // Now send the message to the newly created chat
      await handleSendToExistingChat(pendingUserMessage, activeChatId);
    } catch (error) {
      console.error("Failed to create new chat:", error);
      toast({
        title: "Error",
        description: "Failed to create a new chat. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsWaitingForResponse(false);
      setPendingUserMessage("");
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-4 max-w-3xl mx-auto">
          {chatMessages.map((chatMessage) => (
            <ChatMessage
              key={chatMessage.id}
              message={chatMessage}
              onFeedbackGiven={handleFeedback}
            />
          ))}
        </div>
      </div>

      <Card className="mx-4 mb-4">
        <div className="p-4">
          <div className="flex flex-col gap-2">
            <div className="flex gap-2">
              <Input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Type your query about your emails..."
                className="flex-1"
                onKeyDown={(e) =>
                  e.key === "Enter" &&
                  !isWaitingForResponse &&
                  initiateMessage()
                }
                disabled={isWaitingForResponse}
              />

              {ragSources.length > 0 && (
                <Select
                  value={selectedRagSource}
                  onValueChange={setSelectedRagSource}
                  disabled={isLoadingRagSources || isWaitingForResponse}
                >
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Select source" />
                  </SelectTrigger>
                  <SelectContent>
                    {ragSources.map((source) => (
                      <SelectItem key={source.rag_id} value={source.rag_id}>
                        {source.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}

              <Button
                onClick={initiateMessage}
                className="hover:bg-[#b5adff]"
                disabled={isWaitingForResponse || !message.trim()}
              >
                {isWaitingForResponse ? (
                  <Loader className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
        </div>
      </Card>
      <Dialog open={showNewChatDialog} onOpenChange={setShowNewChatDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Name your new chat</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="name" className="text-right">
                Name
              </Label>
              <Input
                id="name"
                value={newChatName}
                onChange={(e) => setNewChatName(e.target.value)}
                className="col-span-3"
                placeholder="Enter a name for this chat"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowNewChatDialog(false)}
              disabled={isWaitingForResponse}
            >
              Cancel
            </Button>
            <Button onClick={createNewChat} disabled={isWaitingForResponse}>
              {isWaitingForResponse ? (
                <Loader className="h-4 w-4 animate-spin mr-2" />
              ) : null}
              Create Chat
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
