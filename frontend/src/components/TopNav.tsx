import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { useState } from "react";
import { LogoutDialog } from "./LogoutDialog";

export const TopNav = () => {
  const [showLogoutDialog, setShowLogoutDialog] = useState(false);

  return (
    <nav className="h-16 border-b bg-background">
      <div className="container mx-auto h-full flex items-center justify-between px-4">
        <Link
          to="/"
          className="text-2xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent"
        >
          InboxAI
        </Link>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            className="hover:bg-[#b5adff]"
            onClick={() => setShowLogoutDialog(true)}
          >
            <LogOut className="h-5 w-5" />
          </Button>
        </div>
      </div>

      <LogoutDialog
        open={showLogoutDialog}
        onOpenChange={setShowLogoutDialog}
      />
    </nav>
  );
};
