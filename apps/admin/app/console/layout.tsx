import { CommandShell } from "@/components/command-shell";

export default function ConsoleLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <CommandShell>{children}</CommandShell>;
}
