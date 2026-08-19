import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GOPIPE — 設備積算AI",
  description:
    "設備図から拾い出し・見積・申請・保全までを一気通貫にする設備積算AI。AIは提案、確定は人。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
