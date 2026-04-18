#!/usr/bin/env python3
"""
Dickies WS450H Size M Dashboard Generator

Fetches all color variants of the Heavyweight Heathered Short Sleeve Pocket
T-Shirt and writes a static HTML dashboard showing which colors have size M
in stock, with direct links to each product page.

Designed to run in GitHub Actions and deploy to GitHub Pages.
Output is written to site/index.html.
"""

import html
import json
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

# --- Configuration ------------------------------------------------------------

COLOR_CODES = [
    'bdh', 'bud', 'byd', 'cgh', 'cth', 'dth', 'eh2', 'fch', 'ghh', 'gsh',
    'ikh', 'j89', 'j90', 'k49', 'k51', 'l03', 'l06', 'l54', 'lsd', 'oih', 'rrh',
]
BASE_URL = ('https://www.dickies.com/en-us/products/'
            'heavyweight-heathered-short-sleeve-pocket-t-shirt-dkws450h')
TARGET_SIZE = 'M'
REGULAR_PRICE = 13.99
DISPLAY_TZ = ZoneInfo('America/Los_Angeles')

OUTPUT_FILE = Path(__file__).parent / 'site' / 'index.html'

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/120.0.0.0 Safari/537.36'),
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


# --- Fetching and parsing -----------------------------------------------------

def fetch_product(code, max_attempts=3):
    url = f'{BASE_URL}{code}'
    last_err = None
    for attempt in range(max_attempts):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code in (429, 500, 502, 503, 504):
                # Transient; back off and retry
                last_err = f'HTTP {resp.status_code}'
                time.sleep((2 ** attempt) + random.uniform(0, 1))
                continue
            resp.raise_for_status()
            break
        except requests.RequestException as e:
            last_err = str(e)
            time.sleep((2 ** attempt) + random.uniform(0, 1))
    else:
        return {'code': code, 'url': url, 'error': f'fetch: {last_err}'}

    m = re.search(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        resp.text, re.DOTALL)
    if not m:
        return {'code': code, 'url': url, 'error': 'no JSON-LD block'}

    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        return {'code': code, 'url': url, 'error': f'json parse: {e}'}

    pg = next((x for x in data.get('@graph', [])
               if x.get('@type') == 'ProductGroup'), None)
    if not pg or not pg.get('hasVariant'):
        return {'code': code, 'url': url, 'error': 'no product data'}

    raw_color = pg['hasVariant'][0].get('color', code.upper())
    color = re.sub(r'\s*\([^)]*\)\s*$', '', raw_color).strip()
    image = pg['hasVariant'][0].get('image', '')
    if '_small' in image:
        image = image.replace('_small', '_400x')

    variants = [{
        'size': v.get('size'),
        'price': float(v.get('offers', {}).get('price', 0) or 0),
        'in_stock': 'InStock' in v.get('offers', {}).get('availability', ''),
    } for v in pg['hasVariant']]

    return {'code': code, 'url': url, 'color': color, 'image': image,
            'variants': variants}


# --- HTML rendering -----------------------------------------------------------

