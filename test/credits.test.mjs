/**
 * CREDITS & COMPLIANCE TESTS
 */
import { describe, it } from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';

function getFiles(dir, fileList = []) {
  if (!fs.existsSync(dir)) return fileList;
  const files = fs.readdirSync(dir);
  for (const file of files) {
    if (file === 'jingle-local') continue;
    const fullPath = path.join(dir, file);
    if (fs.statSync(fullPath).isDirectory()) {
      getFiles(fullPath, fileList);
    } else {
      fileList.push(fullPath);
    }
  }
  return fileList;
}

describe('credits and compliance', () => {
  it('CREDITS.md exists and is non-empty', () => {
    assert.ok(fs.existsSync(path.resolve('CREDITS.md')));
    const text = fs.readFileSync(path.resolve('CREDITS.md'), 'utf-8');
    assert.ok(text.length > 50);
  });

  it('no shipped path contains "SPN(" or "javaScript30"', () => {
    function walk(dir) {
      const files = fs.readdirSync(dir);
      for (const file of files) {
        if (file === '.git' || file === 'node_modules' || file === 'jingle-local') continue;
        assert.ok(!file.includes('SPN('), `Forbidden path contains SPN(: ${file}`);
        assert.ok(!file.toLowerCase().includes('javascript30'), `Forbidden path contains javaScript30: ${file}`);
        const full = path.join(dir, file);
        if (fs.statSync(full).isDirectory()) {
          walk(full);
        }
      }
    }
    walk(path.resolve('.'));
  });

  it('every file under assets/ except jingle-local has a line in CREDITS.md', () => {
    const creditsContent = fs.readFileSync(path.resolve('CREDITS.md'), 'utf-8');
    const assetFiles = getFiles(path.resolve('assets'));
    for (const fullPath of assetFiles) {
      const relPath = path.relative(path.resolve('.'), fullPath);
      const basename = path.basename(fullPath);
      const covered = creditsContent.includes(relPath) || creditsContent.includes(basename) || creditsContent.includes(path.dirname(relPath));
      assert.ok(covered, `Asset ${relPath} must be listed in CREDITS.md`);
    }
  });

  it('CREDITS.md attributes ScriptHammer band portraits correctly', () => {
    const credits = fs.readFileSync(path.resolve('CREDITS.md'), 'utf-8');
    assert.ok(credits.includes('Band characters and portraits: the ScriptHammer band, TortoiseWolfe/wp-dev (2025), by Jonathan Pohlner'));
    assert.ok(credits.includes('The tool that made the portraits is not recorded'));
  });

  it('CREDITS.md attributes quarter flip CC BY 3.0 correctly', () => {
    const credits = fs.readFileSync(path.resolve('CREDITS.md'), 'utf-8');
    assert.ok(credits.includes('coin-3.wav by l_q, freesound.org/s/440957, CC BY 3.0'));
  });
});
