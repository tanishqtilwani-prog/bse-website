"""
add_calendar.py — replaces the News tab with a Calendar tab in index.html.

Run on VM1:
    cd /home/ubuntu/bse-website
    python3 add_calendar.py

Makes a backup at index.html.bak before touching anything.
"""

import shutil
import sys

PATH = "index.html"

with open(PATH, "r", encoding="utf-8") as f:
    html = f.read()

shutil.copy(PATH, PATH + ".bak")
print("Backup written to index.html.bak")

steps = 0


def swap(old, new, label):
    """Replace old with new exactly once, or abort."""
    global html, steps
    if old not in html:
        print(f"\nFAILED at: {label}")
        print("Could not find this text:\n---")
        print(old[:300])
        print("---\nNothing was written. index.html is unchanged.")
        sys.exit(1)
    html = html.replace(old, new, 1)
    steps += 1
    print(f"  {steps}. {label}")


# ─────────────────────────────────────────────
# 1. BOTTOM NAV : News  ->  Calendar
# ─────────────────────────────────────────────
swap(
    """  <button class="nav-item" data-page="news" onclick="switchPage('news',this)">
    <span class="nav-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/></svg></span><span>News</span>
  </button>""",
    """  <button class="nav-item" data-page="cal" onclick="switchPage('cal',this)">
    <span class="nav-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg></span><span>Calendar</span>
  </button>""",
    "bottom nav -> Calendar",
)

# ─────────────────────────────────────────────
# 2. SIDE MENU : News  ->  Calendar
# ─────────────────────────────────────────────
swap(
    """    <button onclick="switchPage('news',document.querySelector('[data-page=news]'));closeMenu()" style="text-align:left;padding:10px 12px;border-radius:8px;border:none;background:none;cursor:pointer;font-size:14px;color:var(--text);font-family:'Inter',sans-serif">📰 News</button>""",
    """    <button onclick="switchPage('cal',document.querySelector('[data-page=cal]'));closeMenu()" style="text-align:left;padding:10px 12px;border-radius:8px;border:none;background:none;cursor:pointer;font-size:14px;color:var(--text);font-family:'Inter',sans-serif">🗓 Calendar</button>""",
    "side menu -> Calendar",
)

# ─────────────────────────────────────────────
# 3. PAGE BODY : news container -> calendar
# ─────────────────────────────────────────────
swap(
    """<!-- ══ NEWS PAGE ══ -->
<div class="page" id="page-news">
  <div id="news-container" style="padding-top:12px">
    <div style="text-align:center;padding:40px;color:var(--muted)">Loading news...</div>
  </div>
</div>""",
    """<!-- ══ CALENDAR PAGE ══ -->
<div class="page" id="page-cal">
  <div class="cal-wrap">
    <div class="cal-head">
      <button class="cal-nav-btn" onclick="calShift(-1)" aria-label="Previous month">&#8249;</button>
      <div class="cal-title" id="cal-title">&nbsp;</div>
      <button class="cal-nav-btn" onclick="calShift(1)" aria-label="Next month">&#8250;</button>
      <button class="cal-today-btn" onclick="calToday()">Today</button>
    </div>
    <div class="cal-dow"><span>S</span><span>M</span><span>T</span><span>W</span><span>T</span><span>F</span><span>S</span></div>
    <div class="cal-grid" id="cal-grid"></div>
    <div class="cal-legend" id="cal-legend"></div>
  </div>
  <div class="cal-day-panel" id="cal-day-panel"></div>
</div>""",
    "calendar page markup",
)

