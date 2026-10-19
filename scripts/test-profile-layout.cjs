// Keep the faculty portrait clear of the right workspace and reveal profile sections on approach.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../script.js'), 'utf8');
function functionSource(name) {
  const start = source.indexOf(`function ${name}(`);
  assert(start >= 0, `Missing ${name}`);
  return source.slice(start, source.indexOf('\n}', start) + 2);
}
const scope = {};
vm.runInNewContext(functionSource('facultyPortraitGeometry'), scope);
for (const [width, height] of [[320, 568], [360, 640], [375, 812], [390, 844], [414, 896], [430, 932], [568, 320], [760, 375], [768, 1024], [1024, 768], [1280, 720], [1440, 900], [1512, 982], [1867, 925], [2560, 1080], [1200, 1300]]) {
  const g = scope.facultyPortraitGeometry(width, height, 80);
  assert(g.headTop >= 80, 'Portrait head must remain below the navigation');
  assert(g.personLeft >= 0, 'The visible body should remain inside the screen');
  if (!g.compact) {
    assert(g.personRight <= width * .5, 'Portrait must fit in the left half');
    assert(width * .52 - g.personRight >= 20, 'Right workspace needs a gap from the body');
  } else {
    assert(g.personRight <= width, 'Compact portrait should remain inside the screen');
    // Adding a card changes hero height, but must not keep pushing the portrait and controls down.
    const expanded = scope.facultyPortraitGeometry(width, height + 700, 80, height);
    assert.equal(expanded.bottom, g.bottom);
  }
}
let scroll, ready = false;
const sections = [100, 1100, 2100].map(top => ({ top, visible: false,
  getBoundingClientRect() { return {top: this.top}; }, classList: {add() {}} }));
sections.forEach(section => section.classList.add = () => { section.visible = true; });
const window = {innerHeight: 800, matchMedia: () => ({matches: false}),
  addEventListener(type, fn) { if (type === 'scroll') scroll = fn; }, removeEventListener() {}};
const document = {querySelectorAll: () => sections, documentElement: {classList: {add() { ready = true; }}}};
vm.runInNewContext(functionSource('initReveal') + '\ninitReveal();', {window, document});
assert(ready && sections[0].visible && !sections[1].visible && !sections[2].visible);
sections.forEach(s => { s.top -= 800; }); scroll();
assert(sections[1].visible && !sections[2].visible);
window.matchMedia = () => ({matches: true}); ready = false;
vm.runInNewContext(functionSource('initReveal') + '\ninitReveal();', {window, document});
assert(!ready, 'Reduced motion must not hide sections behind an animation gate');
const people = JSON.parse(fs.readFileSync(path.join(__dirname, '../assets/people.json'), 'utf8'));
for (const person of people.groups.concat(people.alumni || []).flatMap(group => group.members)) {
  if (person.profile_ref) continue;
  const slug = person.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const html = fs.readFileSync(path.join(__dirname, `../members/${slug}/index.html`), 'utf8');
  const hasIntro = Boolean(person.photo && person.hero && (person.hero.cutout || person.hero.layout === 'photo'));
  assert.equal(html.includes('data-member-intro'), hasIntro, `${person.name} must use the same photo-introduction rule for members and alumni`);
  assert.equal((html.match(/<h1[ >]/g) || []).length, 1, `${person.name} needs one main heading`);
  if (hasIntro) {
    assert(html.includes('data-member-hero'));
    assert(html.indexOf('data-member-intro') < html.indexOf('class="profile-grid"'));
    assert(html.includes('href="#member-details"') && html.includes('id="member-details"'));
    if (person.hero.layout === 'photo') {
      const intro = html.slice(html.indexOf('data-member-intro'), html.indexOf('class="profile-grid"'));
      assert(html.includes('class="member-intro member-intro-photo-scene"'));
      assert(!intro.includes('member-intro-portrait') && !intro.includes('cutout') && !intro.includes('member-intro-wash'), 'Complete-photo introductions must not render extracted subjects or replacement backgrounds');
      const scene = intro.match(/<img class="member-intro-scene-image"[^>]*>/)[0];
      assert(scene.includes(person.photo) && scene.includes('fetchpriority="high"'), 'Load the original photo for the introduction');
      assert(scene.includes(`${person.hero.photo_dimensions[0]}w`), 'Offer the full-resolution original on high-density displays');
      if (person.hero.scene_image) {
        const wide = intro.match(/<source media="\(min-width: 761px\)"[^>]*>/)[0];
        assert(wide.includes(person.hero.scene_image), 'Use the extended continuous scene on desktop');
        assert(wide.includes(`width="${person.hero.scene_dimensions[0]}"`) && wide.includes(`height="${person.hero.scene_dimensions[1]}"`), 'The panorama needs its own aspect ratio so the subject remains full height');
      }
    }
  }
}
console.log('Passed portrait geometry, compact layout, progressive reveals, reduced motion and shared member/alumni photo introductions.');
