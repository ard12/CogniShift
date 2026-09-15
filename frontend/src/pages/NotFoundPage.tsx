import { Link } from "react-router-dom";
import { Button } from "@/components/ui/Button";

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
      <p className="font-mono text-xs uppercase tracking-widest text-ink-3">404</p>
      <h1 className="text-lg font-semibold text-ink-1">Route not found</h1>
      <p className="max-w-sm text-sm text-ink-3">
        This page doesn't exist in the CogniShift console. Head back to the dashboard to continue.
      </p>
      <Link to="/dashboard">
        <Button variant="primary" size="sm">
          Back to dashboard
        </Button>
      </Link>
    </div>
  );
}
