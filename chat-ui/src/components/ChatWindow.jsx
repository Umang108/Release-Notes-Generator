import { useState } from "react";
import { sendQuery } from "../services/api";

const ChatWindow = ({ addChat, activeChat }) => {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);

  const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8507";

  const buildPdfUrl = (pdfUrl) => {
    if (!pdfUrl) return null;
    if (pdfUrl.startsWith("http://") || pdfUrl.startsWith("https://"))
      return pdfUrl;
    return `${API_BASE}${pdfUrl}`; // "/pdf/.." -> full url
  };

  // ✅ GET request Preview
  const handlePreview = async () => {
    if (!activeChat?.pdf_url) return;

    const pdfUrl = buildPdfUrl(activeChat.pdf_url);

    try {
      const res = await fetch(pdfUrl, { method: "GET" });
      if (!res.ok) throw new Error("Failed to load PDF");

      const blob = await res.blob();
      const fileUrl = window.URL.createObjectURL(blob);

      window.open(fileUrl, "_blank"); // open preview
    } catch (err) {
      alert("Preview failed!");
      console.error(err);
    }
  };

  // ✅ GET request Download
  const handleDownload = async () => {
    if (!activeChat?.pdf_url) return;

    const pdfUrl = buildPdfUrl(activeChat.pdf_url);

    try {
      const res = await fetch(pdfUrl, { method: "GET" });
      if (!res.ok) throw new Error("Failed to download PDF");

      const blob = await res.blob();
      const fileUrl = window.URL.createObjectURL(blob);

      const link = document.createElement("a");
      link.href = fileUrl;

      // filename from url
      const filename = pdfUrl.split("/").pop() || "release_notes.pdf";
      link.download = filename;

      document.body.appendChild(link);
      link.click();
      link.remove();

      window.URL.revokeObjectURL(fileUrl);
    } catch (err) {
      alert("Download failed!");
      console.error(err);
    }
  };

  const handleSend = async () => {
    if (!question.trim()) return;

    setLoading(true);
    try {
      const res = await sendQuery(question);

      addChat({
        question,
        reply: res.data.message || res.data.reply,
        pdf_url: res.data.pdf_url,
      });

      setQuestion("");
    } catch (err) {
      const errorMsg =
        err.response?.data?.detail || "Something went wrong. Please try again.";

      addChat({
        question,
        reply: errorMsg,
        pdf_url: null,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-panel">
      <h2>🤖 Release Notes Assistant</h2>

      <div className="chat-box">
        {loading && (
          <div className="loader-container">
            <div className="spinner"></div>
            <p>Generating release notes…</p>
          </div>
        )}

        {!loading && activeChat && (
          <>
            <p className="reply">{activeChat.reply}</p>

            {activeChat.pdf_url && (
              <div className="pdf-actions">
                <button onClick={handlePreview} className="pdf-btn">
                  📄 Preview PDF
                </button>

                <button onClick={handleDownload} className="pdf-btn outline">
                  ⬇ Download
                </button>
              </div>
            )}
          </>
        )}

        {!loading && !activeChat && (
          <p className="empty-text">Start a new chat by asking a question 👋</p>
        )}
      </div>

      <div className="input-area">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask something..."
        />
        <button onClick={handleSend} disabled={loading}>
          Send
        </button>
      </div>
    </div>
  );
};

export default ChatWindow;
