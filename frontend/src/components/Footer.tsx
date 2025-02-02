export const Footer = () => {
  return (
    <footer className="bg-secondary/50 py-12">
      <div className="container mx-auto mt-8 pt-8 border-t">
        <p className="text-center text-sm text-muted-foreground">
          © {new Date().getFullYear()} InboxAI. All rights reserved.
        </p>
      </div>
    </footer>
  );
};
