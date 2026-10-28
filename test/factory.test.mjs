import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';

test('take factory unit tests pass', () => {
  const r = spawnSync('python3', ['-m', 'unittest', 'test_take_factory'], { cwd: 'tools/factory', encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
});
