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

test('weather sampling uses race-time windows and Davis Moonlight override', async () => {
  const diary = await loadDiaryData();
  const moonlight = diary.results.find((entry) => entry.race_name === 'Davis Moonlight Run' && entry.race_date_local === '2025-07-12');

  assert.ok(moonlight?.weather, 'Davis Moonlight Run should have weather data');
  assert.equal(moonlight.weather.window_start_local, '2025-07-12T20:00');
  assert.equal(moonlight.weather.window_end_local, '2025-07-12T21:00');
  assert.equal(moonlight.weather.hour_count, 2);
  assert.equal(moonlight.weather.hourly_sample?.[0]?.time, '2025-07-12T20:00');
  assert.equal(moonlight.weather.hourly_sample?.[1]?.time, '2025-07-12T21:00');
});

test('weather metadata includes day/night labels', async () => {
  const diary = await loadDiaryData();
  const moonlight = diary.results.find((entry) => entry.race_name === 'Davis Moonlight Run' && entry.race_date_local === '2025-07-12');
  const davisStampede = diary.results.find((entry) => entry.race_name === 'Davis Stampede' && entry.race_date_local === '2026-02-22');
  const goldenGateHalf = diary.results.find((entry) => entry.race_name === 'Golden Gate Half' && entry.race_date_local === '2025-11-02');

  assert.equal(moonlight?.weather?.day_period, 'night');
  assert.equal(moonlight?.weather?.day_period_label, 'Night race');
  assert.equal(davisStampede?.weather?.day_period, 'day');
  assert.equal(davisStampede?.weather?.day_period_label, 'Day race');
  assert.equal(goldenGateHalf?.weather?.day_period, 'day');
  assert.equal(goldenGateHalf?.weather?.day_period_label, 'Day race');
});

test('index page wires local data sources and smoke-test API', async () => {
  const html = await readRepoFile('index.html');

  assert.match(html, /<script src="\.\/data\/athlete-diary\.js"><\/script>/);
  assert.match(html, /fetch\('\.\/data\/athlete-diary\.json', \{ cache: 'no-store' \}\)/);
  assert.match(html, /globalThis\.RunRunDiary = \{[\s\S]*loadData,[\s\S]*classifyDistance,[\s\S]*formatDistance,[\s\S]*deriveVisibleResults,[\s\S]*\};/);
});

test('scatter plot and grit map labels stay semantically clear', async () => {
  const html = await readRepoFile('index.html');

  assert.match(html, /function isTrailEffort\(result\) \{/);
  assert.match(html, /return trailText\.includes\('trail'\);/);
  assert.match(html, /const y = \(value\) => pad \+ \(\(value - minPace\) \/ Math\.max\(maxPace - minPace, 1\)\) \* \(height - pad \* 2\);/);
  assert.match(html, /<text x="\$\{width - 155\}" y="\$\{height - 12\}" fill="#7a6f64" font-size="12">Warmer temp<\/text>/);
  assert.match(html, /const y = baseline - \(\(item\.score \/ peakMax\) \* 88\);/);
  assert.doesNotMatch(html, /item\.trail \? 10 : 0/);
  assert.match(html, /\+ \(trail \? 18 : 0\)/);
  assert.match(html, /trail,\n              pace: result\.pace_seconds_per_mile,/);
  assert.match(html, /<text x="\$\{point\.x\.toFixed\(1\)\}" y="\$\{\(baseline \+ 14\)\.toFixed\(1\)\}" text-anchor="middle" fill="#7a6f64" font-size="11">\$\{index \+ 1\}<\/text>/);
  assert.match(html, /A proxy based on distance, trail bias, finish duration, weather strain, and slower-than-baseline pace\. Trail efforts are black dots; road efforts are brown\./);
  assert.match(html, /const isNight = point\.day_period === 'night';/);
  assert.match(html, /const fill = isNight \? '#a88fcb' : rainy \? '#1f1a17' : '#b69b7a';/);
  assert.match(html, /<span><i style="background:#a88fcb"><\/i> Night race<\/span>/);
});

test('bucket charts render in canonical order with signed bars for relative pace deltas', async () => {
  const html = await readRepoFile('index.html');

  assert.match(html, /const TEMPERATURE_BUCKET_ORDER = \['<45°F', '45–54°F', '55–64°F', '65–74°F', '75°F\+', 'Unknown'\];/);
  assert.match(html, /const WIND_BUCKET_ORDER = \['<6 mph', '6–9 mph', '10–13 mph', '14\+ mph', 'Unknown'\];/);
  assert.match(html, /const HUMIDITY_BUCKET_ORDER = \['<50%', '50–64%', '65–74%', '75%\+', 'Unknown'\];/);
  assert.match(html, /body: createBarList\(sortBuckets\(weather\.temperature_bins \|\| \[], TEMPERATURE_BUCKET_ORDER\), 'avg_pace_seconds_per_mile'\)/);
  assert.match(html, /function createSignedBarList\(items, valueKey, className = '', formatter = null\) \{/);
  assert.match(html, /const directionClass = value < 0 \? 'negative' : 'positive';/);
  assert.match(html, /const zeroOffset = value == null \? 50 : value < 0 \? 50 - width : 50;/);
  assert.match(html, /<div class="track signed"><div class="zero-line"><\/div><div class="fill \$\{className\} \$\{directionClass\}" style="left:\$\{zeroOffset\}%; width:\$\{width\}%"><\/div><\/div>/);
  assert.match(html, /\.track\.signed \{/);
  assert.match(html, /\.zero-line \{/);
  assert.match(html, /\.fill\.negative \{/);
  assert.match(html, /body: createSignedBarList\(windBins, 'avg_pace_vs_pattern_baseline_pct', 'alt'\)/);
  assert.match(html, /copy: 'Avg pace-vs-your baseline pace by wind speed bin\. Positive bars mean slower-than-baseline pacing\.'/);
  assert.match(html, /footer: windOutlier \? `\$\{windOutlier\.label\} is the slowest relative wind bucket at \$\{formatSignedPercent\(windOutlier\.avg_pace_vs_pattern_baseline_pct\)\} across \$\{windOutlier\.race_count\} races\.` : ''/);
  assert.match(html, /copy: 'Pacing by humidity relative to your baseline\. Positive bars mean slower-than-baseline pacing\.'/);
  assert.match(html, /body: createSignedBarList\(humidityBins, 'avg_pace_vs_pattern_baseline_pct', 'alt'\)/);
  assert.match(html, /There is not a simple more-humidity-equals-slower pattern here\. Interestingly, in the most humid conditions \(\$\{humidityMostHumid\.label\}\) your pace was faster than your baseline on similar courses\./);
  assert.match(html, /\{ label: 'Humidity vs pace', title: correlations\.humidity_vs_pace_seconds_per_mile == null \? '—' : String\(correlations\.humidity_vs_pace_seconds_per_mile\), copy: 'Negative means more humid races were slightly faster overall\.' \},/);
  assert.match(html, /\$\{chart\.footer \? `<div class="mini-copy" style="margin-top:12px;">\$\{chart\.footer\}<\/div>` : ''\}/);
});

test('README documents local validation commands', async () => {
  const readme = await readRepoFile('README.md');

  assert.match(readme, /npm test/);
  assert.match(readme, /python3 -m py_compile scripts\/build_diary_data\.py/);
  assert.match(readme, /GitHub Actions/i);
});
