// Node-side .docx renderer for the group-synastry skill (Phase 2).
//
// Invoked by scripts/render_docx.py. Reads a payload on stdin:
//   { kind: "natal"|"synastry"|"composite", style: {...}, chart: {...} }
// and writes the .docx to the path given via --out <path>.
//
// Why a JS file at all: docx-js has no maintained Python port; the validation
// path the spec calls for (§10.2) lives in the JS ecosystem.

const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun,
  Table, TableRow, TableCell, WidthType, BorderStyle,
  HeadingLevel, AlignmentType,
  Footer, PageNumber,
  ShadingType,
  PageOrientation,
  ExternalHyperlink,
} = require('docx');
const { Lexer } = require('marked');

const SIGN_GLYPHS = {
  Aries: '♈', Taurus: '♉', Gemini: '♊', Cancer: '♋',
  Leo: '♌', Virgo: '♍', Libra: '♎', Scorpio: '♏',
  Sagittarius: '♐', Capricorn: '♑', Aquarius: '♒', Pisces: '♓',
};
const PLANET_GLYPHS = {
  Sun: '☉', Moon: '☽', Mercury: '☿', Venus: '♀',
  Mars: '♂', Jupiter: '♃', Saturn: '♄', Uranus: '♅',
  Neptune: '♆', Pluto: '♇', Chiron: '⚷',
  'True Node': '☊', 'South Node': '☋',
  Ceres: '⚳', Eris: '⯰', Lilith: '⚸',
};
const ASPECT_GLYPHS = {
  conjunction: '☌', opposition: '☍', trine: '△',
  square: '□', sextile: '✱', quincunx: '⊻',
  semisextile: '⌵', semisquare: '∠', sesquisquare: '⚼',
};

// ---------------------------------------------------------------------------
// Style helpers
// ---------------------------------------------------------------------------

function ptHalfPoints(pt) { return pt * 2; }

function styleColors(style) { return style.colors || {}; }
function styleFonts(style) { return style.fonts || {}; }
function styleSizes(style) { return style.font_sizes_pt || {}; }

// Resolve a payload into a flat style object with the requested theme's
// colors lifted into `style.colors` and `style.page_bg` set for the page
// background. Both `payload.theme` and `style.default_theme` are honored,
// in that order, with a final fallback to "light".
function resolveStyle(payload) {
  const raw = payload.style || {};
  const themeName = payload.theme || raw.default_theme || 'light';
  const themes = raw.themes || {};
  const theme = themes[themeName] || themes.light || {};
  return {
    ...raw,
    colors: theme,
    page_bg: theme.page_bg,
    _theme: themeName,
  };
}

function bodyRun(text, style, opts) {
  return new TextRun({
    text: String(text),
    font: styleFonts(style).body,
    size: ptHalfPoints(styleSizes(style).body || 11),
    bold: opts?.bold || false,
    italics: opts?.italics || false,
    color: opts?.color || styleColors(style).text || '000000',
  });
}

function bodyPara(text, style, opts) {
  const runs = Array.isArray(text)
    ? text.map((r) => (r instanceof TextRun ? r : bodyRun(r, style)))
    : [bodyRun(text, style, opts)];
  return new Paragraph({
    children: runs,
    spacing: { before: 60, after: 60 },
    alignment: opts?.alignment,
  });
}

function heading(text, level, style) {
  const sizes = styleSizes(style);
  const colors = styleColors(style);
  const sizeMap = { 1: sizes.h1, 2: sizes.h2, 3: sizes.h3 };
  const colorMap = { 1: colors.heading, 2: colors.heading, 3: colors.subheading };
  const headingLevelMap = {
    1: HeadingLevel.HEADING_1,
    2: HeadingLevel.HEADING_2,
    3: HeadingLevel.HEADING_3,
  };
  return new Paragraph({
    heading: headingLevelMap[level],
    spacing: { before: 240, after: 120 },
    children: [
      new TextRun({
        text: String(text),
        font: styleFonts(style).heading,
        size: ptHalfPoints(sizeMap[level] || sizes.body || 11),
        bold: true,
        color: colorMap[level] || colors.text || '000000',
      }),
    ],
  });
}