CSS = """
:root {
  --bg: #0a0a0b;
  --bg-panel: #141416;
  --bg-card: #17171a;
  --border: #26262b;
  --border-sale: rgba(245, 158, 11, 0.45);
  --text: #e8e8ea;
  --text-dim: #7a7a82;
  --amber: #f59e0b;
  --amber-light: #fbbf24;
  --amber-soft: rgba(245, 158, 11, 0.12);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 14px;
  line-height: 1.5;
  padding: 20px 16px 48px;
  min-height: 100vh;
}
.wrap { max-width: 720px; margin: 0 auto; }

header {
  border-bottom: 1px solid var(--border);
  padding-bottom: 20px;
  margin-bottom: 24px;
}
.eyebrow {
  font-size: 11px;
  letter-spacing: 0.25em;
  color: var(--amber);
  text-transform: uppercase;
  font-weight: 700;
  margin-bottom: 10px;
}
h1 {
  font-size: 22px;
  font-weight: 700;
  color: #fafafa;
  letter-spacing: -0.01em;
  margin-bottom: 4px;
  line-height: 1.2;
}
.subtitle {
  font-size: 13px;
  color: var(--text-dim);
  margin-bottom: 14px;
}
.meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-dim);
  letter-spacing: 0.05em;
}
.meta strong { color: var(--text); font-weight: 500; }

.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 28px;
}
.stat {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  padding: 14px 12px;
}
.stat.hit { border-color: var(--border-sale); background: var(--amber-soft); }
.stat-value {
  font-size: 32px;
  font-weight: 700;
  line-height: 1;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}
.stat.hit .stat-value { color: var(--amber); }
.stat-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--text-dim);
  margin-top: 8px;
  font-weight: 500;
  line-height: 1.3;
}

.section-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  color: var(--text-dim);
  margin: 24px 0 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
}
.section-title::before { content: '+ '; color: var(--amber); }
.section-title .count { color: var(--text); }

.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  display: grid;
  grid-template-columns: 80px 1fr auto;
  gap: 14px;
  padding: 12px;
  margin-bottom: 8px;
  align-items: center;
}
.card.sale { border-color: var(--border-sale); }
.card img {
  width: 80px;
  height: 80px;
  background: #1f1f23;
  object-fit: cover;
  display: block;
}
.card-info { min-width: 0; }
.card-color {
  font-size: 15px;
  font-weight: 700;
  color: #fafafa;
  margin-bottom: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-code {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  color: var(--text-dim);
  font-weight: 500;
}
.card-price {
  margin-top: 8px;
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.price-current {
  font-size: 18px;
  font-weight: 700;
  color: var(--amber-light);
  font-variant-numeric: tabular-nums;
}
.price-regular {
  font-size: 12px;
  text-decoration: line-through;
  color: var(--text-dim);
  font-variant-numeric: tabular-nums;
}
.savings {
  font-size: 10px;
  font-weight: 700;
  background: var(--amber-soft);
  color: var(--amber);
  padding: 2px 6px;
  letter-spacing: 0.05em;
}

.buy-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--amber);
  color: #0a0a0b;
  padding: 12px 16px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  text-decoration: none;
  white-space: nowrap;
  transition: background 0.12s ease;
  font-family: inherit;
}
.buy-btn:hover, .buy-btn:active { background: var(--amber-light); }

.oos-card { opacity: 0.55; }
.oos-card .buy-btn {
  background: transparent;
  color: var(--text-dim);
  border: 1px solid var(--border);
}
.oos-tag {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  color: #ef4444;
  font-weight: 700;
  margin-top: 6px;
}

.empty {
  padding: 32px 16px;
  text-align: center;
  color: var(--text-dim);
  font-size: 13px;
  border: 1px dashed var(--border);
  background: var(--bg-panel);
}

details {
  margin-top: 20px;
  border-top: 1px solid var(--border);
  padding-top: 16px;
}
details summary {
  cursor: pointer;
  font-size: 11px;
  color: var(--text-dim);
  padding: 4px 0;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  user-select: none;
  font-weight: 700;
  list-style: none;
}
details summary::-webkit-details-marker { display: none; }
details summary::before { content: '▸ '; color: var(--amber); }
details[open] summary::before { content: '▾ '; }
details summary:hover { color: var(--text); }
details > *:not(summary) { margin-top: 12px; }

footer {
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
  font-size: 11px;
  color: var(--text-dim);
  text-align: center;
  line-height: 1.8;
  letter-spacing: 0.05em;
}

.errors {
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  padding: 10px 12px;
  font-size: 11px;
  margin-bottom: 16px;
}

.card img { cursor: zoom-in; transition: opacity 0.15s; }
.card img:hover { opacity: 0.85; }

.lightbox {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.94);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  z-index: 1000;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.18s ease;
  cursor: zoom-out;
  padding: 40px 20px;
  -webkit-tap-highlight-color: transparent;
}
.lightbox.open { opacity: 1; pointer-events: auto; }
.lightbox img {
  max-width: 100%;
  max-height: 75vh;
  object-fit: contain;
  border: 1px solid var(--border);
  background: var(--bg-panel);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
}
.lightbox-caption {
  text-align: center;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  color: var(--text-dim);
  font-weight: 500;
  max-width: 90%;
}
.lightbox-caption strong {
  display: block;
  color: var(--amber);
  font-size: 14px;
  letter-spacing: 0.15em;
  margin-bottom: 4px;
  font-weight: 700;
}
.lightbox-close {
  position: absolute;
  top: 16px;
  right: 16px;
  font-size: 24px;
  color: var(--text-dim);
  line-height: 1;
}

@media (max-width: 520px) {
  .card { grid-template-columns: 60px 1fr; gap: 12px; }
  .card img { width: 60px; height: 60px; }
  .buy-btn { grid-column: 1 / -1; width: 100%; padding: 14px; }
  .stat-value { font-size: 26px; }
}
"""


