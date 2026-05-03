import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children?: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div style={{ padding: "2rem", color: "#ef4444", background: "#fee2e2", borderRadius: "8px" }}>
          <h3 style={{ margin: "0 0 1rem 0" }}>Something went wrong in the 3D view</h3>
          <pre style={{ fontSize: "0.8rem", overflow: "auto" }}>{this.state.error?.message}</pre>
        </div>
      );
    }

    return this.props.children;
  }
}
