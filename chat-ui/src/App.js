import { useState, useEffect } from "react";
import ChatHistory from "./components/ChatHistory";
import ChatWindow from "./components/ChatWindow";
import "./App.css";

function App() {
  const [chats, setChats] = useState([]);
  const [activeChat, setActiveChat] = useState(null);

  // 🔹 Load from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("chatHistory");
    if (saved) {
      const parsed = JSON.parse(saved);
      setChats(parsed);
      setActiveChat(parsed[0] || null);
    }
  }, []);

  // 🔹 Save to localStorage
  useEffect(() => {
    localStorage.setItem("chatHistory", JSON.stringify(chats));
  }, [chats]);

  const addChat = (chat) => {
    const updated = [chat, ...chats];
    setChats(updated);
    setActiveChat(chat);
  };

  const clearChats = () => {
    localStorage.removeItem("chatHistory");
    setChats([]);
    setActiveChat(null);
  };

  return (
    <div className="app-container">
      <ChatHistory
        chats={chats}
        activeChat={activeChat}
        setActiveChat={setActiveChat}
        clearChats={clearChats}
      />
      <ChatWindow addChat={addChat} activeChat={activeChat} />
    </div>
  );
}

export default App;
