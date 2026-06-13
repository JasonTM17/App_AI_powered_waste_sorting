"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCcw } from "lucide-react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error in component:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="error-boundary-alert alert danger compact-alert">
          <AlertTriangle size={20} />
          <div style={{ flex: 1 }}>
            <strong>Đã xảy ra lỗi hiển thị</strong>
            <p style={{ margin: 0, fontSize: "0.85em", opacity: 0.9 }}>
              {this.state.error?.message || "Lỗi không xác định."}
            </p>
          </div>
          <button
            type="button"
            className="icon-button"
            onClick={() => this.setState({ hasError: false })}
            title="Thử lại"
          >
            <RefreshCcw size={16} />
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