function titlePara(text, style) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 240 },
    children: [
      new TextRun({
        text: String(text),
        font: styleFonts(style).heading,
        size: ptHalfPoints(styleSizes(style).title || 28),
        bold: true,
        color: styleColors(style).title || '1F2A4A',
      }),
    ],
  });
}

function kvPara(label, value, style) {
  return new Paragraph({
    spacing: { before: 40, after: 40 },
    children: [
      bodyRun(`${label}: `, style, { bold: true, color: styleColors(style).subheading || '3D5285' }),
      bodyRun(value, style),
    ],
  });
}

// ---------------------------------------------------------------------------
// Table helpers
// ---------------------------------------------------------------------------

const NO_BORDER = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const THIN_BORDER = { style: BorderStyle.SINGLE, size: 4, color: 'B8B4C8' };

function tableCell(text, style, opts) {
  const colors = styleColors(style);
  const fonts = styleFonts(style);
  const sizes = styleSizes(style);
  const isHeader = opts?.header;
  const altRow = opts?.altRow;
  const bg = isHeader ? colors.table_header_bg : (altRow ? colors.table_alt_row_bg : undefined);
  const fg = isHeader
    ? (colors.table_header_fg || 'FFFFFF')
    : (colors.table_row_fg || colors.text || '000000');
  return new TableCell({
    shading: bg ? { type: ShadingType.CLEAR, color: 'auto', fill: bg } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [
      new Paragraph({
        spacing: { before: 0, after: 0 },
        alignment: opts?.alignment,
        children: [
          new TextRun({
            text: String(text == null ? '' : text),
            font: fonts.body,
            size: ptHalfPoints(sizes.table || 10),
            bold: !!isHeader,
            color: fg,
          }),
        ],
      }),
    ],
  });
}

function buildTable(headers, rows, style) {
  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((h) => tableCell(h, style, { header: true })),
  });
  const bodyRows = rows.map((row, i) =>
    new TableRow({
      children: row.map((cell) => tableCell(cell, style, { altRow: i % 2 === 1 })),
    })
  );
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: [headerRow, ...bodyRows],
  });
}

// ---------------------------------------------------------------------------
// Position formatting (mirrors render_md._planet_row)
// ---------------------------------------------------------------------------

function formatPos(entry) {
  const signGlyph = SIGN_GLYPHS[entry.sign] || '';
  let pos = `${entry.degree}° ${signGlyph} ${entry.sign} ${String(entry.minute).padStart(2, '0')}'`;
  if (entry.retrograde) pos += ' R';
  return pos;
}

function bodyLabel(name) {
  const g = PLANET_GLYPHS[name];
  return g ? `${g} ${name}` : name;
}

function aspectLabel(name) {
  const g = ASPECT_GLYPHS[name];
  return g ? `${g} ${name}` : name;
}

function formatOrb(orbDeg) {
  let deg = Math.floor(orbDeg);
  let mins = Math.round((orbDeg - deg) * 60);
  if (mins === 60) { mins = 0; deg += 1; }
  return `${deg}°${String(mins).padStart(2, '0')}'`;
}

// ---------------------------------------------------------------------------
// Markdown → docx-js (for interpretation section bodies)
// ---------------------------------------------------------------------------

