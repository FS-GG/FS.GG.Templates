// Deliberately narrow Node CLI ambient interface; actual entrypoint tests verify it.
declare const process: { argv: string[]; stdout: { write(text: string): void }; stderr: { write(text: string): void }; exitCode?: number };