def get_m_price(r):
    return next((v['price'] for v in r['variants'] if v['size'] == TARGET_SIZE), 999)


def render_card(item, on_sale, in_stock):
    med = next((v for v in item['variants'] if v['size'] == TARGET_SIZE), None)
    if not med:
        return ''

    classes = ['card']
    if on_sale and in_stock:
        classes.append('sale')
    if not in_stock:
        classes.append('oos-card')

    savings_pct = 0
    if med['price'] < REGULAR_PRICE:
        savings_pct = round((REGULAR_PRICE - med['price']) / REGULAR_PRICE * 100)

    color_esc = html.escape(item['color'])
    code_esc = html.escape(item['code'].upper())
    url_esc = html.escape(item['url'], quote=True)
    img_esc = html.escape(item.get('image', ''), quote=True)
    # Larger image for the lightbox — swap the card's _400x size suffix for _1024x
    img_large = item.get('image', '').replace('_400x', '_1024x')
    img_large_esc = html.escape(img_large, quote=True)

    price_block = f'<span class="price-current">${med["price"]:.2f}</span>'
    if med['price'] < REGULAR_PRICE:
        price_block += f'<span class="price-regular">${REGULAR_PRICE:.2f}</span>'
        price_block += f'<span class="savings">−{savings_pct}%</span>'

    oos_tag = '<div class="oos-tag">Out of stock</div>' if not in_stock else ''
    btn_label = 'Shop Color' if in_stock else 'View Page'

    return f'''
    <div class="{' '.join(classes)}">
      <img src="{img_esc}" data-large="{img_large_esc}" data-color="{color_esc}" data-code="{code_esc}" alt="{color_esc}" loading="lazy">
      <div class="card-info">
        <div class="card-color">{color_esc}</div>
        <div class="card-code">{code_esc}</div>
        <div class="card-price">{price_block}</div>
        {oos_tag}
      </div>
      <a class="buy-btn" href="{url_esc}" target="_blank" rel="noopener">{btn_label} →</a>
    </div>'''


