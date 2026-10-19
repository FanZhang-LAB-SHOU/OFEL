// Exercise the actual shared navigation at phone and desktop widths.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const script = fs.readFileSync(path.join(__dirname, '../script.js'), 'utf8');
const navigationCode = script.slice(script.indexOf('const menuButton ='), script.indexOf('\nfunction initNewsFilters'));
function fixture(width = 390) {
  const listeners = {}, mediaListeners = {}, bodyClasses = new Set(), navClasses = new Set();
  const control = () => ({attrs: {}, events: {}, focused: false,
    setAttribute(key, value) { this.attrs[key] = value; },
    getAttribute(key) { return this.attrs[key]; },
    addEventListener(type, fn) { this.events[type] = fn; },
    focus() { this.focused = true; }});
  const toggle = control(); toggle.setAttribute('aria-expanded', 'false');
  const groups = ['people', 'research'].map(name => {
    const button = control(), submenu = {hidden: true};
    button.setAttribute('aria-expanded', 'false');
    return {name, button, submenu,
      querySelector(s) { return s === '.nav-dropdown-toggle' ? button : submenu; },
      querySelectorAll() { return []; }};
  });
  const link = control(); link.href = 'https://example.org/OFEL/members/';
  const nav = {classList: {toggle(name, on) { on ? navClasses.add(name) : navClasses.delete(name); }},
    querySelectorAll(s) { return s === '.nav-group' ? groups : s === 'a' ? [link] : []; }};
  const body = {dataset: {page: 'index'}, classList: {toggle(name, on) { on ? bodyClasses.add(name) : bodyClasses.delete(name); }}};
  const context = {URL, location: {pathname: '/OFEL/'},
    document: {body, querySelector(s) { return s === '.menu-toggle' ? toggle : nav; },
      addEventListener(type, fn) { listeners[type] = fn; }},
    window: {matchMedia(query) { return {matches: query.includes('max-width') ? width <= 760 : width >= 761,
      addEventListener(type, fn) { mediaListeners[query] = fn; }}; }}};
  vm.runInNewContext(navigationCode, context);
  return {toggle, groups, link, bodyClasses, navClasses, listeners, mediaListeners,
    resize(value) { width = value; mediaListeners['(min-width: 761px)'](); }};
}
for (const width of [320, 390, 700, 740, 760]) {
  const f = fixture(width);
  f.toggle.events.click();
  assert.equal(f.toggle.attrs['aria-expanded'], 'true');
  assert(f.navClasses.has('is-open') && f.bodyClasses.has('is-navigation-open'));
  f.groups[0].button.events.click();
  assert.equal(f.groups[0].submenu.hidden, false);
  f.groups[1].button.events.click();
  assert.equal(f.groups[0].submenu.hidden, true);
  assert.equal(f.groups[1].submenu.hidden, false);
  f.listeners.keydown({key: 'Escape'});
  assert.equal(f.groups[1].submenu.hidden, true);
  assert(f.groups[1].button.focused);
  f.listeners.keydown({key: 'Escape'});
  assert.equal(f.toggle.attrs['aria-expanded'], 'false');
  assert(f.toggle.focused && !f.bodyClasses.has('is-navigation-open'));
  f.toggle.events.click();
  f.listeners.click({target: {closest() { return null; }}});
  assert(!f.bodyClasses.has('is-navigation-open'));
  f.toggle.events.click();
  f.link.events.click({button: 0});
  assert(!f.navClasses.has('is-open') && !f.bodyClasses.has('is-navigation-open'));
  f.toggle.events.click(); f.resize(1024);
  assert(!f.navClasses.has('is-open') && !f.bodyClasses.has('is-navigation-open'));
}
const desktop = fixture(1440);
desktop.groups[0].button.events.click();
assert.equal(desktop.groups[0].submenu.hidden, false);
assert(!desktop.bodyClasses.has('is-navigation-open'), 'Desktop disclosures must not lock page scrolling');
console.log('Passed phone menu locking, submenus, Escape/focus, outside clicks, navigation, breakpoint changes and desktop disclosures.');
