
import { useState } from "react";
import { Send, Loader } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { gmailService } from "@/services/gmailService";
import { ChatMessage, ChatMessageType } from "./ChatMessage";
import { useToast } from "@/components/ui/use-toast";

export const ChatInterface = () => {
  const { toast } = useToast();
  const [message, setMessage] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessageType[]>([
    { id: '1', content: "How can I help with your emails today?", sender: 'assistant' }
  ]);
  const [isWaitingForResponse, setIsWaitingForResponse] = useState(false);

  const generateId = () => Math.random().toString(36).substring(2, 11);

  const handleSend = async () => {
    if (!message.trim()) return;
    
    const userMessageId = generateId();
    const assistantMessageId = generateId();
    
    // Add user message to chat
    setChatMessages(prev => [
      ...prev, 
      { id: userMessageId, content: message, sender: 'user' }
    ]);
    
    // Add placeholder for assistant's message
    setChatMessages(prev => [
      ...prev, 
      { id: assistantMessageId, content: "", sender: 'assistant', isLoading: true }
    ]);
    
    setIsWaitingForResponse(true);
    setMessage("");

    try {
      // Call the inference API
      const response = await gmailService.getInference(message);
      
      // Update assistant's message with the response
      setChatMessages(prev => 
        prev.map(msg => 
          msg.id === assistantMessageId 
            ? { ...msg, content: response.answer, isLoading: false, responseId: response.id } 
            : msg
        )
      );
    } catch (error) {
      console.error("Failed to get inference:", error);
      
      // Show error message in chat
      setChatMessages(prev => 
        prev.map(msg => 
          msg.id === assistantMessageId 
            ? { ...msg, content: "Sorry, I couldn't process your request.", isLoading: false } 
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

  const handleFeedback = (messageId: string, feedback: 'yes' | 'no') => {
    // Update the message to show feedback was given
    setChatMessages(prev => 
      prev.map(msg => 
        msg.id === messageId 
          ? { ...msg, feedbackGiven: feedback } 
          : msg
      )
    );
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
      
      <div className="border-t p-4">
        <div className="flex gap-2 max-w-3xl mx-auto">
          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Type your query about your emails..."
            className="flex-1"
            onKeyDown={(e) => e.key === "Enter" && !isWaitingForResponse && handleSend()}
            disabled={isWaitingForResponse}
          />
          <Button 
            onClick={handleSend}
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
  );
};