def render_html(results, timestamp_pacific):
    successful = [r for r in results if 'error' not in r]
    errored = [r for r in results if 'error' in r]

    in_stock_items = []
    oos_items = []
    for r in successful:
        med = next((v for v in r['variants'] if v['size'] == TARGET_SIZE), None)
        if not med:
            continue
        if med['in_stock']:
            in_stock_items.append(r)
        else:
            oos_items.append(r)

    in_stock_items.sort(key=get_m_price)
    oos_items.sort(key=lambda r: r['color'])

    sale_in_stock_count = sum(1 for r in in_stock_items if get_m_price(r) < REGULAR_PRICE)

    if in_stock_items:
        in_stock_html = ''.join(
            render_card(r, on_sale=(get_m_price(r) < REGULAR_PRICE), in_stock=True)
            for r in in_stock_items
        )
    else:
        in_stock_html = '<div class="empty">No colors currently have size M in stock.</div>'

    if oos_items:
        oos_html = ''.join(
            render_card(r, on_sale=(get_m_price(r) < REGULAR_PRICE), in_stock=False)
            for r in oos_items
        )
    else:
        oos_html = '<div class="empty">None — every color has M in stock right now!</div>'

    errors_html = ''
    if errored:
        err_list = ', '.join(html.escape(e['code'].upper()) for e in errored)
        errors_html = f'<div class="errors"><strong>{len(errored)} fetch error(s):</strong> {err_list}</div>'

    ts_short = timestamp_pacific.strftime('%b %d, %Y · %I:%M %p %Z')
    ts_iso = timestamp_pacific.isoformat()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0a0a0b">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>Dickies WS450H · Size M Stock</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="eyebrow">Dickies · WS450H</div>
    <h1>Heavyweight Heathered Tee</h1>
    <div class="subtitle">Size M availability · {len(COLOR_CODES)} colors</div>
    <div class="meta">
      <span>Updated <strong><time datetime="{ts_iso}">{ts_short}</time></strong></span>
      <span><strong>{len(successful)}</strong>/{len(COLOR_CODES)} checked</span>
    </div>
  </header>

  <div class="stats">
    <div class="stat hit">
      <div class="stat-value">{sale_in_stock_count}</div>
      <div class="stat-label">On sale<br>M in stock</div>
    </div>
    <div class="stat">
      <div class="stat-value">{len(in_stock_items)}</div>
      <div class="stat-label">Total<br>M in stock</div>
    </div>
    <div class="stat">
      <div class="stat-value">{len(oos_items)}</div>
      <div class="stat-label">Out of stock<br>in M</div>
    </div>
  </div>

  {errors_html}

  <div class="section-title">In stock <span class="count">({len(in_stock_items)})</span></div>
  {in_stock_html}

  <details>
    <summary>Out of stock ({len(oos_items)})</summary>
    {oos_html}
  </details>

  <footer>
    <div>Auto-updated daily · Regular price baseline ${REGULAR_PRICE:.2f}</div>
    <div>Data: dickies.com JSON-LD</div>
  </footer>
</div>

<div id="lightbox" class="lightbox" role="dialog" aria-modal="true" aria-hidden="true">
  <div class="lightbox-close" aria-hidden="true">×</div>
  <img src="" alt="">
  <div class="lightbox-caption"></div>
</div>

<script>
(function() {{
  const lb = document.getElementById('lightbox');
  const lbImg = lb.querySelector('img');
  const lbCaption = lb.querySelector('.lightbox-caption');

  function open(img) {{
    lbImg.src = img.dataset.large || img.src;
    lbImg.alt = img.alt;
    lbCaption.innerHTML = '<strong>' + img.dataset.color + '</strong>' + (img.dataset.code || '');
    lb.classList.add('open');
    lb.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }}
  function close() {{
    lb.classList.remove('open');
    lb.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    // Clear src after animation ends to free memory
    setTimeout(() => {{ if (!lb.classList.contains('open')) lbImg.src = ''; }}, 300);
  }}

  document.querySelectorAll('.card img').forEach(img => {{
    img.addEventListener('click', () => open(img));
  }});
  lb.addEventListener('click', close);
  document.addEventListener('keydown', e => {{
    if (e.key === 'Escape' && lb.classList.contains('open')) close();
  }});
}})();
</script>
</body>
</html>
'''


# --- Main ---------------------------------------------------------------------

def main():
    print(f'Fetching {len(COLOR_CODES)} color variants in parallel...')
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(fetch_product, COLOR_CODES))

    in_stock_m, oos_m, errs = 0, 0, 0
    for r in results:
        if 'error' in r:
            print(f'  {r["code"]}: ERROR - {r["error"]}')
            errs += 1
            continue
        med = next((v for v in r['variants'] if v['size'] == TARGET_SIZE), None)
        if med and med['in_stock']:
            in_stock_m += 1
            tag = f'${med["price"]:.2f}' + (' SALE' if med['price'] < REGULAR_PRICE else '')
            print(f'  {r["code"]} {r["color"]:30s} M IN STOCK {tag}')
        else:
            oos_m += 1

    print(f'\n{in_stock_m} in stock · {oos_m} out · {errs} errors')

    now_pacific = datetime.now(DISPLAY_TZ)
    page = render_html(results, now_pacific)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(page, encoding='utf-8')
    print(f'Wrote {OUTPUT_FILE} ({len(page):,} bytes)')

    if errs > len(COLOR_CODES) // 2:
        sys.exit(1)


if __name__ == '__main__':
    main()



if __name__ == '__main__':
    main()