// Walk marked inline tokens (within a paragraph or list item) into a flat
// list of TextRun / ExternalHyperlink children suitable for Paragraph.children.
// Honors **strong**, *em*, `code`, ~~del~~, and [link](url). Nested emphasis
// is flattened by carrying bold/italic/code flags through recursion.
function inlineRuns(tokens, style, opts) {
  opts = opts || {};
  const colors = styleColors(style);
  const fonts = styleFonts(style);
  const sizes = styleSizes(style);
  const out = [];
  for (const tk of tokens || []) {
    switch (tk.type) {
      case 'text':
      case 'escape':
        out.push(new TextRun({
          text: tk.text,
          font: opts.code ? (fonts.mono || fonts.body) : fonts.body,
          size: ptHalfPoints(sizes.body || 11),
          bold: !!opts.bold,
          italics: !!opts.italic,
          strike: !!opts.strike,
          color: colors.text || '000000',
        }));
        break;
      case 'strong':
        out.push(...inlineRuns(tk.tokens, style, { ...opts, bold: true }));
        break;
      case 'em':
        out.push(...inlineRuns(tk.tokens, style, { ...opts, italic: true }));
        break;
      case 'codespan':
        out.push(new TextRun({
          text: tk.text,
          font: fonts.mono || fonts.body,
          size: ptHalfPoints(sizes.body || 11),
          color: colors.accent || colors.text || '000000',
        }));
        break;
      case 'del':
        out.push(...inlineRuns(tk.tokens, style, { ...opts, strike: true }));
        break;
      case 'link': {
        const linkRuns = inlineRuns(tk.tokens, style, opts).map((r) => {
          // Hyperlink color overrides text color, but only for non-styled runs.
          if (r instanceof TextRun) {
            // Rebuild with hyperlink color; docx-js TextRun has no .options getter,
            // so create a fresh one rather than trying to mutate.
            return new TextRun({
              text: tk.tokens?.map((t) => t.raw || t.text).join('') || tk.text,
              font: fonts.body,
              size: ptHalfPoints(sizes.body || 11),
              bold: !!opts.bold,
              italics: !!opts.italic,
              color: colors.subheading || '3D5285',
              underline: { type: 'single' },
            });
          }
          return r;
        });
        out.push(new ExternalHyperlink({ link: tk.href, children: linkRuns }));
        break;
      }
      case 'image':
        // Future media support: embed image bytes. For now leave a textual
        // placeholder so authors can mark up image insertion points today.
        out.push(new TextRun({
          text: `[image: ${tk.text || tk.href}]`,
          font: fonts.body,
          size: ptHalfPoints(sizes.body || 11),
          italics: true,
          color: colors.accent || colors.text || '000000',
        }));
        break;
      case 'br':
        out.push(new TextRun({ text: '', break: 1 }));
        break;
      case 'html':
        // Strip HTML — markdown allows raw HTML but docx can't host it directly.
        break;
      default:
        // Unknown inline token: fall back to raw text so nothing is silently dropped.
        if (typeof tk.text === 'string') {
          out.push(new TextRun({
            text: tk.text,
            font: fonts.body,
            size: ptHalfPoints(sizes.body || 11),
            color: colors.text || '000000',
          }));
        }
    }
  }
  return out;
}

