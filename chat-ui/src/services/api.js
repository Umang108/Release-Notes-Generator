import axios from "axios";

const api = axios.create({
    baseURL: "http://127.0.0.1:8507",
    headers: {
        "Content-Type": "application/json",
    },
});

export const sendQuery = (message) => {
    return api.post("/query", {
        message: message,   // ✅ EXACT MATCH WITH BACKEND
    });
};
