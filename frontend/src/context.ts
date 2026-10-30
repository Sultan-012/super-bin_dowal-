import { createContext, useContext } from "react";
import type { Me, Page } from "./types";
export const Context = createContext<{
  me: Me;
  revision: number;
  refresh: () => void;
  notify: (text: string) => void;
  navigate: (page: Page, sid?: number) => void;
}>(null!);
export const useApp = () => useContext(Context);