# ─────────────────────────────────────────────
# 4. CSS
# ─────────────────────────────────────────────
swap(
    "/* ── FUNDAMENTALS MODAL ── */",
    """/* ── CALENDAR TAB ── */
.cal-wrap{max-width:680px;margin:0 auto;padding:8px 12px 0}
.cal-head{display:flex;align-items:center;gap:6px;padding:10px 4px 14px}
.cal-title{font-family:'Syne',sans-serif;font-weight:800;font-size:20px;letter-spacing:-.4px;flex:1;text-align:left;margin-left:2px}
.cal-nav-btn{width:32px;height:32px;border:none;background:none;color:var(--muted);font-size:22px;line-height:1;cursor:pointer;border-radius:50%;display:flex;align-items:center;justify-content:center;transition:background .15s}
.cal-nav-btn:hover{background:var(--surface);color:var(--text)}
.cal-today-btn{border:1px solid var(--border);background:var(--surface);color:var(--text);border-radius:20px;padding:5px 13px;font-size:12px;font-weight:500;cursor:pointer;font-family:'Inter',sans-serif}
.cal-dow{display:grid;grid-template-columns:repeat(7,1fr);text-align:center;font-size:11px;font-weight:600;color:var(--muted);letter-spacing:.5px;padding-bottom:6px}
.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:2px}
.cal-cell{aspect-ratio:1/1;display:flex;flex-direction:column;align-items:center;justify-content:flex-start;padding-top:5px;gap:3px;border:none;background:none;cursor:pointer;border-radius:10px;font-family:'Inter',sans-serif;transition:background .12s}
.cal-cell:hover{background:var(--surface)}
.cal-cell.empty{visibility:hidden;cursor:default}
.cal-num{font-size:14px;font-weight:500;color:var(--text);width:28px;height:28px;display:flex;align-items:center;justify-content:center;border-radius:50%;line-height:1}
.cal-cell.other .cal-num{color:var(--muted);opacity:.45}
.cal-cell.today .cal-num{background:var(--red);color:#fff;font-weight:700}
.cal-cell.sel{background:var(--surface)}
.cal-cell.sel .cal-num{outline:2px solid var(--text);outline-offset:-2px}
.cal-cell.today.sel .cal-num{outline-color:var(--red)}
.cal-dots{display:flex;gap:2.5px;height:6px;align-items:center;flex-wrap:wrap;justify-content:center;max-width:90%}
.cal-dot{width:5px;height:5px;border-radius:50%;flex-shrink:0}
.cal-legend{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;padding:16px 4px 4px;border-top:1px solid var(--border);margin-top:14px}
.cal-leg-item{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--muted)}
.cal-day-panel{max-width:680px;margin:0 auto;padding:6px 16px 0}
.cal-day-title{font-family:'Syne',sans-serif;font-weight:700;font-size:15px;padding:14px 2px 10px}
.cal-group{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:8px;overflow:hidden}
.cal-group-head{display:flex;align-items:center;gap:9px;padding:12px 14px;cursor:pointer;user-select:none}
.cal-group-head:hover{background:var(--surface)}
.cal-group-name{flex:1;font-size:13px;font-weight:600;color:var(--text)}
.cal-group-count{font-size:11px;font-family:'JetBrains Mono',monospace;color:var(--muted);background:var(--tag-bg);border-radius:20px;padding:2px 9px}
.cal-chev{font-size:11px;color:var(--muted);transition:transform .18s;width:12px;text-align:center}
.cal-group.open .cal-chev{transform:rotate(90deg)}
.cal-group-body{display:none;border-top:1px solid var(--border)}
.cal-group.open .cal-group-body{display:block}
.cal-item{padding:10px 14px 10px 34px;border-bottom:1px solid var(--border)}
.cal-item:last-child{border-bottom:none}
.cal-item-name{font-size:13px;font-weight:500;color:var(--text);line-height:1.35}
.cal-item-sub{font-size:11px;color:var(--muted);margin-top:3px;line-height:1.4}
.cal-empty{text-align:center;padding:30px 20px;color:var(--muted);font-size:13px}
.cal-loading{text-align:center;padding:40px 20px;color:var(--muted);font-size:13px}

/* ── FUNDAMENTALS MODAL ── */""",
    "calendar CSS",
)

# ─────────────────────────────────────────────
# 5. JS : replace loadNews() with the calendar engine
# ─────────────────────────────────────────────
OLD_NEWS_JS_START = "// ── NEWS TAB ──"
OLD_NEWS_JS_END = "// ── FUNDAMENTALS ──"

i = html.find(OLD_NEWS_JS_START)
j = html.find(OLD_NEWS_JS_END)
if i == -1 or j == -1 or j < i:
    print("\nFAILED at: news JS block")
    print("Could not locate the loadNews() section. Nothing written.")
    sys.exit(1)

