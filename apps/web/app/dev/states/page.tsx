import { notFound } from "next/navigation";
import StatesGallery from "@/components/StatesGallery";

export const metadata = { title: "States (dev)", robots: { index: false, follow: false } };

export default function StatesPage() {
  if (process.env.NEXT_PUBLIC_DEV !== "1") notFound(); // never exposed in production builds
  return <StatesGallery />;
}
