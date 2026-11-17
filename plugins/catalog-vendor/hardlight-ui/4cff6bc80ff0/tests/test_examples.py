"""Offline examples. Core checks need stdlib only; real Chrome is explicit opt-in.

Run browser checks with HARDLIGHT_BROWSER_TESTS=1 and optionally
HARDLIGHT_CHROME=/path/to/installed/chrome. Otherwise use system Chrome or
an already installed Playwright Chromium. No browser is downloaded.
"""
from html.parser import HTMLParser
from pathlib import Path
import os
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'examples'


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.tags = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class EditorialTests(unittest.TestCase):
    def test_editorial_has_readable_sections_and_local_navigation(self):
        path = EXAMPLES / 'editorial.html'
        self.assertTrue(path.is_file(), 'the editorial reading demo must exist')
        source = path.read_text(encoding='utf-8')
        doc = Document(source)
        ids = [attrs['id'] for _, attrs in doc.tags if 'id' in attrs]
        self.assertEqual(len(ids), len(set(ids)), 'IDs must be unique')
        self.assertIn('shore', ids)
        self.assertIn('listening', ids)
        self.assertIn('keeping', ids)
        self.assertTrue(any(t == 'form' and a.get('role') == 'search' for t, a in doc.tags))
        self.assertIn('aria-live="polite"', source)
        self.assertIn('prefers-reduced-motion', source)
        self.assertIn(':focus-visible', source)
        for tag, attrs in doc.tags:
            if tag == 'a' and attrs.get('href', '').startswith('#'):
                self.assertIn(attrs['href'][1:], ids)


class WorkspaceTests(unittest.TestCase):
    def test_workspace_has_jobs_materials_and_session_log(self):
        path = EXAMPLES / 'workspace.html'
        self.assertTrue(path.is_file(), 'the operating demo must exist')
        source = path.read_text(encoding='utf-8')
        doc = Document(source)
        ids = [a['id'] for _, a in doc.tags if 'id' in a]
        self.assertEqual(len(ids), len(set(ids)))
        for target in ('desk', 'materials', 'session-log', 'job-atlas', 'job-imprint', 'job-fold', 'job-proof'):
            self.assertIn(target, ids)
        self.assertIn('Session-only', source)
        self.assertIn('aria-live="polite"', source)
        self.assertIn(':focus-visible', source)
        self.assertIn('prefers-reduced-motion', source)
        self.assertTrue(any(t == 'select' for t, _ in doc.tags))
        for tag, attrs in doc.tags:
            if tag == 'a' and attrs.get('href', '').startswith('#'):
                self.assertIn(attrs['href'][1:], ids)


class ExpressiveTests(unittest.TestCase):
    def test_expressive_has_program_disclosures_and_honest_event_context(self):
        path = EXAMPLES / 'expressive.html'
        self.assertTrue(path.is_file(), 'the cultural demonstration must exist')
        source = path.read_text(encoding='utf-8')
        doc = Document(source)
        ids = [a['id'] for _, a in doc.tags if 'id' in a]
        self.assertEqual(len(ids), len(set(ids)))
        for target in ('program', 'visit', 'about'):
            self.assertIn(target, ids)
        self.assertGreaterEqual(sum(t == 'details' for t, _ in doc.tags), 4)
        self.assertIn('fictional', source.lower())
        self.assertIn('prefers-reduced-motion', source)
        self.assertIn(':focus-visible', source)
        self.assertIn('aria-live="polite"', source)
        self.assertTrue(any(t == 'svg' for t, _ in doc.tags))
        for tag, attrs in doc.tags:
            if tag == 'a' and attrs.get('href', '').startswith('#'):
                self.assertIn(attrs['href'][1:], ids)


