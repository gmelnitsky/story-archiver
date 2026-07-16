// Run this in the Chrome DevTools console on the correspondent's the news site author page.
//
//   1. Be on the author's index page on the site you're archiving
//   2. ⌘⌥J to open the console
//   3. If Chrome says "pasting is blocked", type:  allow pasting  <Enter>  first
//   4. Paste this, hit Enter, and leave the tab in the foreground
//
// It clicks "load more" until her archive is exhausted, then downloads every story
// URL as urls.json. Pagination happens in your browser, as a normal reader —
// nothing automated touches the news site's disallowed /get/ endpoint.

(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const storyUrls = () => [
    ...new Set(
      [...document.querySelectorAll('a[href]')]
        .map((a) => a.href.split(/[?#]/)[0])
        // keep story permalinks (dated /YYYY/MM/DD/ paths) on the current site
        .filter((h) => /^https?:\/\/[^/]+\/\d{4}\/\d{2}\/\d{2}\/./.test(h))
    ),
  ];

  const loadMoreButton = () =>
    [...document.querySelectorAll('button, a')].find(
      (el) =>
        /load more|more stories/i.test(el.textContent || '') && el.offsetParent !== null
    );

  // --- sanity checks, so this can't fail silently the way the last run did ---
  const anchors = document.querySelectorAll('a[href]').length;
  const start = storyUrls().length;
  console.log(`page has ${anchors} links, ${start} of them stories`);

  if (!location.href.includes('/people/')) {
    console.error('You are not on the author page. Go to the author page and re-run.');
    return;
  }
  if (start === 0) {
    console.error('Found 0 story links. The page may not have finished loading — reload and re-run.');
    return;
  }

  let clicks = 0;
  let stalled = 0;

  while (stalled < 3) {
    const before = storyUrls().length;
    const btn = loadMoreButton();

    if (!btn) {
      console.log('%cNo "load more" button left — archive fully expanded.', 'color:#0a0');
      break;
    }

    btn.scrollIntoView({ block: 'center' });
    btn.click();
    clicks++;
    await sleep(1500); // pace it like a person clicking

    const after = storyUrls().length;
    stalled = after > before ? 0 : stalled + 1;
    console.log(`click ${clicks} → ${after} stories${stalled ? ` (no new ones ×${stalled})` : ''}`);
  }

  const urls = storyUrls();
  console.log(`%cDone. ${urls.length} unique stories after ${clicks} clicks.`,
    'color:#0a0;font-weight:bold;font-size:14px');

  if (urls.length === 0) {
    console.error('Collected nothing — do not use this file. Tell Claude what you see above.');
    return;
  }

  const blob = new Blob([JSON.stringify(urls, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'urls.json';
  a.click();
  console.log('%cSaved to ~/Downloads/urls.json', 'color:#0a0');
})();