// Convert a markdown string to an array of docx-js block children.
// Supports: paragraphs, headings (forced to h3 so the section's h2 stays
// dominant), bullet/ordered lists, blockquotes, code blocks, hr.
function markdownToDocx(md, style) {
  if (!md || typeof md !== 'string') return [];
  const fonts = styleFonts(style);
  const sizes = styleSizes(style);
  const colors = styleColors(style);
  const tokens = new Lexer().lex(md);
  const out = [];
  for (const tk of tokens) {
    switch (tk.type) {
      case 'space':
        break;
      case 'paragraph':
        out.push(new Paragraph({
          spacing: { before: 80, after: 80 },
          children: inlineRuns(tk.tokens, style),
        }));
        break;
      case 'heading':
        // Force any in-body heading to h3 — the section's heading is already h2.
        out.push(new Paragraph({
          heading: HeadingLevel.HEADING_3,
          spacing: { before: 200, after: 80 },
          children: [
            new TextRun({
              text: tk.text,
              font: fonts.heading,
              size: ptHalfPoints(sizes.h3 || 12),
              bold: true,
              color: colors.subheading || colors.text || '000000',
            }),
          ],
        }));
        break;
      case 'list': {
        const ordered = !!tk.ordered;
        tk.items.forEach((item, idx) => {
          // Each item may contain inline tokens or nested block tokens.
          // Render as a single paragraph with bullet/number prefix; nested
          // blocks beyond the first paragraph are flattened to inline.
          const prefix = ordered ? `${(tk.start || 1) + idx}. ` : '• ';
          const inline = (item.tokens || []).flatMap((sub) => {
            if (sub.type === 'text' && sub.tokens) return sub.tokens;
            if (sub.type === 'paragraph') return sub.tokens || [];
            if (sub.tokens) return sub.tokens;
            return [{ type: 'text', text: sub.text || sub.raw || '' }];
          });
          out.push(new Paragraph({
            spacing: { before: 40, after: 40 },
            indent: { left: 360 },
            children: [
              new TextRun({
                text: prefix,
                font: fonts.body,
                size: ptHalfPoints(sizes.body || 11),
                color: colors.text || '000000',
              }),
              ...inlineRuns(inline, style),
            ],
          }));
        });
        break;
      }
      case 'blockquote':
        // Lex the inner markdown and render with italics + indent.
        for (const inner of markdownToDocx(tk.text, style)) {
          // Mutating inner paragraphs to add indent is awkward; rebuild lightly.
          out.push(new Paragraph({
            spacing: { before: 60, after: 60 },
            indent: { left: 720 },
            children: (inner.options?.children || []).map((r) => r),
          }));
        }
        break;
      case 'code':
        out.push(new Paragraph({
          spacing: { before: 80, after: 80 },
          indent: { left: 360 },
          children: [
            new TextRun({
              text: tk.text,
              font: fonts.mono || fonts.body,
              size: ptHalfPoints((sizes.body || 11) - 1),
              color: colors.text || '000000',
            }),
          ],
        }));
        break;
      case 'hr':
        out.push(new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 120, after: 120 },
          children: [
            new TextRun({
              text: '—  —  —',
              font: fonts.body,
              size: ptHalfPoints(sizes.body || 11),
              color: colors.rule || colors.text || '000000',
            }),
          ],
        }));
        break;
      case 'html':
        // Strip raw HTML.
        break;
      default:
        if (typeof tk.text === 'string') {
          out.push(new Paragraph({
            spacing: { before: 60, after: 60 },
            children: [new TextRun({
              text: tk.text,
              font: fonts.body,
              size: ptHalfPoints(sizes.body || 11),
              color: colors.text || '000000',
            })],
          }));
        }
    }
  }
  return out;
}

// Build the "## Interpretation" section + each named subsection. Appended
// AFTER all chart data so number-only readers can stop scrolling at the data.
function renderInterpretation(interp, style) {
  if (!interp || !Array.isArray(interp.sections) || interp.sections.length === 0) {
    return [];
  }
  const out = [];
  out.push(heading('Interpretation', 1, style));
  for (const section of interp.sections) {
    if (section.heading) {
      out.push(heading(section.heading, 2, style));
    }
    if (section.body) {
      out.push(...markdownToDocx(section.body, style));
    }
  }
  return out;
}


// ---------------------------------------------------------------------------
// Per-kind renderers
// ---------------------------------------------------------------------------

function renderNatal(chart, style) {
  const children = [];
  const b = chart.birth || {};
  const place = b.place_label || `${b.lat?.toFixed(4)}, ${b.lon?.toFixed(4)}`;
  children.push(titlePara(`${chart.display_name} — Western Tropical Natal Chart`, style));
  children.push(kvPara('Born', `${b.date} ${b.time} (${b.tz}) — ${place}`, style));
  children.push(kvPara('UT', `${chart.ut_iso}  ·  JD (UT) ${Number(chart.julian_day_ut).toFixed(4)}`, style));
  children.push(kvPara('Zodiac', `tropical  ·  House system: ${chart.house_system}`, style));

  if (chart.angles && chart.angles.length) {
    children.push(heading('Angles', 1, style));
    const rows = chart.angles.map((a) => [a.name, formatPos(a)]);
    children.push(buildTable(['Angle', 'Position'], rows, style));
  }

  children.push(heading('Planets and Points', 1, style));
  const planetRows = (chart.planets || []).map((p) => [
    bodyLabel(p.name) + (isKeplerianSource(p.source) ? ' *' : ''),
    formatPos(p),
    p.house != null ? String(p.house) : '—',
  ]);
  children.push(buildTable(['Body', 'Position', 'House'], planetRows, style));

  if ((chart.planets || []).some((p) => isKeplerianSource(p.source))) {
    children.push(bodyPara(
      '* Computed via bundled Keplerian elements (Swiss Ephemeris asteroid file unavailable). ' +
      'Accuracy: ±arcminutes for Ceres/Eris; ±1–2° for Chiron because Saturn perturbations preclude ' +
      'better single-element-set fits over multi-decade ranges.',
      style, { italics: true }
    ));
  }

  if (chart.aspects && chart.aspects.length) {
    children.push(heading('Notable Aspects', 1, style));
    const top = chart.aspects.slice(0, 25);
    const rows = top.map((a) => [a.a, aspectLabel(a.aspect), a.b, formatOrb(a.orb_deg)]);
    children.push(buildTable(['A', 'Aspect', 'B', 'Orb'], rows, style));
  }

  if (chart.notes && chart.notes.length) {
    children.push(heading('Notes', 1, style));
    chart.notes.forEach((n) => children.push(bodyPara(`• ${n}`, style)));
  }

  return children;
}