class GalleryTests(unittest.TestCase):
    def test_gallery_links_all_demos_without_remote_dependencies(self):
        path = EXAMPLES / 'index.html'
        self.assertTrue(path.is_file(), 'a navigable gallery index must exist')
        doc = Document(path.read_text(encoding='utf-8'))
        hrefs = [a.get('href') for t, a in doc.tags if t == 'a']
        for name in ('editorial.html', 'workspace.html', 'expressive.html'):
            self.assertIn(name, hrefs)
        for file in EXAMPLES.glob('*.html'):
            source = file.read_text(encoding='utf-8')
            parsed = Document(source)
            self.assertIn('<html lang="en">', source)
            self.assertIn('name="viewport"', source)
            self.assertIn(':focus-visible', source)
            self.assertIn('prefers-reduced-motion', source)
            for tag, attrs in parsed.tags:
                for attr in ('src', 'href', 'action'):
                    value = attrs.get(attr, '')
                    self.assertFalse(value.startswith(('http:', 'https:', '//')), (file.name, value))
                if tag == 'a':
                    href = attrs.get('href', '')
                    self.assertTrue(href, (file.name, 'empty link'))
                    if not href.startswith('#'):
                        self.assertTrue((EXAMPLES / href.split('#')[0]).is_file(), (file.name, href))
            self.assertNotIn('fetch(', source)
            self.assertNotIn('innerHTML', source)
            self.assertNotIn('@import', source)


class SourceEncodingTests(unittest.TestCase):
    def test_source_checks_with_cp1252_default(self):
        original_read_text = Path.read_text

        def read_text(path, encoding='cp1252', **kwargs):
            return original_read_text(path, encoding=encoding, **kwargs)

        suite = unittest.TestSuite(
            unittest.defaultTestLoader.loadTestsFromTestCase(case)
            for case in (EditorialTests, WorkspaceTests, ExpressiveTests, GalleryTests)
        )
        result = unittest.TestResult()
        with patch('pathlib.Path.read_text', read_text):
            suite.run(result)
        self.assertEqual(result.testsRun, 4)
        self.assertTrue(result.wasSuccessful(), result.errors + result.failures)


