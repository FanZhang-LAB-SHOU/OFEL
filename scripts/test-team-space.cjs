// Exercise full-stage photo travel, bounded reflections, and the real motion controller.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict');
const people = JSON.parse(fs.readFileSync(path.join(__dirname, '../assets/people.json'), 'utf8'));
const directory = fs.readFileSync(path.join(__dirname, '../members/index.html'), 'utf8');
const floating = directory.split('<!-- floating-members:start -->')[1].split('<!-- floating-members:end -->')[0];
const expectedNames = people.groups.flatMap(group => group.members).filter(person => person.profile_photo || person.photo).map(person => person.name);
const floatingNames = [...floating.matchAll(/aria-label="Meet ([^"]+)"/g)].map(match => match[1]);
assert.equal(floatingNames.length, expectedNames.length, 'Every photographed current member must appear in the floating area');
assert.deepEqual(new Set(floatingNames), new Set(expectedNames), 'Adding a new photo must not exclude members later in the list');
const source = fs.readFileSync(path.join(__dirname, '../script.js'), 'utf8');
function functionSource(name) {
  const start = source.indexOf(`function ${name}(`);
  return source.slice(start, source.indexOf('\n}', start) + 2);
}
const helpers = functionSource('teamPhotoBounds') + '\n' + functionSource('advanceTeamPhoto');
const scope = {}; vm.runInNewContext(helpers, scope);
for (const [width, height, photoWidth] of [[320, 720, 100], [390, 844, 116], [768, 760, 100], [1440, 820, 190], [1600, 980, 190]]) {
  const b = scope.teamPhotoBounds(width, height, photoWidth, photoWidth * 1.25);
  const state = {x: width / 2, y: height / 2, vx: 39, vy: -51};
  let minX = state.x, maxX = state.x, minY = state.y, maxY = state.y;
  for (let i = 0; i < 12000; i++) {
    scope.advanceTeamPhoto(state, b, 1 / 60);
    assert(state.x >= b.minX && state.x <= b.maxX && state.y >= b.minY && state.y <= b.maxY);
    minX = Math.min(minX, state.x); maxX = Math.max(maxX, state.x);
    minY = Math.min(minY, state.y); maxY = Math.max(maxY, state.y);
  }
  assert(maxX - minX > (b.maxX - b.minX) * .95, 'Travel must span the width, rather than bob locally');
  assert(maxY - minY > (b.maxY - b.minY) * .95, 'Photos must travel from top to bottom');
}
function fixture(reduced = false) {
  const events = {}, classes = new Set(), queue = new Map(); let sequence = 0, intersection, width = 1200;
  const stage = {getBoundingClientRect: () => ({left: 0, top: 0, width, height: 760})};
  const cards = Array.from({length: 13}, (_, i) => ({events: {}, offsetWidth: 100, offsetHeight: 125,
    style: {removeProperty(key) { delete this[key]; }},
    getBoundingClientRect: () => ({left: 60 + i * 70, top: 80 + i * 35, width: 100, height: 125}),
    addEventListener(type, fn) { this.events[type] = fn; }}));
  const button = {attrs: {}, setAttribute(key, value) { this.attrs[key] = value; }, addEventListener(type, fn) { events[type] = fn; }};
  const motion = {matches: reduced, addEventListener(type, fn) { events.motion = fn; }};
  const hero = {querySelectorAll: () => cards, querySelector: s => s === '.team-space-stage' ? stage : button,
    classList: {add: c => classes.add(c), remove: c => classes.delete(c), toggle: (c, on) => on ? classes.add(c) : classes.delete(c)}};
  const document = {hidden: false, querySelector: () => hero, addEventListener(type, fn) { events[type] = fn; }};
  const window = {innerWidth: 1200, matchMedia: () => motion,
    requestAnimationFrame(fn) { const id = ++sequence; queue.set(id, fn); return id; },
    cancelAnimationFrame(id) { queue.delete(id); }, addEventListener(type, fn) { events[type] = fn; },
    IntersectionObserver: class {constructor(fn) { intersection = fn; } observe(value) { assert.equal(value, hero); }}};
  vm.runInNewContext(helpers + '\n' + functionSource('initTeamSpace') + '\ninitTeamSpace();', {window, document, Math});
  return {events, classes, cards, motion, button, document, queue,
    intersect(on) { intersection([{isIntersecting: on}]); },
    resize(w) { width = w; events.resize(); },
    tick(time) { const [id, fn] = queue.entries().next().value; queue.delete(id); fn(time); }};
}
const f = fixture(); assert(f.classes.has('is-moving')); assert.equal(f.queue.size, 1);
f.tick(0); const initial = f.cards[0].style.transform; f.tick(16); assert.notEqual(f.cards[0].style.transform, initial);
f.cards[0].events.pointerenter(); const held = f.cards[0].style.transform, other = f.cards[1].style.transform;
f.tick(32); assert.equal(f.cards[0].style.transform, held); assert.notEqual(f.cards[1].style.transform, other);
f.cards[0].events.pointerleave(); f.tick(48); assert.notEqual(f.cards[0].style.transform, held);
f.cards[0].events.focusin(); const focused = f.cards[0].style.transform; f.tick(64); assert.equal(f.cards[0].style.transform, focused);
f.cards[0].events.focusout();
f.events.click(); assert(!f.classes.has('is-moving')); assert.equal(f.queue.size, 0); assert.equal(f.button.attrs['aria-pressed'], 'true');
f.intersect(true); assert.equal(f.queue.size, 0, 'Visibility cannot undo a manual pause');
f.events.click(); assert.equal(f.queue.size, 1);
f.intersect(false); assert.equal(f.queue.size, 0); f.intersect(true); assert.equal(f.queue.size, 1);
f.document.hidden = true; f.events.visibilitychange(); assert.equal(f.queue.size, 0);
f.document.hidden = false; f.events.visibilitychange(); f.tick(100000); const resumed = f.cards[0].style.transform;
assert.equal(resumed, focused, 'Returning from a hidden tab must not jump');
f.resize(390); f.tick(100016);
f.motion.matches = true; f.events.motion(); assert.equal(f.queue.size, 0); assert(!f.classes.has('has-free-motion')); assert(f.button.hidden);
f.motion.matches = false; f.events.motion(); assert(f.classes.has('is-moving'));
const slow = fixture(); slow.tick(0);
const position = card => card.style.transform.match(/translate3d\(([-.\d]+)px, ([-.\d]+)px/).slice(1).map(Number);
const start = position(slow.cards[0]);
for (let i = 1; i <= 600; i++) slow.tick(i * 16);
const finish = position(slow.cards[0]);
assert(Math.abs(finish[0] - start[0]) >= 12 && Math.abs(finish[0] - start[0]) <= 36, 'Horizontal movement should stay gentle over ten seconds');
assert(Math.abs(finish[1] - start[1]) >= 20 && Math.abs(finish[1] - start[1]) <= 48, 'Keep full-stage paths at the earlier gentle pace');
const still = fixture(true); assert.equal(still.queue.size, 0); assert(!still.classes.has('has-free-motion'));
vm.runInNewContext(functionSource('initTeamSpace') + '\ninitTeamSpace();', {document: {querySelector: () => null}});
console.log('Passed full-stage horizontal/vertical travel, edge reflections, hover/focus holds, pause, resize, visibility and reduced-motion checks.');
