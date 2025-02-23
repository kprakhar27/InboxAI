import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { HashRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import Login from "./pages/Login";
import Home from "./pages/Home";
import Redirect from "./pages/Redirect";
import { Toaster } from "./components/ui/toaster";
import AccountSettings from "./pages/settings/Account";
import EmailDataSettings from "./pages/settings/EmailData";
import PreferencesSettings from "./pages/settings/Preferences";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <HashRouter>
      <Routes>
        <Route path="/inbox-ai" element={<Index />} />
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Home />} />
        <Route path="/redirect" element={<Redirect />} />
        <Route path="/settings/account" element={<AccountSettings />} />
        <Route path="/settings/email" element={<EmailDataSettings />} />
        <Route path="/settings/preferences" element={<PreferencesSettings />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      <Toaster />
    </HashRouter>
  </QueryClientProvider>
);

export default App;
