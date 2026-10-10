import { createInterface } from 'node:readline';
import { stdin, stdout } from 'node:process';
import { Request } from './domain';
import { Engine } from './solution';
const engine = new Engine();
const lines = createInterface({ input: stdin, crlfDelay: Infinity });
// The public contract guarantees valid request shapes; conversion is at this boundary.
lines.on('line', line => stdout.write(JSON.stringify(engine.handle(JSON.parse(line) as Request)) + '\n'));