CAL_JS = r"""// ── CALENDAR TAB ──
var CAL_TYPES = {
  result:   { label: 'Results',      color: '#d97706' },
  dividend: { label: 'Dividend',     color: '#16a34a' },
  bonus:    { label: 'Bonus',        color: '#3b82f6' },
  rights:   { label: 'Rights',       color: '#a855f7' },
  split:    { label: 'Split',        color: '#14b8a6' },
  buyback:  { label: 'Buyback',      color: '#ec4899' },
  listing:  { label: 'New listing',  color: '#f97316' },
  corp_action: { label: 'Other',     color: '#64748b' }
};
var CAL_ORDER = ['result','listing','bonus','rights','split','buyback','dividend','corp_action'];
var MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];

var _calCursor = new Date();          // month being viewed
var _calSelected = null;              // 'YYYY-MM-DD'
var _calData = {};                    // 'YYYY-MM-DD' -> [events]
var _calMonthLoaded = '';             // 'YYYY-MM' already fetched
var _calOpenGroups = {};              // remembers which groups user expanded

function calKey(d) {
  return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
}

function calShift(n) {
  _calCursor = new Date(_calCursor.getFullYear(), _calCursor.getMonth() + n, 1);
  _calSelected = null;
  loadCalendar();
}

function calToday() {
  var t = new Date();
  _calCursor = new Date(t.getFullYear(), t.getMonth(), 1);
  _calSelected = calKey(t);
  loadCalendar();
}

function loadCalendar() {
  var ym = _calCursor.getFullYear() + '-' + String(_calCursor.getMonth()+1).padStart(2,'0');
  document.getElementById('cal-title').textContent = MONTHS[_calCursor.getMonth()] + ' ' + _calCursor.getFullYear();

  if (_calMonthLoaded === ym) { renderCalGrid(); return; }

  document.getElementById('cal-day-panel').innerHTML = '<div class="cal-loading">Loading events…</div>';

  // pull a little either side so leading/trailing grid days have dots too
  var from = new Date(_calCursor.getFullYear(), _calCursor.getMonth(), -7);
  var to   = new Date(_calCursor.getFullYear(), _calCursor.getMonth()+1, 8);

  var url = SUPABASE_URL + '/rest/v1/calendar_events?select=event_date,event_type,company_name,scrip_code,details'
          + '&event_date=gte.' + calKey(from)
          + '&event_date=lte.' + calKey(to)
          + '&order=event_date.asc,company_name.asc&limit=3000';

  fetch(url, {headers:{'apikey':SUPABASE_KEY,'Authorization':'Bearer '+SUPABASE_KEY}})
    .then(function(r){ return r.json(); })
    .then(function(rows){
      _calData = {};
      (rows || []).forEach(function(e){
        if (!_calData[e.event_date]) _calData[e.event_date] = [];
        _calData[e.event_date].push(e);
      });
      _calMonthLoaded = ym;
      if (!_calSelected) {
        var t = calKey(new Date());
        _calSelected = (_calData[t] || _calCursor.getMonth() === new Date().getMonth()) ? t : null;
      }
      renderCalGrid();
    })
    .catch(function(){
      document.getElementById('cal-day-panel').innerHTML = '<div class="cal-empty">Could not load calendar.</div>';
    });
}

function renderCalGrid() {
  var y = _calCursor.getFullYear(), m = _calCursor.getMonth();
  var first = new Date(y, m, 1);
  var start = new Date(y, m, 1 - first.getDay());   // back up to Sunday
  var todayKey = calKey(new Date());
  var html = '';

  for (var i = 0; i < 42; i++) {
    var d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
    var k = calKey(d);
    var evs = _calData[k] || [];

    // trim trailing all-empty week
    if (i >= 35 && d.getMonth() !== m) continue;

    var cls = 'cal-cell';
    if (d.getMonth() !== m) cls += ' other';
    if (k === todayKey) cls += ' today';
    if (k === _calSelected) cls += ' sel';

    var types = [];
    evs.forEach(function(e){ if (types.indexOf(e.event_type) === -1) types.push(e.event_type); });
    types.sort(function(a,b){ return CAL_ORDER.indexOf(a) - CAL_ORDER.indexOf(b); });

    var dots = types.slice(0,4).map(function(t){
      var c = (CAL_TYPES[t] || CAL_TYPES.corp_action).color;
      return '<span class="cal-dot" style="background:' + c + '"></span>';
    }).join('');

    html += '<button class="' + cls + '" onclick="calSelect(\'' + k + '\')">'
          + '<span class="cal-num">' + d.getDate() + '</span>'
          + '<span class="cal-dots">' + dots + '</span>'
          + '</button>';
  }
  document.getElementById('cal-grid').innerHTML = html;

  // legend — only types present this month
  var present = {};
  Object.keys(_calData).forEach(function(k){
    if (k.slice(0,7) === y + '-' + String(m+1).padStart(2,'0')) {
      _calData[k].forEach(function(e){ present[e.event_type] = true; });
    }
  });
  document.getElementById('cal-legend').innerHTML = CAL_ORDER
    .filter(function(t){ return present[t]; })
    .map(function(t){
      var c = CAL_TYPES[t] || CAL_TYPES.corp_action;
      return '<span class="cal-leg-item"><span class="cal-dot" style="background:'+c.color+'"></span>'+c.label+'</span>';
    }).join('');

  renderCalDay();
}

function calSelect(k) {
  _calSelected = k;
  _calOpenGroups = {};
  renderCalGrid();
  var p = document.getElementById('cal-day-panel');
  if (p) p.scrollIntoView({behavior:'smooth', block:'nearest'});
}

function calGroupToggle(t) {
  _calOpenGroups[t] = !_calOpenGroups[t];
  var el = document.getElementById('calg-' + t);
  if (el) el.classList.toggle('open');
}

function renderCalDay() {
  var el = document.getElementById('cal-day-panel');
  if (!_calSelected) {
    el.innerHTML = '<div class="cal-empty">Tap a date to see its events.</div>';
    return;
  }

  var parts = _calSelected.split('-');
  var d = new Date(+parts[0], +parts[1]-1, +parts[2]);
  var heading = d.toLocaleDateString('en-IN', {weekday:'long', day:'numeric', month:'long'});
  var evs = _calData[_calSelected] || [];

  if (!evs.length) {
    el.innerHTML = '<div class="cal-day-title">' + heading + '</div>'
                 + '<div class="cal-empty">No corporate events on this date.</div>';
    return;
  }

  var groups = {};
  evs.forEach(function(e){
    var t = CAL_TYPES[e.event_type] ? e.event_type : 'corp_action';
    (groups[t] = groups[t] || []).push(e);
  });

  var html = '<div class="cal-day-title">' + heading + '</div>';

  CAL_ORDER.forEach(function(t){
    var list = groups[t];
    if (!list || !list.length) return;
    var meta = CAL_TYPES[t];

    // small groups start open, big ones collapsed
    var open = (_calOpenGroups[t] !== undefined) ? _calOpenGroups[t] : (list.length <= 4);

    html += '<div class="cal-group' + (open ? ' open' : '') + '" id="calg-' + t + '">'
          + '<div class="cal-group-head" onclick="calGroupToggle(\'' + t + '\')">'
          +   '<span class="cal-dot" style="background:' + meta.color + '"></span>'
          +   '<span class="cal-group-name">' + meta.label + '</span>'
          +   '<span class="cal-group-count">' + list.length + '</span>'
          +   '<span class="cal-chev">&#9654;</span>'
          + '</div>'
          + '<div class="cal-group-body">';

    list.forEach(function(e){
      var sub = e.details || '';
      html += '<div class="cal-item">'
            +   '<div class="cal-item-name">' + (e.company_name || '') + '</div>'
            +   (sub ? '<div class="cal-item-sub">' + sub + '</div>' : '')
            + '</div>';
    });

    html += '</div></div>';
  });

  el.innerHTML = html;
}

"""

