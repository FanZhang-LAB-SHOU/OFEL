"""Build member cards, alumni tiles and one profile page per person from assets/people.json."""

import hashlib
import html
import importlib.util
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'templates'
BASE = 'https://fanzhang-lab-shou.github.io/OFEL/'
RESERVED = {'index', 'research', 'fan-zhang', 'members', 'alumni', 'publications', 'blog', 'contact'}
data = json.loads((ROOT / 'assets/people.json').read_text())
groups = data['groups']
alumni = data.get('alumni', [])


def seniority(member):
    """Senior year first (from 'Year N' in the role), then alphabetical by name as written."""
    year = re.search(r'Year (\d+)', member.get('role', ''))
    return (-int(year.group(1)) if year else 0, member['name'].lower())


for group in groups:
    group['members'].sort(key=seniority)
for cohort in alumni:
    cohort['members'].sort(key=seniority)

import sys  # noqa: E402
sys.path.insert(0, str(ROOT / 'scripts'))
from icons import expand, icon  # noqa: E402
from site_paths import clean_url, output_path, rebase_links, write_page  # noqa: E402
from responsive_images import responsive_images, manifest as image_manifest  # noqa: E402
from page_metadata import render_head  # noqa: E402

spec = importlib.util.spec_from_file_location('publications', ROOT / 'scripts/build-publications.py')
publications = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publications)
for paper in publications.records:
    publications.validate(paper)
# Verified member papers also appear in the All publications collection.
member_records = publications.member_records
known = {publications.paper_key(p) for p in publications.records}
for paper in member_records:
    publications.validate(paper)
    if publications.paper_key(paper) in known:
        raise ValueError(f'{paper["doi"]} is already in publications.json; remove it from member-publications.json')
all_records = publications.records + member_records

icons = {
    'website': icon('globe'),
    'researchgate': icon('researchgate'),
    'email': '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 6 8 7 8-7"/></svg>',
    'github': '<svg viewBox="0 0 24 24" aria-hidden="true" class="github-icon"><path d="M12 .8A11.2 11.2 0 0 0 8.46 22.63c.56.1.77-.24.77-.54v-2.08c-3.13.68-3.79-1.33-3.79-1.33-.51-1.3-1.25-1.65-1.25-1.65-1.02-.7.08-.68.08-.68 1.13.08 1.73 1.16 1.73 1.16 1 1.72 2.64 1.22 3.28.93.1-.73.4-1.22.71-1.5-2.5-.28-5.13-1.25-5.13-5.57 0-1.23.44-2.24 1.16-3.03-.12-.28-.5-1.43.11-2.98 0 0 .94-.3 3.08 1.15A10.76 10.76 0 0 1 12 6.13c.95 0 1.9.13 2.79.38 2.14-1.45 3.08-1.15 3.08-1.15.61 1.55.23 2.7.11 2.98.72.79 1.16 1.8 1.16 3.03 0 4.33-2.64 5.29-5.15 5.57.4.35.76 1.03.76 2.08v3.07c0 .3.2.65.77.54A11.2 11.2 0 0 0 12 .8Z"/></svg>',
}
placeholder = ('<div class="member-photo-placeholder" aria-hidden="true"><svg viewBox="0 0 80 100">'
               '<circle cx="40" cy="34" r="14"/><path d="M15 88V78c0-15 11-24 25-24s25 9 25 24v10"/></svg></div>')


def esc(value):
    return html.escape(value, quote=True)


def chinese_name(person):
    return (f'<span class="person-name-zh" lang="zh-CN">{esc(person["name_zh"])}</span>'
            if person.get('name_zh') else '')


def asset_version():
    """Short content hash of the stylesheet and script, appended to their URLs to bust browser caches."""
    digest = hashlib.sha256((ROOT / 'styles.css').read_bytes() + (ROOT / 'script.js').read_bytes())
    return digest.hexdigest()[:10]


