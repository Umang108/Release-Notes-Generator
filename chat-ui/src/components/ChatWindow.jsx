import { useState } from "react";
import { sendQuery } from "../services/api";

const ChatWindow = ({ addChat, activeChat }) => {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!question.trim()) return;

    setLoading(true);
    try {
      const res = await sendQuery(question);

      addChat({
        question,
        reply: res.data.reply,
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
      <h2>🤖 JIRA Release Assistant</h2>

      <div className="chat-box">
        {/* Loader */}
        {loading && (
          <div className="loader-container">
            <div className="spinner"></div>
            <p>Generating release notes…</p>
          </div>
        )}

        {/* Chat content driven ONLY by activeChat */}
        {!loading && activeChat && (
          <>
            <p className="reply">{activeChat.reply}</p>

            {activeChat.pdf_url && (
              <div className="pdf-actions">
                <a
                  href={activeChat.pdf_url}
                  target="_blank"
                  rel="noreferrer"
                  className="pdf-btn"
                >
                  📄 Preview PDF
                </a>
                <a
                  href={activeChat.pdf_url}
                  download
                  className="pdf-btn outline"
                >
                  ⬇ Download
                </a>
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
