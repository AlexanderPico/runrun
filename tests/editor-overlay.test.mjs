import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '..');

async function readIndex() {
  return fs.readFile(path.join(repoRoot, 'index.html'), 'utf8');
}

test('Results editor uses a separate local overlay rather than mutating generated source data', async () => {
  const html = await readIndex();

  assert.match(html, /const RESULT_OVERLAY_STORAGE_KEY = 'runrun-results-overlay-v1';/);
  assert.match(html, /function applyResultOverlay\(results, overlay\) \{/);
  assert.match(html, /deleted_ids/);
  assert.match(html, /added_results/);
  assert.match(html, /edited_results/);
  assert.match(html, /state\.data\.results = applyResultOverlay\(/);
});

test('Results editor is explicitly a local convenience gate with add and delete controls', async () => {
  const html = await readIndex();

  assert.match(html, /Editor mode is a local convenience gate, not secure account protection\./);
  assert.match(html, /id="editorLogin"/);
  assert.match(html, /id="editorAddResult"/);
  assert.match(html, /data-delete-result-id=/);
  assert.match(html, /crypto\.subtle\.digest\('SHA-256'/);
});