function isKeplerianSource(src) {
  return typeof src === 'string' && src.startsWith('keplerian');
}

function renderSynastry(rpt, style) {
  const children = [];
  children.push(titlePara(`Synastry — ${rpt.person_a} × ${rpt.person_b}`, style));
  children.push(bodyPara(
    'Western tropical inter-aspects + house overlays in both directions, including ' +
    'Chiron, Ceres, Lilith, Eris (per spec D6).',
    style
  ));

  for (const [label, ch] of [['A: ' + rpt.person_a, rpt.chart_a], ['B: ' + rpt.person_b, rpt.chart_b]]) {
    children.push(heading(label, 1, style));
    const rows = [];
    for (const p of (ch.planets || [])) {
      rows.push([bodyLabel(p.name), formatPos(p)]);
    }
    for (const a of (ch.angles || [])) {
      if (a.name === 'Ascendant' || a.name === 'Midheaven') {
        rows.push([a.name, formatPos(a)]);
      }
    }
    children.push(buildTable(['Body', 'Position'], rows, style));
  }

  children.push(heading('Cross-aspects (tightest first)', 1, style));
  const top = (rpt.aspects || []).slice(0, 30);
  children.push(buildTable(
    [rpt.person_a, 'Aspect', rpt.person_b, 'Orb'],
    top.map((a) => [a.a_body, aspectLabel(a.aspect), a.b_body, formatOrb(a.orb_deg)]),
    style,
  ));

  if (rpt.overlays_a_in_b && rpt.overlays_a_in_b.length) {
    children.push(heading(`${rpt.person_a}'s planets in ${rpt.person_b}'s houses`, 2, style));
    children.push(buildTable(['Body', 'House'], rpt.overlays_a_in_b.map((o) => [o.body, String(o.house)]), style));
  }
  if (rpt.overlays_b_in_a && rpt.overlays_b_in_a.length) {
    children.push(heading(`${rpt.person_b}'s planets in ${rpt.person_a}'s houses`, 2, style));
    children.push(buildTable(['Body', 'House'], rpt.overlays_b_in_a.map((o) => [o.body, String(o.house)]), style));
  }

  return children;
}

function renderComposite(comp, style) {
  const children = [];
  const title = comp.method === 'davison' ? 'Davison' : 'Midpoint Composite';
  children.push(titlePara(`${title} — ${comp.person_a} & ${comp.person_b}`, style));
  if (comp.method === 'davison' && comp.moment) {
    const m = comp.moment;
    children.push(bodyPara(
      `Cast for the temporal/spatial midpoint: ${m.ut_datetime} at lat ${m.lat.toFixed(2)}°, lon ${m.lon.toFixed(2)}°.`,
      style,
    ));
  } else {
    children.push(bodyPara('Per-pair shorter-arc midpoints; equal-house from composite Ascendant.', style));
  }

  if (comp.angles && comp.angles.length) {
    children.push(heading('Angles', 1, style));
    children.push(buildTable(
      ['Angle', 'Position'],
      comp.angles.map((a) => [a.name, formatPos(a)]),
      style,
    ));
  }

  children.push(heading('Bodies', 1, style));
  children.push(buildTable(
    ['Body', 'Position', 'House'],
    (comp.points || []).map((p) => [
      bodyLabel(p.name),
      formatPos(p),
      p.house != null ? String(p.house) : '—',
    ]),
    style,
  ));

  if (comp.aspects && comp.aspects.length) {
    children.push(heading('Internal Aspects (tightest first)', 1, style));
    children.push(buildTable(
      ['A', 'Aspect', 'B', 'Orb'],
      comp.aspects.slice(0, 20).map((a) => [a.a, aspectLabel(a.aspect), a.b, formatOrb(a.orb_deg)]),
      style,
    ));
  }

  if (comp.notes && comp.notes.length) {
    children.push(heading('Notes', 1, style));
    comp.notes.forEach((n) => children.push(bodyPara(`• ${n}`, style)));
  }

  return children;
}

