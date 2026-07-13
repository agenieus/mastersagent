import { Conversation } from "@/lib/types";
import styles from "../app/chat/chat.module.css";

interface SidebarProps {
  conversations: Conversation[];
  activeId: number | null;
  onSelect: (id: number) => void;
  onNewChat: () => void;
}

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNewChat,
}: SidebarProps) {
  return (
    <div className={styles.sidebar}>
      <div className={styles.sidebarHeader}>
        <button className={styles.newChatBtn} onClick={onNewChat}>
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          New Chat
        </button>
      </div>
      <div className={styles.conversationList}>
        {conversations.map((c) => (
          <button
            key={c.id}
            className={`${styles.convItem} ${
              activeId === c.id ? styles.active : ""
            }`}
            onClick={() => onSelect(c.id)}
            title={c.title}
          >
            {c.title}
          </button>
        ))}
      </div>
    </div>
  );
}
