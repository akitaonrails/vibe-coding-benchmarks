// Frozen minimal declarations for the only Node transport APIs used by the scaffold.
// Application JSON/domain types live in editable src/. No npm dependencies.
declare module 'node:process' {
  export const stdin: { readonly readable: boolean };
  export const stdout: { write(text: string): boolean };
}
declare module 'node:readline' {
  export function createInterface(options: { input: { readonly readable: boolean }; crlfDelay: number }): {
    on(event: 'line', callback: (line: string) => void): void;
  };
}
declare function structuredClone<T>(value: T): T;