// ---------------------------------------------------------------------------
// Document assembly
// ---------------------------------------------------------------------------

function detectKind(chart) {
  if (chart.overlays_a_in_b !== undefined) return 'synastry';
  if (chart.method !== undefined && chart.points !== undefined) return 'composite';
  if (chart.planets !== undefined && chart.display_name !== undefined) return 'natal';
  throw new Error('Cannot detect chart kind from payload shape.');
}

function footerFor(label, style) {
  const colors = styleColors(style);
  const footerColor = colors.accent || '8B6F47';
  const footerSize = ptHalfPoints(styleSizes(style).footer || 9);
  return new Footer({
    children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({
            text: `${label}  ·  page `,
            font: styleFonts(style).body,
            size: footerSize,
            color: footerColor,
          }),
          new TextRun({ children: [PageNumber.CURRENT], size: footerSize, color: footerColor }),
          new TextRun({ text: ' of ', size: footerSize, color: footerColor }),
          new TextRun({ children: [PageNumber.TOTAL_PAGES], size: footerSize, color: footerColor }),
        ],
      }),
    ],
  });
}

function buildDocument(payload) {
  const { kind, chart } = payload;
  const style = resolveStyle(payload);
  const k = kind || detectKind(chart);
  let children;
  let footerLabel;
  if (k === 'natal') {
    children = renderNatal(chart, style);
    footerLabel = `${chart.display_name} — Natal`;
  } else if (k === 'synastry') {
    children = renderSynastry(chart, style);
    footerLabel = `Synastry: ${chart.person_a} × ${chart.person_b}`;
  } else if (k === 'composite') {
    children = renderComposite(chart, style);
    footerLabel = `${chart.method === 'davison' ? 'Davison' : 'Composite'}: ${chart.person_a} & ${chart.person_b}`;
  } else {
    throw new Error(`Unknown kind: ${k}`);
  }

  // Interpretation (if any) is always appended after the chart data so that
  // readers who only want numbers can stop scrolling at the end of the
  // Aspects table.
  if (payload.interpretation) {
    children = children.concat(renderInterpretation(payload.interpretation, style));
  }

  const margins = style.margins_twips || {};
  const docOpts = {
    creator: 'group-synastry',
    description: footerLabel,
    sections: [{
      properties: {
        page: {
          margin: {
            top: margins.top || 1080,
            right: margins.right || 1080,
            bottom: margins.bottom || 1080,
            left: margins.left || 1080,
          },
        },
      },
      footers: { default: footerFor(footerLabel, style) },
      children,
    }],
  };
  if (style.page_bg) {
    docOpts.background = { color: style.page_bg };
  }
  return new Document(docOpts);
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => { data += chunk; });
    process.stdin.on('end', () => resolve(data));
    process.stdin.on('error', reject);
  });
}

function parseArgs(argv) {
  const out = { out: null };
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === '--out' && i + 1 < argv.length) { out.out = argv[++i]; }
  }
  return out;
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args.out) {
    process.stderr.write('render_docx.js: --out <path> is required\n');
    process.exit(2);
  }
  const raw = await readStdin();
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch (e) {
    process.stderr.write(`render_docx.js: invalid JSON on stdin: ${e.message}\n`);
    process.exit(2);
  }
  const doc = buildDocument(payload);
  const buf = await Packer.toBuffer(doc);
  fs.writeFileSync(args.out, buf);
}

main().catch((e) => {
  process.stderr.write(`render_docx.js: ${e.stack || e.message || e}\n`);
  process.exit(1);
});
