
import { useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const ConnectedState = () => {
  const [message, setMessage] = useState("");

  const handleSend = () => {
    if (!message.trim()) return;
    // TODO: Implement message sending
    console.log("Sending message:", message);
    setMessage("");
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      <div className="flex-1 overflow-y-auto p-4">
        {/* Chat history will go here */}
        <div className="space-y-4">
          {/* Example messages */}
          <div className="flex justify-end">
            <div className="bg-primary text-primary-foreground rounded-lg p-3 max-w-[80%]">
              How can I help with your emails today?
            </div>
          </div>
        </div>
      </div>
      
      <div className="border-t p-4">
        <div className="flex gap-2 max-w-3xl mx-auto">
          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Type your message..."
            className="flex-1"
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
          />
          <Button 
            onClick={handleSend}
            className="hover:bg-[#b5adff]"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};
