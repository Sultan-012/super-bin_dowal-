// Same-origin preview of the real built application. No sample data is created.
import {spawn} from 'node:child_process';
import {existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const args=process.argv.slice(2);
function option(name,fallback){const i=args.lastIndexOf(name);return i>=0?args[i+1]:fallback}
const executable=path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
const python=existsSync(executable)?executable:(process.platform==='win32'?'python':'python3');
if(!existsSync(path.join(root,'frontend','dist','index.html')))throw new Error('Build the frontend first: npm --prefix frontend run build');
const child=spawn(python,['-m','uvicorn','app.main:create_app','--factory','--host',option('--host','127.0.0.1'),'--port',option('--port',process.env.PORT||'8000')],{cwd:path.join(root,'backend'),stdio:'inherit'});
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>child.kill(signal));
child.on('exit',code=>process.exit(code??1));