html = html[:i] + CAL_JS + html[j:]
steps += 1
print(f"  {steps}. calendar JS (replaced loadNews)")

# ─────────────────────────────────────────────
# 6. Hook the tab switch
# ─────────────────────────────────────────────
swap(
    """// ── PATCH switchPage TO LOAD NEWS ──
var _origSwitchPage = switchPage;
switchPage = function(name, btn) {
  _origSwitchPage(name, btn);
  if (name === 'news') loadNews();
};""",
    """// ── PATCH switchPage TO LOAD CALENDAR ──
var _origSwitchPage = switchPage;
switchPage = function(name, btn) {
  _origSwitchPage(name, btn);
  if (name === 'cal') loadCalendar();
};""",
    "switchPage hook",
)

# ─────────────────────────────────────────────
# 7. Fix broken quotes in fundSearchSuggest
# ─────────────────────────────────────────────
BAD = """    return '<div onclick="loadFundamentals(\\"' + c.isin + '\\",\\"' + c.company_name + '\\")" style="padding:8px 12px;cursor:pointer;border-radius:8px;font-size:13px;background:var(--surface);margin-bottom:4px">' + c.company_name + '</div>';"""
GOOD = """    return '<div onclick="loadFundamentals(&quot;' + c.isin + '&quot;,&quot;' + c.company_name.replace(/"/g,'') + '&quot;)" style="padding:8px 12px;cursor:pointer;border-radius:8px;font-size:13px;background:var(--surface);margin-bottom:4px">' + c.company_name + '</div>';"""
if BAD in html:
    html = html.replace(BAD, GOOD, 1)
    steps += 1
    print(f"  {steps}. fixed fundSearchSuggest quotes")
else:
    print("  -  fundSearchSuggest already fine (skipped)")

with open(PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\nDone — {steps} changes written to index.html")
print("If the site misbehaves:  cp index.html.bak index.html")
