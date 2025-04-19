import { Blocks, CalendarSync, ShieldCheck, MailQuestion } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Navbar } from "@/components/Navbar";
import { FeatureCard } from "@/components/FeatureCard";
import { Footer } from "@/components/Footer";
import { useNavigate } from "react-router-dom";

const features = [
  {
    title: "Cross-Platform Integration",
    description:
      "Seamlessly connects with multiple email platforms, allowing users to manage all their accounts in one place.",
    icon: Blocks,
  },
  {
    title: "Contextual Querying",
    description:
      "Enables users to ask questions about their emails, past conversations, and important details from their inbox.",
    icon: MailQuestion,
  },
  {
    title: "Task Automation",
    description:
      "Extracts action items, schedules tasks, and sets reminders directly from email content to boost productivity.",
    icon: CalendarSync,
  },
  {
    title: "Privacy-Focused",
    description:
      "Ensures user data security by following strict privacy regulations while processing emails and generating insights.",
    icon: ShieldCheck,
  },
];

const Index = () => {
  const navigate = useNavigate();
  const handleGetStarted = () => {
    navigate("/login", { state: { register: true } });
  };
  return (
    <div className="min-h-screen">
      <Navbar />

      {/* Hero Section */}
      <section className="section-padding pt-32 md:pt-40">
        <div className="container mx-auto text-center">
          <h1 className="text-4xl md:text-6xl font-bold mb-6 animate-fade-down">
            Your Inbox,{" "}
            <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
              Supercharged with AI
            </span>
          </h1>
          <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto animate-fade-up">
            Transform your email experience with AI-powered insights, smart
            automation, and effortless organization.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center animate-fade-up">
            <Button
              size="lg"
              className="bg-primary hover:bg-primary/90"
              onClick={handleGetStarted}
            >
              Get Started
            </Button>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="section-padding">
        <div className="container mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">
            Powerful Features for Your Inbox
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((feature, index) => (
              <div
                key={index}
                className="animate-fade-up"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                <FeatureCard {...feature} />
              </div>
            ))}
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
};

export default Index;
