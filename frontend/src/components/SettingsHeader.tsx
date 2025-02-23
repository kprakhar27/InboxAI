import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";

interface SettingsHeaderProps {
  title: string;
}

export const SettingsHeader = ({ title }: SettingsHeaderProps) => {
  const navigate = useNavigate();

  return (
    <div className="flex items-center gap-4 mb-8">
      <Button variant="ghost" size="icon" onClick={() => navigate("/")}>
        <ArrowLeft className="h-5 w-5" />
      </Button>
      <h1 className="text-2xl font-bold">{title}</h1>
    </div>
  );
};
