import "./Footer.css";

export default function Footer() {
  return (
    <footer className="app-footer">
      <strong>VTU AI</strong>

      <p>
        AI-powered VTU exam answer generation using your own notes.
      </p>

      <small>© {new Date().getFullYear()} VTU AI. All rights reserved.</small>
    </footer>
  );
}
