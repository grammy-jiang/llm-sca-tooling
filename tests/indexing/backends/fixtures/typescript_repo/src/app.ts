import { helper } from "./util";

export class App {
  run(): string {
    return helper();
  }
}

export function main(): string {
  return helper();
}

export function secondary(): string {
  return main();
}
