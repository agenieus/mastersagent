import React from "react";

interface MemoryBadgeProps {
  count: number;
}

export default function MemoryBadge({ count }: MemoryBadgeProps) {
  if (count <= 0) return null;

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
        padding: "2px 8px",
        borderRadius: "12px",
        backgroundColor: "rgba(100, 100, 255, 0.1)",
        color: "#646cff",
        fontSize: "0.75rem",
        fontWeight: 600,
        marginBottom: "8px",
        border: "1px solid rgba(100, 100, 255, 0.2)",
      }}
    >
      <span>🧠</span>
      <span>{count} {count === 1 ? "memory" : "memories"} used</span>
    </div>
  );
}
