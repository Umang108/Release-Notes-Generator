const ChatHistory = ({ chats, activeChat, setActiveChat, clearChats }) => {
  return (
    <div className="history-panel">
      <div className="history-header">
        <h2>💬 Chats</h2>
        <button className="clear-btn" onClick={clearChats}>
          New Chat
        </button>
      </div>

      {chats.length === 0 && <p className="empty-text">No chats yet</p>}

      {chats.map((chat, index) => (
        <div
          key={index}
          className={`history-item ${activeChat === chat ? "active" : ""}`}
          onClick={() => setActiveChat(chat)}
        >
          {chat.question}
        </div>
      ))}
    </div>
  );
};

export default ChatHistory;