class BrowserSetupTests(unittest.TestCase):
    def setup_browser(self, explicit='', system=None, installed=True, launch_error=None):
        class Harness(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                ChromeExamplesTests.setUpClass.__func__(cls)
        runtime = MagicMock()
        runtime.chromium.executable_path = '/installed/playwright/chrome'
        runtime.chromium.launch.side_effect = launch_error
        api = SimpleNamespace(sync_playwright=lambda: SimpleNamespace(start=lambda: runtime))
        self.addCleanup(Harness.doClassCleanups)
        with patch.dict('sys.modules', {'playwright.sync_api': api}), \
             patch.dict(os.environ, {'HARDLIGHT_CHROME': explicit, 'HARDLIGHT_EVIDENCE_DIR': ''}), \
             patch('shutil.which', return_value=system), \
             patch.object(Path, 'is_file', return_value=installed):
            try:
                Harness.setUpClass()
            except unittest.SkipTest as exc:
                if installed or explicit or system:
                    self.fail(str(exc))
                runtime.chromium.launch.assert_not_called()
                raise
        return runtime

    def test_installed_playwright_fallback_without_system_chrome(self):
        runtime = self.setup_browser()
        self.assertEqual(runtime.chromium.launch.call_args.kwargs['executable_path'],
                         '/installed/playwright/chrome')

    def test_missing_browsers_skip_without_launch(self):
        with self.assertRaisesRegex(unittest.SkipTest, 'no download attempted'):
            self.setup_browser(installed=False)

    def test_explicit_selection_precedes_system_and_playwright(self):
        runtime = self.setup_browser(explicit='/chosen/chrome', system='/system/chrome')
        self.assertEqual(runtime.chromium.launch.call_args.kwargs['executable_path'], '/chosen/chrome')

    def test_system_selection_precedes_playwright(self):
        runtime = self.setup_browser(system='/system/chrome')
        self.assertEqual(runtime.chromium.launch.call_args.kwargs['executable_path'], '/system/chrome')

    def test_setup_failure_stops_playwright(self):
        runtime = MagicMock()
        runtime.chromium.launch.side_effect = RuntimeError('launch failed')
        api = SimpleNamespace(sync_playwright=lambda: SimpleNamespace(start=lambda: runtime))
        class Harness(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                ChromeExamplesTests.setUpClass.__func__(cls)
        with patch.dict('sys.modules', {'playwright.sync_api': api}), \
             patch.dict(os.environ, {'HARDLIGHT_CHROME': '/chosen/chrome'}):
            with self.assertRaisesRegex(RuntimeError, 'launch failed'):
                try:
                    Harness.setUpClass()
                finally:
                    Harness.doClassCleanups()
        runtime.stop.assert_called_once()


@unittest.skipUnless(os.environ.get('HARDLIGHT_BROWSER_TESTS') == '1',
                     'Chrome checks not run: opt in with HARDLIGHT_BROWSER_TESTS=1')
class ChromeExamplesTests(unittest.TestCase):
    """Real local-file browser paths. No remote services, mocks or downloads."""

    @classmethod
    def setUpClass(cls):
        import shutil
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise unittest.SkipTest('Optional playwright package is not installed') from exc
        executable = os.environ.get('HARDLIGHT_CHROME') or shutil.which('google-chrome') or shutil.which('chromium')
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        if not executable:
            bundled = cls.playwright.chromium.executable_path
            if Path(bundled).is_file():
                executable = bundled
            else:
                raise unittest.SkipTest('An installed Chrome/Chromium is required; no download attempted')
        cls.browser = cls.playwright.chromium.launch(executable_path=executable, headless=True,
                                                    args=['--no-sandbox'])
        cls.addClassCleanup(cls.browser.close)
        cls.evidence = Path(os.environ['HARDLIGHT_EVIDENCE_DIR']) if os.environ.get('HARDLIGHT_EVIDENCE_DIR') else None
        if cls.evidence:
            cls.evidence.mkdir(parents=True, exist_ok=True)

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
        self.errors = []
        self.remote = []
        def guard(route):
            if route.request.url.startswith(('http:', 'https:')):
                self.remote.append(route.request.url)
                route.abort()
            else:
                route.continue_()
        self.context.route('**/*', guard)
        self.page = self.context.new_page()
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.on('console', lambda message: self.errors.append(message.text) if message.type == 'error' else None)

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [], 'Browser JavaScript/console errors')
        self.assertEqual(self.remote, [], 'Offline examples must not request remote resources')

    def open(self, name, fragment=''):
        self.page.goto((EXAMPLES / name).as_uri() + fragment)

    def assert_no_overflow(self):
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth'),
                        self.page.evaluate('({width:innerWidth,document:document.documentElement.scrollWidth})'))

    def capture(self, name):
        if self.evidence:
            self.page.screenshot(path=str(self.evidence / (name + '.png')), full_page=False)

    def test_00_initial_wide_narrow_reduced_keyboard(self):
        for name in ('index', 'editorial', 'workspace', 'expressive'):
            for mode, width, height in (('wide', 1440, 1000), ('narrow', 390, 844), ('reduced', 390, 844)):
                with self.subTest(page=name, mode=mode):
                    self.page.set_viewport_size({'width': width, 'height': height})
                    self.page.emulate_media(reduced_motion='reduce' if mode == 'reduced' else 'no-preference')
                    self.open(name + '.html')
                    self.page.wait_for_timeout(850 if name == 'expressive' and mode != 'reduced' else 20)
                    self.assert_no_overflow()
                    self.assertEqual(self.page.locator('h1').count(), 1)
                    self.assertTrue(self.page.locator('h1').is_visible())
                    self.assertTrue(self.page.evaluate('''() => {
                        const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);
                        return ids.length===new Set(ids).size;
                    }'''))
                    self.capture(name + '-initial-' + mode)
                    self.page.keyboard.press('Tab')
                    self.assertIn('skip', self.page.evaluate('document.activeElement.className'))
                    self.assertEqual(self.page.evaluate('getComputedStyle(document.activeElement).outlineStyle'), 'solid')
                    self.page.keyboard.press('Enter')
                    if name == 'expressive' and mode == 'reduced':
                        self.assertEqual(self.page.locator('.disc').evaluate('(e)=>getComputedStyle(e).animationName'), 'none')

    def test_editorial_search_escape_navigation_and_recovery(self):
        self.open('editorial.html')
        self.page.locator('#essay-search').fill('listening')
        self.assertEqual(self.page.locator('[data-passage]:visible').count(), 1)
        self.assertIn('1 of 3', self.page.locator('#search-state').inner_text())
        self.page.get_by_role('link', name='02 Learning to listen').click()
        self.assertTrue(self.page.url.endswith('#listening'))
        self.assertEqual(self.page.locator('#contents [aria-current]').get_attribute('href'), '#listening')
        self.page.locator('#essay-search').fill('<img src=x onerror=alert(1)>')
        self.assertEqual(self.page.locator('[data-passage]:visible').count(), 0)
        self.assertIn('No passages match', self.page.locator('#search-state').inner_text())
        self.assertEqual(self.page.locator('img').count(), 0)
        self.page.get_by_role('button', name='Clear', exact=True).click()
        self.assertEqual(self.page.locator('[data-passage]:visible').count(), 3)
        self.page.get_by_role('link', name='03 What we keep').click()
        self.page.go_back()
        self.assertTrue(self.page.url.endswith('#listening'))
        self.page.locator('#essay-search').fill('listening')
        self.page.locator('#listening').scroll_into_view_if_needed()
        self.capture('editorial-engaged-wide')
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.page.locator('#listening').scroll_into_view_if_needed()
        self.assert_no_overflow()
        self.capture('editorial-engaged-narrow')

    def test_workspace_back_restores_initial_selection(self):
        self.open('workspace.html')
        self.page.locator('a[href="#job-imprint"]').click()
        self.page.locator('#job-imprint').wait_for(state='visible')
        self.page.go_back()
        self.page.locator('#job-atlas').wait_for(state='visible', timeout=1000)
        self.assertEqual(self.page.locator('.job-link[aria-current]').get_attribute('href'), '#job-atlas')

    def test_workspace_long_note_remains_contained(self):
        self.page.set_viewport_size({'width':390,'height':844})
        self.open('workspace.html')
        self.page.locator('#atlas-note').fill('x' * 600)
        self.page.locator('#job-atlas').get_by_role('button', name='Apply to this session').click()
        self.assertEqual(self.page.locator('#job-atlas .saved-note').inner_text(), 'x' * 600)
        self.assert_no_overflow()

    def test_workspace_container_topology_and_platform_fallback(self):
        self.page.set_viewport_size({'width': 1440, 'height': 1000})
        self.open('workspace.html')
        queue = self.page.locator('.queue').bounding_box()
        inspector = self.page.locator('.inspector').bounding_box()
        self.assertGreater(inspector['x'], queue['x'] + queue['width'] - 2)
        self.page.locator('.main').evaluate("e => e.style.inlineSize = '540px'")
        queue = self.page.locator('.queue').bounding_box()
        inspector = self.page.locator('.inspector').bounding_box()
        self.assertGreaterEqual(inspector['y'], queue['y'] + queue['height'] - 2,
                                'A narrow embedded workbench must stack inside a wide viewport')
        self.page.locator('a[href="#job-imprint"]').click()
        self.page.locator('#job-imprint').wait_for(state='visible')
        self.assertTrue(self.page.locator('#job-imprint').is_visible())
        self.assertLess(self.page.locator('#job-imprint').bounding_box()['y'], 100,
                        'Selection must reach the jacket whenever container topology stacks')
        # Remove enhancement rules: test the real stylesheet's baseline, not an invented copy.
        self.open('workspace.html')
        self.page.evaluate('''() => {
            for (const sheet of document.styleSheets) {
                for (let i = sheet.cssRules.length - 1; i >= 0; i--) {
                    const rule = sheet.cssRules[i];
                    if (rule.cssText.startsWith('@container') || rule.cssText.startsWith('@supports')) {
                        sheet.deleteRule(i);
                    }
                }
            }
        }''')
        queue = self.page.locator('.queue').bounding_box()
        inspector = self.page.locator('.inspector').bounding_box()
        self.assertGreaterEqual(inspector['y'], queue['y'] + queue['height'] - 2)
        self.page.get_by_role('link', name='J—015 / Identity A useful imprint', exact=False).click()
        self.page.locator('#job-imprint').wait_for(state='visible')
        self.assertTrue(self.page.locator('#job-imprint').is_visible())
        self.assert_no_overflow()

    def test_workspace_reflow_text_preferences_and_rtl(self):
        for width in (320, 390, 768, 1440):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width': width, 'height': 1000})
                self.open('workspace.html')
                self.assert_no_overflow()
                original_size = self.page.locator('body').evaluate('(e) => parseFloat(getComputedStyle(e).fontSize)')
                self.page.locator('html').evaluate("e => e.style.fontSize = '200%'")
                self.assertGreaterEqual(self.page.locator('body').evaluate('(e) => parseFloat(getComputedStyle(e).fontSize)'), original_size * 1.95)
                self.assert_no_overflow()
                self.page.get_by_role('link', name='J—015 / Identity A useful imprint', exact=False).click()
                self.page.locator('#job-imprint').wait_for(state='visible')
                self.assertTrue(self.page.locator('#job-imprint').is_visible())
                self.page.locator('html').evaluate("e => e.dir = 'rtl'")
                self.assert_no_overflow()
                self.capture(f'workspace-large-text-rtl-{width}')
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.open('workspace.html')
        self.page.emulate_media(forced_colors='active', reduced_motion='reduce')
        self.page.locator('a[href="#job-imprint"]').click()
        self.page.locator('#job-imprint').wait_for(state='visible')
        link = self.page.locator('a[href="#job-imprint"]')
        self.assertNotEqual(link.evaluate('(e) => getComputedStyle(e).borderInlineStartStyle'), 'none')
        self.page.locator('#imprint-note').focus()
        self.page.keyboard.press('Tab')
        self.assertEqual(self.page.evaluate('document.activeElement.textContent'), 'Apply to this session')
        self.assertEqual(self.page.evaluate('getComputedStyle(document.activeElement).outlineStyle'), 'solid')
        self.capture('workspace-forced-colors')
        self.page.emulate_media(forced_colors='none', reduced_motion='no-preference')

    def test_workspace_mobile_link_reaches_selected_jacket(self):
        self.page.set_viewport_size({'width':390,'height':844})
        self.open('workspace.html')
        self.page.locator('a[href="#job-imprint"]').click()
        self.page.locator('#job-imprint').wait_for(state='visible')
        box = self.page.locator('#job-imprint').bounding_box()
        self.assertIsNotNone(box)
        assert box is not None
        self.assertLess(box['y'], 100,
                        'Selecting a previously hidden mobile jacket must reach the jacket, not stay at the list')
        self.assertEqual(self.page.evaluate('document.activeElement.id'), 'job-imprint')

    def test_workspace_select_edit_filter_history_and_reset(self):
        self.open('workspace.html')
        self.assertTrue(self.page.locator('#job-atlas').is_visible())
        self.page.locator('a[href="#job-imprint"]').click()
        self.page.locator('#job-imprint').wait_for(state='visible')
        self.assertTrue(self.page.locator('#job-imprint').is_visible())
        self.page.locator('a[href="#job-fold"]').click()
        self.page.locator('#job-fold').wait_for(state='visible')
        self.assertTrue(self.page.locator('#job-fold').is_visible())
        self.page.go_back()
        self.page.locator('#job-imprint').wait_for(state='visible')
        self.assertTrue(self.page.locator('#job-imprint').is_visible())
        self.assertEqual(self.page.locator('.job-link[aria-current]').get_attribute('href'), '#job-imprint')
        self.page.locator('#imprint-status').select_option(label='Ready for press')
        self.page.locator('#imprint-note').fill('<img src=x onerror=alert(1)> Check impression.')
        self.page.locator('#job-imprint').get_by_role('button', name='Apply to this session').click()
        self.assertEqual(self.page.locator('#job-imprint .current-status').inner_text(), 'Ready for press')
        self.assertIn('<img src=x', self.page.locator('#job-imprint .saved-note').inner_text())
        self.assertEqual(self.page.locator('#job-imprint img').count(), 0)
        self.assertIn('A useful imprint', self.page.locator('#change-log').inner_text())
        self.assertIn('Applied in this tab', self.page.locator('#job-imprint .session-state').inner_text())
        self.page.locator('#job-search').fill('nothing-matches')
        self.assertEqual(self.page.locator('.jobs > li:visible').count(), 0)
        self.assertTrue(self.page.locator('.empty').is_visible())
        self.page.get_by_role('button', name='Show all jobs', exact=True).click()
        self.assertEqual(self.page.locator('.jobs > li:visible').count(), 4)
        self.page.locator('#status-filter').select_option('Ready for press')
        self.assertEqual(self.page.locator('.jobs > li:visible').count(), 2)
        self.page.get_by_role('button', name='Reset', exact=True).click()
        self.page.evaluate('scrollTo(0,0)')
        self.capture('workspace-engaged-wide')
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.page.locator('#job-imprint').scroll_into_view_if_needed()
        self.assert_no_overflow()
        self.capture('workspace-engaged-narrow')
        self.page.reload()
        self.assertEqual(self.page.locator('#job-imprint .current-status').inner_text(), 'Needs review')
        self.assertIn('No changes yet', self.page.locator('#change-log').inner_text())
        self.open('workspace.html', '#job-proof')
        self.assertTrue(self.page.locator('#job-proof').is_visible())

    def test_expressive_program_keyboard_disclosure_and_history(self):
        self.open('expressive.html')
        self.assertEqual(self.page.locator('.topbar nav [aria-current]').count(), 0,
                         'The gallery link must not claim to be the current event section')
        self.page.get_by_role('link', name='Explore the program').click()
        self.page.locator('#medium').select_option('sound')
        self.assertEqual(self.page.locator('.event:visible').count(), 1)
        self.assertIn('1 work', self.page.locator('#program-state').inner_text())
        summary = self.page.locator('#work-low summary')
        summary.focus()
        self.page.keyboard.press('Enter')
        self.assertTrue(self.page.locator('#work-low').evaluate('(e)=>e.open'))
        self.assertTrue(self.page.get_by_text('Intervals for an empty hall').is_visible())
        self.page.locator('#program').scroll_into_view_if_needed()
        self.capture('expressive-engaged-wide')
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.page.locator('#program').scroll_into_view_if_needed()
        self.assert_no_overflow()
        self.capture('expressive-engaged-narrow')
        self.page.get_by_role('button', name='Show all', exact=True).click()
        self.assertEqual(self.page.locator('.event:visible').count(), 4)
        self.page.locator('.topbar').get_by_role('link', name='Visit notes').click()
        self.page.locator('.topbar').get_by_role('link', name='About', exact=True).click()
        self.page.go_back()
        self.assertTrue(self.page.url.endswith('#visit'))
        self.assertEqual(self.page.locator('.topbar nav [aria-current]').get_attribute('href'), '#visit')

    def test_mobile_navigation_follows_dom_order(self):
        self.page.set_viewport_size({'width':390,'height':844})
        for name, selector in (('workspace', '.sidebar a'), ('expressive', '.topbar a')):
            self.open(name + '.html')
            tops = self.page.locator(selector).evaluate_all('(links)=>links.map(e=>e.getBoundingClientRect().top)')
            self.assertEqual(tops, sorted(tops), name + ': navigation must not visually jump backward in DOM order')

    def test_no_javascript_keeps_complete_documents(self):
        context = self.browser.new_context(java_script_enabled=False, viewport={'width':390,'height':844})
        try:
            page = context.new_page()
            for name, selector, count in (('editorial', '[data-passage]', 3),
                                          ('workspace', '.jacket', 4),
                                          ('expressive', '.event', 4)):
                page.goto((EXAMPLES / (name + '.html')).as_uri())
                self.assertEqual(page.locator(selector + ':visible').count(), count)
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                self.assertEqual(page.locator('form:visible').count(), 0)
            page.locator('#work-low summary').click()
            self.assertTrue(page.get_by_text('Intervals for an empty hall').is_visible())
        finally:
            context.close()

    def test_gallery_real_destinations_and_returns(self):
        self.open('index.html')
        for name, filename in (('Intertidal', 'editorial.html'), ('Set', 'workspace.html'), ('Afterimage', 'expressive.html')):
            self.page.get_by_role('link', name=name, exact=False).first.click()
            self.assertTrue(self.page.url.endswith(filename))
            self.page.get_by_role('link', name='Back to the demo index').click()
            self.assertTrue(self.page.url.endswith('index.html'))


if __name__ == '__main__':
    unittest.main()
