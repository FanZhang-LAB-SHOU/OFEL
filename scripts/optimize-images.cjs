// Run when source photos or covers change. Commit derivatives; CI needs only Python.
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const sharp = require('sharp');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'assets/optimized');
const widths = [320, 640, 960, 1440, 1920];

async function files(folder) {
  const entries = await fs.readdir(folder, {withFileTypes: true});
  const nested = await Promise.all(entries.map(entry => entry.isDirectory()
    ? files(path.join(folder, entry.name)) : [path.join(folder, entry.name)]));
  return nested.flat();
}

async function main() {
  await fs.mkdir(output, {recursive: true});
  const sources = (await Promise.all(['people', 'news', 'research', 'software', 'contact']
    .map(folder => files(path.join(root, 'assets', folder))))).flat().sort();
  const manifest = {};
  for (const source of sources) {
    if (!/\.(png|jpe?g|webp)$/i.test(source)) continue;
    const bytes = await fs.readFile(source);
    if (bytes.length < 100 * 1024) continue;
    const input = sharp(bytes);
    const meta = await input.metadata();
    if (meta.pages > 1) continue; // Preserve animated media as supplied.
    const rotated = [5, 6, 7, 8].includes(meta.orientation);
    const width = rotated ? meta.height : meta.width;
    const height = rotated ? meta.width : meta.height;
    const originalFacultyPhoto = /people\/fan-zhang\.jpg$/.test(source);
    const enhancedPortrait = /people\/portraits\/.*-enhanced-v1\.webp$/.test(source);
    const quality = originalFacultyPhoto ? 94 : enhancedPortrait ? 90 : /poster|fig\d|roadmap/i.test(source) ? 88 : 82;
    const digest = crypto.createHash('sha256').update(bytes).digest('hex');
    const version = crypto.createHash('sha256').update(digest + `webp-${quality}-v1`).digest('hex').slice(0, 12);
    const stem = path.basename(source, path.extname(source)).replace(/[^a-z0-9-]/gi, '-');
    const outputWidths = originalFacultyPhoto ? [...widths, 2560, 3200] : widths;
    const sizes = [...new Set([...outputWidths.filter(size => size < width), Math.min(width, originalFacultyPhoto ? 3200 : 1920)])].sort((a,b) => a-b);
    const variants = [];
    for (const size of sizes) {
      const filename = `${stem}-${version}-${size}.webp`;
      const dest = path.join(output, filename);
      try { await fs.access(dest); }
      catch { await sharp(bytes).rotate().resize({width: size, withoutEnlargement: true}).webp({quality, effort: 6}).toFile(dest); }
      variants.push({width: size, src: `assets/optimized/${filename}`, bytes: (await fs.stat(dest)).size});
    }
    const relative = path.relative(root, source).split(path.sep).join('/');
    manifest[relative] = {sha256: digest, bytes: bytes.length, width, height, variants};
  }
  await fs.writeFile(path.join(output, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
  console.log(`Prepared responsive WebP variants for ${Object.keys(manifest).length} source images.`);
}
main().catch(error => { console.error(error); process.exitCode = 1; });
