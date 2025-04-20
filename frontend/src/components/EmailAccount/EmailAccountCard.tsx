import { RefreshCcw, Trash2, Loader, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConnectedEmail } from "@/services/gmailService";
import { format, parseISO, isValid } from "date-fns";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

interface EmailAccountCardProps {
  account: ConnectedEmail;
  onRefresh: (email: string) => void;
  onRemove: (email: string) => void;
  isRefreshing: boolean;
}

export const EmailAccountCard = ({
  account,
  onRemove,
  isRefreshing,
}: EmailAccountCardProps) => {
  const formatDate = (dateString: string) => {
    try {
      return dateString
        ? format(new Date(dateString), "MMM d, yyyy h:mm a")
        : "";
    } catch (error) {
      return "-";
    }
  };
  const isActivelyRefreshing =
    account.run_status !== "COMPLETED" || isRefreshing;
  return (
    <Card className="relative">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Mail className="h-5 w-5" />
          {account.email}
          {isActivelyRefreshing && (
            <Loader className="h-4 w-4 animate-spin ml-auto" />
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-2">
            <span>{account.total_emails_processed} emails processed</span>
          </div>
          <div className="flex items-center gap-2 mb-4">
            <span>Refresh status: {account.run_status}</span>
          </div>

          <div className="flex items-center gap-2">
            <RefreshCcw className="h-4 w-4 text-muted-foreground" />
            <span>Last refreshed: {formatDate(account.last_read)}</span>
          </div>
          <div className="flex justify-end">
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-red-500 hover:text-red-700"
                >
                  <Trash2 className="h-4 w-4" />
                  <span>Remove</span>
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Remove Email Account</AlertDialogTitle>
                  <AlertDialogDescription>
                    Are you sure you want to remove {account.email}? This action
                    cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={() => onRemove(account.email)}
                    className="bg-red-500 hover:bg-red-700 text-white"
                  >
                    Remove
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
