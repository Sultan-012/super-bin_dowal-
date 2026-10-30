import {createContext,useContext} from 'react';
import type {Me,Page} from './types';
export type ThemeMode='light'|'dark';
export const Context=createContext<{me:Me;revision:number;refresh:()=>void;notify:(s:string)=>void;navigate:(page:Page,id?:number)=>void;theme:ThemeMode;toggleTheme:()=>void}>({} as never);
export const useApp=()=>useContext(Context);
