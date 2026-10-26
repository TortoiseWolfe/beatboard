/**
 * ASSETS CREDITS TEST — every file under assets/ (except jingle-local) has a line in CREDITS.md
 * and no shipped path contains "SPN(" or "javaScript30"
 */
import { describe, it } from 'node:test';
import assert from 'node:assert';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

const REPO_ROOT = resolve('./');
const ASSETS_DIR = join(REPO_ROOT, 'assets');
const CREDITS_FILE = join(REPO_ROOT, 'CREDITS.md');

function walk(dir, prefix = '') {
  const entries = readdirSync(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const full = join(dir, entry.name);
    const rel = join(prefix, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'jingle-local') continue; // gitignored, not shipped
      files.push(...walk(full, rel));
    } else {
      files.push(rel);
    }
  }
  return files;
}

describe('assets credits', () => {
  const creditsText = readFileSync(CREDITS_FILE, 'utf-8');
  const assetFiles = walk(ASSETS_DIR).filter(f => f !== 'jingle/manifest.json');

  it('every asset file appears in CREDITS.md', () => {
    for (const file of assetFiles) {
      const filename = file.split('/').pop();
      assert.ok(
        creditsText.includes(filename),
        `Missing credit for ${file} (looked for "${filename}")`
      );
    }
  });

  it('no asset path contains "SPN("', () => {
    for (const file of assetFiles) {
      assert.ok(!file.includes('SPN('), `Forbidden pattern "SPN(" in ${file}`);
    }
  });

  it('no asset path contains "javaScript30"', () => {
    for (const file of assetFiles) {
      assert.ok(!file.toLowerCase().includes('javascript30'), `Forbidden pattern "javaScript30" in ${file}`);
    }
  });

  it('CREDITS.md mentions all required license types', () => {
    assert.ok(creditsText.includes('Unlicense'));
    assert.ok(creditsText.includes('CC0'));
    assert.ok(creditsText.includes('CC BY 3.0'));
    assert.ok(creditsText.includes('MIT'));
  });

  it('band portraits exist and are WebP', () => {
    const bandDir = join(ASSETS_DIR, 'band');
    const portraits = ['ivory.webp', 'crash.webp', 'chops.webp', 'reed.webp', 'brass.webp', 'verse.webp', 'form.webp', 'logo.webp'];
    for (const p of portraits) {
      const full = join(bandDir, p);
      const stats = statSync(full);
      assert.ok(stats.size > 0, `${p} is empty`);
      assert.ok(stats.size < 80000, `${p} exceeds 80KB (${stats.size} bytes)`);
    }
  });
});