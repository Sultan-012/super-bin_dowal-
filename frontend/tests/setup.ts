import {afterEach,vi} from 'vitest';
import {cleanup} from '@testing-library/react';
Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value:function(){this.setAttribute('open','')}});
Object.defineProperty(HTMLDialogElement.prototype,'close',{configurable:true,value:function(){this.removeAttribute('open')}});
Object.defineProperty(window,'scrollTo',{configurable:true,value:vi.fn()});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();localStorage.clear();history.replaceState(null,'','/');document.documentElement.removeAttribute('data-theme');document.body.removeAttribute('data-theme')});
