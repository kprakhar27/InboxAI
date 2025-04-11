
import { useState } from "react";
import { ThumbsUp, ThumbsDown, Loader } from "lucide-react";
import { Button } from "@/components/ui/button";
import { gmailService } from "@/services/gmailService";
import { useToast } from "@/components/ui/use-toast";

export interface ChatMessageType {
  id: string;
  content: string;
  sender: 'user' | 'assistant';
  isLoading?: boolean;
  responseId?: string;
  feedbackGiven?: 'yes' | 'no';
}

interface ChatMessageProps {
  message: ChatMessageType;
  onFeedbackGiven: (messageId: string, feedback: 'yes' | 'no') => void;
}

export const ChatMessage = ({ message, onFeedbackGiven }: ChatMessageProps) => {
  const { toast } = useToast();

  const handleFeedback = async (feedback: 'yes' | 'no') => {
    if (!message.responseId || message.feedbackGiven) return;
    
    try {
      await gmailService.sendInferenceFeedback(message.responseId, feedback);
      onFeedbackGiven(message.id, feedback);
      
      toast({
        title: "Feedback Sent",
        description: "Thank you for your feedback!",
      });
    } catch (error) {
      console.error("Failed to send feedback:", error);
      toast({
        title: "Error",
        description: "Failed to send feedback. Please try again.",
        variant: "destructive",
      });
    }
  };

  return (
    <div 
      className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
    >
      <div 
        className={`relative rounded-lg p-3 max-w-[80%] ${
          message.sender === 'user' 
            ? 'bg-primary text-primary-foreground' 
            : 'bg-muted text-muted-foreground'
        }`}
      >
        {message.isLoading ? (
          <div className="flex items-center gap-2">
            <Loader className="h-4 w-4 animate-spin" />
            <span>Thinking...</span>
          </div>
        ) : (
          <>
            {message.content}
            
            {/* Feedback buttons for assistant messages only */}
            {message.sender === 'assistant' && message.responseId && (
              <div className="flex items-center gap-2 mt-2 text-xs">
                <Button
                  variant="ghost"
                  size="sm"
                  className={`p-1 h-auto ${message.feedbackGiven === 'yes' ? 'text-green-500' : 'text-muted-foreground hover:text-green-500'}`}
                  onClick={() => handleFeedback('yes')}
                  disabled={!!message.feedbackGiven}
                >
                  <ThumbsUp className="h-3 w-3" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className={`p-1 h-auto ${message.feedbackGiven === 'no' ? 'text-red-500' : 'text-muted-foreground hover:text-red-500'}`}
                  onClick={() => handleFeedback('no')}
                  disabled={!!message.feedbackGiven}
                >
                  <ThumbsDown className="h-3 w-3" />
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
