import React from "react";
export class ErrorBoundary extends React.Component<any, { hasError: boolean; error: any }> {
  constructor(props: any) { super(props); this.state = { hasError: false, error: null }; }
  static getDerivedStateFromError(error: any) { return { hasError: true, error }; }
  componentDidCatch(error: any, errorInfo: any) { console.error("ErrorBoundary caught an error", error, errorInfo); }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 20, backgroundColor: "#fff", height: "100vh" }}>
          <h1 style={{ color: "red", fontSize: 24 }}>App Crashed</h1>
          <pre style={{ whiteSpace: "pre-wrap", color: "black", fontSize: 12 }}>{this.state.error?.toString()}</pre>
          <pre style={{ whiteSpace: "pre-wrap", color: "black", fontSize: 10 }}>{this.state.error?.stack}</pre>
          <button onClick={() => { localStorage.clear(); window.location.reload(); }} style={{ marginTop: 20, padding: 10, background: "blue", color: "white" }}>Clear Data & Reload</button>
        </div>
      );
    }
    return this.props.children;
  }
}
