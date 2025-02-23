
import { SettingsHeader } from "@/components/SettingsHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Mail, Trash2 } from "lucide-react";

const EmailDataSettings = () => {
  const connectedAccounts = [
    { email: "user@gmail.com", provider: "Gmail" },
  ];

  return (
    <div className="container mx-auto px-4 py-8">
      <SettingsHeader title="Email Data Settings" />
      
      <div className="space-y-8 max-w-2xl">
        <Card>
          <CardHeader>
            <CardTitle>Connected Email Accounts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {connectedAccounts.map((account) => (
              <div
                key={account.email}
                className="flex items-center justify-between p-4 border rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <Mail className="h-5 w-5" />
                  <div>
                    <p className="font-medium">{account.email}</p>
                    <p className="text-sm text-muted-foreground">
                      {account.provider}
                    </p>
                  </div>
                </div>
                <Button variant="ghost" size="icon">
                  <Trash2 className="h-5 w-5" />
                </Button>
              </div>
            ))}
            <Button className="w-full">Connect New Account</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Sync Preferences</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Sync Frequency</label>
              <Select defaultValue="30">
                <SelectTrigger>
                  <SelectValue placeholder="Select frequency" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="15">Every 15 minutes</SelectItem>
                  <SelectItem value="30">Every 30 minutes</SelectItem>
                  <SelectItem value="60">Every hour</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Email Scope</label>
              <Select defaultValue="all">
                <SelectTrigger>
                  <SelectValue placeholder="Select scope" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All emails</SelectItem>
                  <SelectItem value="unread">Unread only</SelectItem>
                  <SelectItem value="important">Important only</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button>Save Preferences</Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default EmailDataSettings;
