/** Offline end-to-end checks against tests/serve_dashboard.py. No live profile collection. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(root, 'frontend', 'package.json'));
const { chromium } = require('playwright');
const base = 'http://127.0.0.1:8124';
const token = process.env.SOCIALINTEL_TEST_TOKEN;
assert(token && token.length >= 32, 'Use a disposable SOCIALINTEL_TEST_TOKEN for the synthetic test server.');
const artifacts = path.join(root, '.qa', 'dashboard');
await fs.mkdir(artifacts, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  ...(process.env.SOCIALINTEL_BROWSER_EXECUTABLE ? {
    executablePath: process.env.SOCIALINTEL_BROWSER_EXECUTABLE,
    args: ['--no-sandbox', '--no-zygote', '--disable-dev-shm-usage', '--disable-gpu'],
  } : {}),
});
const errors = [], external = [], checks = [];
let page;
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1080 }, acceptDownloads: true });
  page = await context.newPage();
  page.setDefaultTimeout(8000);
  page.on('pageerror', error => errors.push(String(error)));
  page.on('request', req => {
    if (!req.url().startsWith(base) && !req.url().startsWith('blob:')) external.push(req.url());
  });
  await page.goto(base);
  await page.getByRole('button', { name: 'Unlock workspace' }).waitFor();
  await page.getByPlaceholder('Enter your bearer token').fill('wrong-token-with-enough-characters-to-pass-form-validation');
  await page.getByRole('button', { name: 'Unlock workspace' }).click();
  await page.getByText('A valid bearer token is required.').waitFor();
  await page.getByPlaceholder('Enter your bearer token').fill(token);
  await page.getByRole('button', { name: 'Unlock workspace' }).click();
  await page.getByRole('button', { name: 'Refresh workspace' }).waitFor();
  checks.push('invalid token rejected; valid token unlocks');

  const nav = page.getByRole('navigation', { name: 'Main navigation' });
  await nav.getByRole('button', { name: 'Cases', exact: true }).click();
  await page.getByLabel('CASE NAME', { exact: true }).fill('Synthetic release QA');
  await page.getByLabel('RESEARCH PURPOSE', { exact: true }).fill('Offline synthetic fixtures only. No real accounts were investigated.');
  await page.getByRole('button', { name: 'Create case', exact: true }).click();
  await page.getByRole('heading', { name: 'Synthetic release QA', exact: true }).waitFor();
  const caseId = page.url().split('#cases/')[1];
  assert(caseId);
  await page.getByLabel('Research notes', { exact: true }).fill('Synthetic notes saved by the release test.');
  await page.getByRole('button', { name: 'Save notes', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('#case-notes')?.value === 'Synthetic notes saved by the release test.');
  await page.getByLabel('PUBLIC SOURCE URL', { exact: true }).fill('https://example.org/');
  await page.getByLabel('EXPORTED FIELDS · JSON OBJECT', { exact: true }).fill(JSON.stringify({ bio: '<script>synthetic-only</script>' }));
  await page.getByRole('button', { name: 'Import fields', exact: true }).click();
  await page.getByRole('heading', { name: 'Imported evidence', exact: true }).waitFor();
  assert(await page.getByText('<script>synthetic-only</script>', { exact: true }).isVisible());
  checks.push('case creation, notes, unverified import, HTML text escaping');

  await nav.getByRole('button', { name: 'New investigation', exact: true }).click();
  await page.getByLabel('Platform', { exact: true }).selectOption('instagram');
  await page.getByPlaceholder('Username, public profile URL, or display name').fill('synthetic-demo');
  await page.getByLabel('Save to case', { exact: true }).selectOption(caseId);
  await page.getByText('Collection options and limits', { exact: true }).click();
  await page.getByLabel('Collect supported public posts', { exact: true }).check();
  await page.getByRole('button', { name: 'Start investigation', exact: true }).click();
  await page.locator('.badge').filter({ hasText: /^completed$/i }).first().waitFor({ timeout: 15000 });
  await page.getByText('UNSUPPORTED BY THIS PROVIDER', { exact: true }).first().waitFor();
  checks.push('unsupported primary is honest; automatic fallback and public-post collection finish');

  for (const route of ['Profiles', 'Evidence', 'Timeline', 'Relationship graph']) {
    await nav.getByRole('button', { name: route, exact: true }).click();
    await page.getByLabel('Select investigation').waitFor();
    if (route === 'Profiles') await page.getByLabel('Filter profiles').waitFor();
    if (route === 'Evidence') await page.getByLabel('Filter evidence page').waitFor();
    if (route === 'Timeline') await page.getByLabel('Filter timeline').waitFor();
    if (route === 'Relationship graph') {
      await page.getByLabel('Fit graph').waitFor();
      await page.getByLabel('Fit graph').click();
      await page.getByLabel('Find graph node').fill('synthetic');
    }
    assert(!(await page.locator('main').innerText()).includes('Internal processing error'));
    checks.push(route.toLowerCase());
  }

  await nav.getByRole('button', { name: 'Reports', exact: true }).click();
  await page.getByLabel('Select case', { exact: true }).selectOption(caseId);
  for (const format of ['JSON', 'HTML', 'CSV', 'MD']) {
    const pending = page.waitForEvent('download');
    await page.getByRole('button', { name: `Download ${format}`, exact: true }).click();
    const download = await pending;
    const filename = path.join(artifacts, `synthetic-report.${format.toLowerCase()}`);
    await download.saveAs(filename);
    const value = await fs.readFile(filename, 'utf8');
    assert(value.length > 100);
    if (format === 'JSON') assert(JSON.parse(value).evidence.length > 0);
    if (format === 'HTML') assert(!value.includes('<script>'));
  }
  checks.push('all four report downloads and HTML escaping');

  await nav.getByRole('button', { name: 'Platform explorer', exact: true }).click();
  await page.getByLabel('Filter platforms').fill('Instagram');
  assert(await page.getByText('NOT IMPLEMENTED', { exact: true }).isVisible());
  await page.getByRole('button', { name: 'Capabilities', exact: true }).click();
  await page.getByText('UNSUPPORTED BY THIS PROVIDER.', { exact: false }).first().waitFor();
  await page.getByLabel('Filter platforms').fill('');
  await page.getByRole('columnheader', { name: 'Last observation', exact: true }).waitFor();
  checks.push('catalog filtering, unsupported detail, readiness separate from observations');

  for (const name of ['Platform health', 'Plugins', 'Settings']) {
    await nav.getByRole('button', { name, exact: true }).click();
    await page.locator('main h1').waitFor();
    assert(!(await page.locator('main').innerText()).includes('Internal processing error'));
  }
  checks.push('health, plugin, and settings pages');
  await nav.getByRole('button', { name: 'Overview', exact: true }).click();
  await page.getByRole('button', { name: 'Refresh workspace' }).click();
  await page.getByText('synthetic-demo', { exact: true }).first().waitFor();
  await page.screenshot({ path: path.join(artifacts, 'dashboard-desktop.png'), fullPage: true });

  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `Horizontal overflow at ${width}px`);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByLabel('Open navigation', { exact: true }).click();
  await nav.getByRole('button', { name: 'Cases', exact: true }).click();
  await page.getByRole('heading', { name: 'Cases', exact: true }).waitFor();
  assert(await page.getByLabel('Open navigation', { exact: true }).isVisible());
  await page.waitForFunction(() => document.querySelector('.sidebar').getBoundingClientRect().right <= 0);
  await page.screenshot({ path: path.join(artifacts, 'dashboard-mobile.png'), fullPage: true });
  checks.push('no overflow at 320/390/768/1440px; mobile navigation');

  await page.getByLabel('Lock workspace', { exact: true }).click();
  await page.getByRole('button', { name: 'Unlock workspace' }).waitFor();
  assert.equal(await page.evaluate(() => sessionStorage.getItem('socialintel-token')), null);
  checks.push('lock clears tab token and hides research');
  assert.deepEqual(errors, []);
  assert.deepEqual(external, []);
  const result = { result: 'passed', browser: await browser.version(), synthetic: true, checks, pageErrors: errors, externalRequests: external };
  await fs.writeFile(path.join(artifacts, 'result.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
} catch (error) {
  if (page) {
    await page.screenshot({ path: path.join(artifacts, "failure.png"), fullPage: true });
    await fs.writeFile(path.join(artifacts, "failure.txt"), await page.locator("body").innerText());
  }
  throw error;
} finally {
  await browser.close();
}
