"use client";

import Link from "next/link";
import styles from "./page.module.css";
import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function Home() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && user) {
      router.push("/chat");
    }
  }, [user, isLoading, router]);

  if (isLoading) return null;

  return (
    <main className={styles.main}>
      <div className={styles.hero}>
        <div className={styles.badge}>v1.0 Now Available</div>
        <h1 className={styles.title}>
          Your Personal <span className={styles.highlight}>AI Agent</span>
        </h1>
        <p className={styles.subtitle}>
          A full-stack, local AI assistant with persistent memory, capable of coding,
          reasoning, and deep conversations.
        </p>
        <div className={styles.actions}>
          <Link href="/register" className={styles.primaryBtn}>
            Get Started
          </Link>
          <Link href="/login" className={styles.secondaryBtn}>
            Log In
          </Link>
        </div>
      </div>
    </main>
  );
}
