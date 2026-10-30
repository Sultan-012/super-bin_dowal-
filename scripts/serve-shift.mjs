// Local same-origin production build. No data or credentials are generated here.
import {spawn} from 'node:child_process';
import {existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const candidate=path.join(root,'backend','.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
const python=process.env.PYTHON_BIN||(existsSync(candidate)?candidate:(process.platform==='win32'?'python':'python3'));
if(!existsSync(path.join(root,'frontend','dist','index.html')))throw new Error('Build first: npm --prefix frontend run build');
const args=process.argv.slice(2);function option(name,fallback){const index=args.indexOf(name);return index<0?fallback:args[index+1]}
const child=spawn(python,['-m','uvicorn','shift_app.main:create_app','--factory','--host',option('--host','127.0.0.1'),'--port',option('--port',process.env.PORT||'8000')],{cwd:path.join(root,'backend'),stdio:'inherit'});
child.on('error',error=>{process.stderr.write(error.message+'\n');process.exit(1)});
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>child.kill(signal));
child.on('exit',code=>process.exit(code??1));
