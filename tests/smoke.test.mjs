import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '..');

async function readRepoFile(relativePath) {
  return fs.readFile(path.join(repoRoot, relativePath), 'utf8');
}

async function loadDiaryData() {
  const source = await readRepoFile('data/athlete-diary.js');
  const context = { globalThis: {} };
  vm.createContext(context);
  new vm.Script(source, { filename: 'data/athlete-diary.js' }).runInContext(context);
  return context.globalThis.RUNRUN_DIARY_DATA;
}

test('diary mirror exposes expected athlete and race summary', async () => {
  const diary = await loadDiaryData();

  assert.ok(diary, 'RUNRUN_DIARY_DATA should be defined');
  assert.equal(diary.meta?.source_site, 'Athlinks');
  assert.equal(diary.athlete?.display_name, 'Elisa Park');
  assert.equal(diary.athlete?.result_count, 107);
  assert.equal(diary.overview?.total_races, diary.results?.length);
  assert.ok(diary.overview?.weather_coverage_count <= diary.results.length);
  assert.match(diary.meta?.notes?.join(' ') ?? '', /local JS mirror/i);
});

test('diary results stay reverse-chronological for newest-first browsing', async () => {
  const diary = await loadDiaryData();
  const raceDates = Array.from(diary.results, (entry) => entry.race_date || '');
  const sorted = [...raceDates].sort((a, b) => String(b).localeCompare(String(a)));

  assert.equal(JSON.stringify(raceDates), JSON.stringify(sorted));
});

test('index page wires local data sources and smoke-test API', async () => {
  const html = await readRepoFile('index.html');

  assert.match(html, /<script src="\.\/data\/athlete-diary\.js"><\/script>/);
  assert.match(html, /fetch\('\.\/data\/athlete-diary\.json', \{ cache: 'no-store' \}\)/);
  assert.match(html, /globalThis\.RunRunDiary = \{[\s\S]*loadData,[\s\S]*classifyDistance,[\s\S]*formatDistance,[\s\S]*deriveVisibleResults,[\s\S]*\};/);
});

test('README documents local validation commands', async () => {
  const readme = await readRepoFile('README.md');

  assert.match(readme, /npm test/);
  assert.match(readme, /python3 -m py_compile scripts\/build_diary_data\.py/);
  assert.match(readme, /GitHub Actions/i);
});