def slugify(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def checked_email(member):
    value = member['email']
    if any(c in value for c in '\r\n') or '@' not in value:
        raise ValueError(f'Invalid email for {member["name"]}')
    return value


def checked_github(member):
    parsed = urlparse(member['github'])
    if parsed.scheme != 'https' or parsed.netloc != 'github.com':
        raise ValueError(f'Invalid GitHub URL for {member["name"]}')
    return member['github']


def checked_website(member):
    parsed = urlparse(member['website'])
    if parsed.scheme != 'https' or not parsed.netloc:
        raise ValueError(f'Invalid website URL for {member["name"]}')
    return member['website']


def checked_researchgate(member):
    parsed = urlparse(member['researchgate'])
    if parsed.scheme != 'https' or parsed.netloc not in {'www.researchgate.net', 'researchgate.net'}:
        raise ValueError(f'Invalid ResearchGate URL for {member["name"]}')
    return member['researchgate']


def contact(member, kind):
    name = esc(member['name'])
    label = {'email': 'Email', 'github': 'GitHub', 'website': 'Website', 'researchgate': 'ResearchGate'}[kind]
    if not member.get(kind):
        return (f'<span class="member-link is-placeholder" role="img" '
                f'aria-label="{label} not yet listed for {name}" title="{label} not yet listed">{icons[kind]}</span>')
    if kind == 'email':
        value = checked_email(member)
        href, description, extra = 'mailto:' + value, f'Email {member["name"]}: {value}', ''
    elif kind == 'website':
        value = href = checked_website(member)
        description = f'{member["name"]}: {member.get("website_label", "Website")} (opens in a new tab)'
        extra = ' target="_blank" rel="noopener noreferrer"'
    elif kind == 'researchgate':
        value = href = checked_researchgate(member)
        description = f'{member["name"]} on ResearchGate (opens in a new tab)'
        extra = ' target="_blank" rel="noopener noreferrer"'
    else:
        value = href = checked_github(member)
        description = f'{member["name"]} on GitHub (opens in a new tab)'
        extra = ' target="_blank" rel="noopener noreferrer"'
    mark = icon(member.get('website_icon', 'globe')) if kind == 'website' else icons[kind]
    return (f'<a class="member-link" href="{esc(href)}"{extra} '
            f'aria-label="{esc(description)}" title="{esc(value)}">{mark}</a>')


def mobile_portrait_style(person):
    """Frame the visible subject on phones without changing the desktop image."""
    framing = person['hero'].get('mobile_portrait')
    if not framing:
        raise ValueError(f'Missing mobile portrait framing for {person["name"]}')
    sw, sh = framing['source']
    x, y, width, height = framing['frame']
    fade = framing.get('fade_start', 92)
    if not (sw > 0 and sh > 0 and width > 0 and height > 0
            and 0 <= x <= sw - width and 0 <= y <= sh - height
            and 60 <= fade <= 95):
        raise ValueError(f'Invalid mobile portrait framing for {person["name"]}')
    return (f' style="--mobile-portrait-ratio: {width / height:.6f}; '
            f'--mobile-image-width: {sw / width * 100:.6f}%; '
            f'--mobile-image-left: {-x / width * 100:.6f}%; '
            f'--mobile-image-top: {-y / height * 100:.6f}%; '
            f'--mobile-fade-start: {fade}%"')


def photo(member, cls, width, height, priority=False, sizes=None):
    if not member.get('photo'):
        return placeholder
    styles = []
    if cls == 'profile-img' and member.get('profile_photo_aspect_ratio'):
        styles.append(f'aspect-ratio: {esc(member["profile_photo_aspect_ratio"])}')
    directory_portrait = cls in {'directory-person-img', 'constellation-img'}
    position = member.get('directory_photo_position', '50% 50%') if directory_portrait else member.get('photo_position')
    if position:
        styles.append(f'object-position: {esc(position)}')
    if directory_portrait and member.get('directory_photo_scale'):
        scale = float(member['directory_photo_scale'])
        if not 1 <= scale <= 2:
            raise ValueError(f'Invalid directory photo scale for {member["name"]}')
        styles.append(f'--directory-photo-scale: {scale:g}')
    style = f' style="{"; ".join(styles)}"' if styles else ''
    loading = 'fetchpriority="high"' if priority else 'loading="lazy"'
    sizes = sizes or ('(max-width: 760px) calc(100vw - 40px), (max-width: 1280px) 46vw, 620px' if priority else None)
    if directory_portrait:
        info = image_manifest().get(member['photo'])
        if info:
            # Cover cropping and extra zoom enlarge landscape sources well beyond
            # the narrow tile width; give the browser the effective source width.
            ratio = .8 if cls == 'constellation-img' else .75
            factor = max(1, info['width'] / info['height'] / ratio) * float(member.get('directory_photo_scale', 1))
            if cls == 'constellation-img':
                sizes = f'(max-width: 700px) {32 * factor:.2f}vw, {round(220 * factor)}px'
            else:
                sizes = (f'(max-width: 760px) {44 * factor:.2f}vw, (max-width: 1100px) {30 * factor:.2f}vw, '
                         f'(max-width: 1400px) {23 * factor:.2f}vw, {round(300 * factor)}px')
    size_attr = f' sizes="{esc(sizes)}"' if sizes else ''
    return (f'<img class="{cls}" src="{esc(member["photo"])}" alt="{esc(member.get("photo_alt", member["name"]))}" '
            f'width="{width}" height="{height}" {loading}{size_attr}{style}>')


def fill(page, marker, sections):
    source = page.read_text()
    start_marker = f'          <!-- {marker}:start -->'
    end_marker = f'          <!-- {marker}:end -->'
    start = source.index(start_marker) + len(start_marker)
    end = source.index(end_marker, start)
    page.write_text(source[:start] + '\n' + rebase_links(responsive_images('\n'.join(sections)), page.relative_to(ROOT).as_posix()) + '\n' + source[end:])


# One ordered list of everyone: current members by group, then alumni by graduation year.
people = []
for group in groups:
    for member in group['members']:
        people.append({**member, 'context': group['heading'], 'back': ('members/index.html', 'Current Members')})
for cohort in alumni:
    label = f'{cohort["year"]} {cohort["degree"]} Graduate'
    for member in cohort['members']:
        if member.get('profile_ref'):
            continue  # Graduates still in the lab keep their existing current-member profile.
        people.append({**member, 'role': label, 'context': 'Alumni', 'back': ('members/alumni.html', 'Alumni')})
for person in people:
    person['slug'] = slugify(person['name'])
slugs = [p['slug'] for p in people]
clash = RESERVED.intersection(slugs) or {s for s in slugs if slugs.count(s) > 1}
if clash:
    raise ValueError(f'Profile page names clash with existing pages or each other: {sorted(clash)}')
by_name = {p['name']: p for p in people}

# Editorial directory: name, role/year and photograph share one profile link.
# Keep the existing group and seniority order, without publishing contact details here.
sections = []
for group in groups:
    for n, member in enumerate(group['members']):
        name, href = esc(member['name']), esc('members/' + by_name[member['name']]['slug'] + '.html')
        # Preserve old group anchors on the first member heading.
        anchor = f' id="{esc(group["id"])}-title"' if n == 0 else ''
        portrait = {**member, 'photo': member.get('profile_photo') or member.get('photo'), 'photo_alt': ''}
        image = photo(portrait, 'directory-person-img', 460, 614,
                      sizes='(max-width: 760px) 44vw, (max-width: 1100px) 30vw, (max-width: 1400px) 23vw, 300px')
        sections.append(
            f'            <article class="directory-person" data-reveal><a class="directory-person-link" href="{href}">'
            f'<div class="directory-person-label"><h2{anchor}>{name}</h2>{chinese_name(member)}<p>{esc(member["role"])}</p></div>'
            f'<div class="directory-photo" aria-hidden="true">{image}</div></a></article>'
        )
fill(ROOT / output_path('members/index.html'), 'member-groups', sections)

# A separate first screen uses supplied photographs only; the full directory stays below.
floating = []
# Extra photographs receive small edge positions beyond the original eleven CSS slots.
extra_photo_slots = [(94, 14, 6), (36, 85, 7), (66, 12, 7), (8, 60, 6),
                     (91, 65, 6), (37, 16, 6), (64, 83, 6), (52, 90, 6)]
for n, member in enumerate(m for group in groups for m in group['members']
                           if m.get('profile_photo') or m.get('photo')):
    portrait = {**member, 'photo': member.get('profile_photo') or member['photo'], 'photo_alt': ''}
    image = photo(portrait, 'constellation-img', 460, 614, sizes='(max-width: 700px) 32vw, 220px')
    position = ''
    if n >= 11:
        x, y, size = extra_photo_slots[(n - 11) % len(extra_photo_slots)]
        position = f' style="--photo-x: {x}%; --photo-y: {y}%; --photo-size: {size}%"'
    floating.append(
        f'          <li class="team-space-card"{position}><a class="team-space-person" href="members/{esc(by_name[member["name"]]["slug"])}.html" aria-label="Meet {esc(member["name"])}">'
        f'<span class="team-space-photo" aria-hidden="true">{image}</span><span class="team-space-name" aria-hidden="true">{esc(member["name"])}</span></a></li>'
    )
fill(ROOT / output_path('members/index.html'), 'floating-members', floating)

# Alumni shares the aligned portrait tiles, with graduation-year and degree groups.
sections = []
for cohort in alumni:
    tiles = []
    for member in cohort['members']:
        reference = member.get('profile_ref', member['name'])
        if reference not in by_name:
            raise ValueError(f'Unknown alumni profile reference: {reference}')
        linked_person = by_name[reference]
        display = {**linked_person, **member}
        portrait = {**display, 'photo': display.get('profile_photo') or display.get('photo'), 'photo_alt': ''}
        image = photo(portrait, 'directory-person-img', 460, 614,
                      sizes='(max-width: 760px) 44vw, (max-width: 1100px) 30vw, (max-width: 1400px) 23vw, 300px')
        graduation = f'{cohort["year"]} {cohort["degree"]} Graduate'
        tiles.append(
            f'                <li class="directory-person" data-reveal><a class="directory-person-link" href="members/{esc(linked_person["slug"])}.html">'
            f'<div class="directory-person-label"><h3>{esc(member["name"])}</h3>{chinese_name(display)}<p>{esc(graduation)}</p></div>'
            f'<div class="directory-photo" aria-hidden="true">{image}</div></a></li>'
        )
    year = cohort['year']
    cohort_id = f'alumni-{year}-{slugify(cohort["degree"])}'
    sections.append(
        f'            <section class="directory-cohort" aria-labelledby="{cohort_id}-title">\n'
        f'              <h2 id="{cohort_id}-title">{year} {esc(cohort["degree"])} Graduates</h2>\n'
        f'              <ul class="directory-board directory-list">\n' + '\n'.join(tiles) + '\n              </ul>\n            </section>'
    )
fill(ROOT / output_path('members/alumni.html'), 'alumni-groups', sections)

# The alumni overview uses actual listed cohorts; no locations or career outcomes are inferred.
years = sorted({cohort['year'] for cohort in alumni}, reverse=True)
fill(ROOT / output_path('members/alumni.html'), 'alumni-overview', [
    f'<dl class="alumni-overview"><div><dt>Alumni</dt><dd>{sum(len(c["members"]) for c in alumni)}</dd></div>'
    f'<div><dt>Graduation years</dt><dd>{len(years)}</dd></div></dl>'
])
fill(ROOT / output_path('members/alumni.html'), 'alumni-cohort-links', [
    f'<a class="alumni-cohort-hop" href="#alumni-{cohort["year"]}-{slugify(cohort["degree"])}-title">'
    f'<span>Class of {cohort["year"]}</span><strong>{esc(cohort["degree"])}</strong>'
    f'<small>{len(cohort["members"])} {"graduate" if len(cohort["members"]) == 1 else "graduates"} <span aria-hidden="true">↗</span></small></a>'
    for cohort in alumni
])


def render_cv(cv, paper_list):
    """Keep supplied CV entries on the person's page; manuscripts are not publication records."""
    sections = []
    navigation = []
    for section in cv['sections']:
        key = section['id']
        if not re.fullmatch(r'[a-z][a-z0-9-]*', key):
            raise ValueError(f'Invalid CV section ID: {key}')
        section_id = 'profile-publications-title' if section['kind'] == 'publications' else 'cv-' + key
        navigation.append(f'<a href="#{section_id}">{esc(section["title"])}</a>')
        heading = f'<h2 id="{section_id}" data-reveal>{esc(section["title"])}</h2>'
        if section['kind'] == 'publications':
            note = f'<p class="profile-cv-note" data-reveal>{esc(section["note"])}</p>' if section.get('note') else ''
            sections.append(f'<section class="profile-publications profile-cv-section" aria-labelledby="{section_id}">{heading}{note}{paper_list}</section>')
            continue
        cards = []
        for item in section['entries']:
            paragraphs = ''.join(f'<p>{esc(par)}</p>' for par in item.get('paragraphs', []))
            if section['kind'] == 'manuscripts':
                if item['status'] != 'Under review':
                    raise ValueError(f'Unexpected manuscript status: {item["status"]}')
                detail = (f'<p class="profile-cv-period">{item["year"]} · {esc(item["status"])}</p>'
                          f'<h3>{esc(item["title"])}</h3><p class="profile-cv-authors">{esc(item["authors"])}</p>'
                          f'<p class="profile-cv-subtitle">Submitted to <em>{esc(item["journal"])}</em></p>')
            else:
                period = f'<p class="profile-cv-period">{esc(item["period"])}</p>' if item.get('period') else ''
                subtitle = f'<p class="profile-cv-subtitle">{esc(item["subtitle"])}</p>' if item.get('subtitle') else ''
                detail = f'{period}<h3>{esc(item["title"])}</h3>{subtitle}'
            cards.append(f'<article class="profile-cv-card" data-reveal>{detail}{paragraphs}</article>')
        sections.append(f'<section class="profile-cv-section" aria-labelledby="{section_id}">{heading}'
                        f'<div class="profile-cv-grid" data-layout="{esc(section.get("layout", "timeline"))}">{"".join(cards)}</div></section>')
    return ('<div class="profile-cv"><nav class="profile-cv-nav" aria-label="Curriculum vitae sections" data-reveal>'
            + ''.join(navigation) + '</nav>' + ''.join(sections) + '</div>')


# Profile pages: name, role, contact, bio, optional CV, then previous/next person.
header = expand((TEMPLATES / 'header.html').read_text())
footer = expand((TEMPLATES / 'footer.html').read_text())
for n, person in enumerate(people):
    name = esc(person['name'])
    given, family = person['name'].split()[0], person['name'].split()[-1]
    papers = sorted((p for p in all_records if any(publications.is_author(a, given, family) for a in p['authors'])),
                    key=lambda p: p['year'], reverse=True)
    paper_list = ('<div class="publication-list profile-publication-list">\n'
                  + '\n'.join(publications.article_html(p, highlight=(given, family)) for p in papers)
                  + '\n        </div>') if papers else '<p class="profile-empty">No publications listed yet.</p>'
    paper_list = paper_list.replace('<article ', '<article data-reveal ').replace('<p class="profile-empty">', '<p class="profile-empty" data-reveal>')
    links = []
    if person.get('email'):
        value = checked_email(person)
        links.append(f'<a class="text-link" href="mailto:{esc(value)}">{icon("mail")}{esc(value)}</a>')
    if person.get('github'):
        links.append(f'<a class="text-link" href="{esc(checked_github(person))}" target="_blank" rel="noopener noreferrer">' + icon('github') + 'GitHub'
                     '<span class="sr-only"> (opens in a new tab)</span></a>')
    if person.get('website'):
        links.append(f'<a class="text-link" href="{esc(checked_website(person))}" target="_blank" rel="noopener noreferrer">'
                     + icon(person.get('website_icon', 'globe')) + esc(person.get('website_label', 'Website'))
                     + '<span class="sr-only"> (opens in a new tab)</span></a>')
    if person.get('researchgate'):
        links.append(f'<a class="text-link" href="{esc(checked_researchgate(person))}" target="_blank" rel="noopener noreferrer">'
                     + icon('researchgate') + 'ResearchGate'
                     + '<span class="sr-only"> (opens in a new tab)</span></a>')
    if person.get('orcid'):
        orcid = person['orcid']
        if not re.fullmatch(r'\d{4}-\d{4}-\d{4}-\d{3}[\dX]', orcid):
            raise ValueError(f'Invalid ORCID for {person["name"]}')
        links.append(f'<a class="text-link" href="https://orcid.org/{esc(orcid)}" target="_blank" rel="noopener noreferrer">'
                     f'<img src="assets/brands/orcid.svg" alt="" width="18" height="18">ORCID'
                     f'<span class="sr-only"> {esc(orcid)} (opens in a new tab)</span></a>')
    detail_links = list(links)
    if person.get('phone'):
        number = re.sub(r'[\s-]', '', person['phone'])
        if not re.fullmatch(r'\+\d{7,15}', number):
            raise ValueError(f'Invalid phone number for {person["name"]}')
        detail_links.append(f'<a class="text-link" href="tel:{number}">{esc(person["phone"])}</a>')
    links_html = f'<div class="pi-links">{"".join(detail_links)}</div>' if detail_links else ''
    bio = ''.join(f'<p>{esc(par)}</p>' for par in person['bio'].split('\n\n')) if person.get('bio') else \
        '<p class="profile-empty">Profile coming soon.</p>'
    if person.get('bio_zh'):
        original = ''.join(f'<p>{esc(par)}</p>' for par in person['bio_zh'].split('\n\n'))
        bio += ('<details class="profile-bio-original"><summary>中文原文 / Original Chinese</summary>'
                f'<div lang="zh-CN">{original}</div></details>')
    gallery_html = ''
    if person.get('gallery'):
        gallery_items = []
        for item in person['gallery']:
            if not item['image'].startswith('assets/people/galleries/') or not (ROOT / item['image']).is_file():
                raise ValueError(f'Missing gallery photo for {person["name"]}')
            gallery_items.append(
                f'<a class="profile-gallery-item" href="{esc(item["image"])}" data-gallery-open data-gallery-caption="{esc(item["caption"])}" '
                f'aria-label="View photo: {esc(item["caption"])}" data-reveal>'
                f'<span class="profile-gallery-image"><img src="{esc(item["image"])}" alt="{esc(item["alt"])}" '
                f'width="{item["width"]}" height="{item["height"]}" loading="lazy" sizes="(max-width: 760px) calc(100vw - 40px), 740px"></span>'
                f'<span class="profile-gallery-caption">{esc(item["caption"])}<span aria-hidden="true">↗</span></span></a>'
            )
        gallery_html = (
            '<section class="profile-gallery" data-profile-gallery aria-labelledby="profile-gallery-title">'
            '<div class="profile-gallery-heading" data-reveal><p class="eyebrow teal">Photo journal</p>'
            '<h2 id="profile-gallery-title">In the field &amp; beyond.</h2>'
            '<p>Research, travel, and moments along the way.</p></div>'
            f'<div class="profile-gallery-grid">{"".join(gallery_items)}</div>'
            '<dialog class="profile-gallery-viewer" data-gallery-viewer aria-label="Photo viewer">'
            '<button type="button" class="gallery-close" data-gallery-close aria-label="Close photo viewer">×</button>'
            '<figure><img data-gallery-full alt=""><figcaption data-gallery-caption></figcaption></figure>'
            '<div class="gallery-viewer-controls"><button type="button" data-gallery-prev aria-label="Previous photo">←</button>'
            '<span data-gallery-count role="status" aria-live="polite" aria-atomic="true"></span>'
            '<button type="button" data-gallery-next aria-label="Next photo">→</button></div></dialog></section>'
        )
    pager = []
    back_href, back_label = person['back']
    neighbours = [
        ('prev', people[n - 1] if n > 0 else None, 'Previous', 'left'),
        ('next', people[n + 1] if n < len(people) - 1 else None, 'Next', 'right'),
    ]
    for side, neighbour, direction, arrow in neighbours:
        href = f'members/{neighbour["slug"]}.html' if neighbour else back_href
        label = neighbour['name'] if neighbour else back_label
        direction = direction if neighbour else 'Back to'
        relation = f' rel="{side}"' if neighbour else ''
        badge = f'<span class="pager-badge" aria-hidden="true">{icon(arrow)}</span>'
        text = f'<span class="pager-text"><span class="pager-dir">{direction}</span><span class="pager-name">{esc(label)}</span></span>'
        pager.append(f'<a class="profile-{side}"{relation} href="{esc(href)}" aria-label="{direction}: {esc(label)}">'
                     + (badge + text if side == 'prev' else text + badge) + '</a>')
    breadcrumb = (f'<nav class="breadcrumb" aria-label="Breadcrumb"><a href="{back_href}">{back_label}</a>'
                  f'<span aria-hidden="true">/</span><span aria-current="page">{name}</span></nav>')
    # Current members and alumni share the same introduction rules, including complete photos.
    # Keep the full existing profile below it, including bilingual bios and papers.
    hero = person.get('hero', {})
    original_scene = hero.get('layout') == 'photo'
    has_intro = bool(person.get('photo') and (hero.get('cutout') or original_scene))
    intro = ''
    if has_intro:
        hero = person['hero']
        if not original_scene and not (ROOT / hero['cutout']).is_file():
            raise ValueError(f'Missing foreground portrait for {person["name"]}')
        first_paragraph = hero.get('summary') or (person.get('bio') or '').split('\n\n')[0]
        summary = f'<p class="member-intro-summary">{esc(first_paragraph)}</p>' if first_paragraph else ''
        topics = ''.join(f'<span>{esc(topic)}</span>' for topic in hero.get('research', []))
        topics = topics or '<span class="member-intro-topic-pending">To be updated</span>'
        hero_links = f'<div class="pi-links">{"".join(links)}</div>' if links else ''
        tint = hero.get('background_color')
        if original_scene:
            scene_width, scene_height = hero['photo_dimensions']
            scene_sizes = ('(max-width: 760px) calc(100vw - 48px), 38vw'
                           if hero.get('photo_display') == 'contained' else 'max(100vw, 150svh)')
            backdrop = photo(person, 'member-intro-scene-image', scene_width, scene_height,
                             priority=True, sizes=scene_sizes)
            if hero.get('scene_image'):
                if not (ROOT / hero['scene_image']).is_file():
                    raise ValueError(f'Missing extended scene for {person["name"]}')
                panorama_width, panorama_height = hero['scene_dimensions']
                backdrop = (f'<picture><source media="(min-width: 761px)" srcset="{esc(hero["scene_image"])}" '
                            f'width="{panorama_width}" height="{panorama_height}">{backdrop}</picture>')
        elif tint:
            if not re.fullmatch(r'#[0-9a-fA-F]{6}', tint):
                raise ValueError(f'Invalid portrait background color for {person["name"]}')
            backdrop = ('<div class="member-intro-wash member-intro-color" aria-hidden="true" '
                        f'style="--member-tint: {tint}"></div>')
        else:
            backdrop_source = hero.get('background_image') or person['photo']
            if not (ROOT / backdrop_source).is_file():
                raise ValueError(f'Missing introduction background for {person["name"]}')
            backdrop_width, backdrop_height = hero.get('background_dimensions', [640, 800])
            backdrop = (f'<img class="member-intro-wash" src="{esc(backdrop_source)}" alt="" aria-hidden="true" '
                        f'width="{backdrop_width}" height="{backdrop_height}" sizes="640px" fetchpriority="low">')
        portrait = ''
        if not original_scene:
            hero_person = {**person, 'photo': hero['cutout']}
            feather = hero.get('edge_feather')
            if feather not in {None, 'soft', 'cropped'}:
                raise ValueError(f'Invalid portrait feathering for {person["name"]}')
            feather_attr = f' data-portrait-feather="{feather}"' if feather else ''
            portrait_width, portrait_height = hero['mobile_portrait']['source']
            portrait = ('<div class="member-intro-watermark" aria-hidden="true">OFEL</div>'
                        f'<div class="member-intro-portrait"{feather_attr}{mobile_portrait_style(person)}>{photo(hero_person, "member-intro-photo", portrait_width, portrait_height, priority=True)}</div>')
        intro_class = 'member-intro member-intro-photo-scene' if original_scene else 'member-intro'
        scene_display = ''
        if original_scene and (hero.get('photo_display') == 'contained' or hero.get('photo_copy') == 'right'):
            scene_variant = ('data-photo-display="contained"' if hero.get('photo_display') == 'contained'
                             else 'data-photo-copy="right"')
            scene_display = (f' {scene_variant} style="--scene-width: {scene_width}px; '
                             f'--scene-ratio: {scene_width} / {scene_height}; '
                             f'--scene-inverse-ratio: {scene_height / scene_width:.8f}"')
        intro = (
            f'    <section class="{intro_class}" aria-labelledby="profile-title" data-member-intro{scene_display}>'
            f'{backdrop}'
            f'{portrait}'
            '<div class="container member-intro-layout">'
            '<div class="member-intro-copy">'
            f'<div class="member-intro-identity" style="--mobile-name-size: {min(7.8, 60 / max(len(given), len(family), 1)):.4f}vw">'
            '<p class="member-intro-greeting">Hi, I’m</p>'
            f'<h1 id="profile-title"><span>{esc(given)}</span><span>{esc(family)}</span></h1>'
            f'{chinese_name(person)}'
            f'<p class="member-intro-role">{esc(person["role"])}</p></div>{summary}{hero_links}</div>'
            '<div class="member-intro-research"><p>Research interests</p>'
            f'<div>{topics}</div></div></div>'
            f'<a class="member-intro-more" href="#member-details">{icon("down")}<span>Scroll to profile</span></a>'
            '</section>\n'
        )
    details_id = 'member-details' if has_intro else 'profile-title'
    heading = (f'<h2 class="member-details-heading" id="member-details">{name}</h2>' if has_intro
               else f'<h1 id="profile-title">{name}</h1>')
    breadcrumb_html = '' if has_intro else f'        {breadcrumb}\n'
    detail_person = {**person, 'photo': person.get('profile_photo') or person.get('photo'),
                     'photo_alt': person.get('profile_photo_alt') or person.get('photo_alt') or person['name']}
    detail_photo_class = 'profile-photo profile-photo-enhanced' if person.get('profile_photo') else 'profile-photo'
    curriculum = render_cv(person['cv'], paper_list) if person.get('cv') else (
        '<section class="profile-publications" aria-labelledby="profile-publications-title">'
        '<h2 id="profile-publications-title" data-reveal>Publications</h2>\n        ' + paper_list + '\n        </section>')
    content = (
        intro + f'    <section class="people section detail-page profile-page" aria-labelledby="{details_id}">\n'
        f'      <div class="container">\n'
        f'{breadcrumb_html}'
        f'        <div class="profile-grid">\n'
        f'          <div class="{detail_photo_class}" data-reveal>{photo(detail_person, "profile-img", 600, 800)}</div>\n'
        f'          <div class="profile-content" data-reveal style="--reveal-delay: .08s"><p class="eyebrow teal">{esc(person["context"])}</p>'
        f'{heading}{chinese_name(person)}<p class="pi-role">{esc(person["role"])}</p>{links_html}'
        f'<div class="profile-bio">{bio}</div></div>\n'
        f'        </div>\n'
        f'{gallery_html}'
        f'        {curriculum}\n'
        f'        <nav class="profile-pager" aria-label="Browse people" data-reveal>{"".join(pager)}</nav>\n'
        f'      </div>\n    </section>\n'
    )
    title = f'{person["name"]} | OFEL'
    description = f'{person["name"]}, {person["role"]} at the Oceanic Fisheries Ecosystem Laboratory, Shanghai Ocean University.'
    head = render_head(title, description, BASE + clean_url('members/' + person['slug'] + '.html'), asset_version(),
                       image=person.get('photo'), image_alt=person.get('photo_alt') or (person['name'] + ' profile photo' if person.get('photo') else None), kind='profile')
    write_page(f'members/{person["slug"]}.html',
        head + f'<body id="top" data-page="profile" data-nav-section="people"{ " data-member-hero" if has_intro else ""}>\n'
        '  <a class="skip-link" href="#main">Skip to content</a>\n' + header
        + '\n  <main id="main">\n' + content + '  </main>\n\n' + footer + '</body>\n</html>\n'
    )

current = sum(len(g['members']) for g in groups)
alumni_tiles = sum(len(cohort['members']) for cohort in alumni)
print(f'Built {current} member cards, {alumni_tiles} alumni tiles and {len(people)} profile pages.')
