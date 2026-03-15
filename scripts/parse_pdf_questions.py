"""
Parse the official BAMF question catalogue PDF into question_bank_from_pdf.json.
Downloads the PDF from the official BAMF URL if not already present locally.
"""
import fitz
import re
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
PDF_PATH = ROOT / 'gesamtfragenkatalog-lebenindeutschland.pdf'
OUT_PATH = ROOT / 'question_bank_from_pdf.json'

PDF_URL = (
    'https://www.bamf.de/SharedDocs/Anlagen/DE/Integration/Einbuergerung/'
    'gesamtfragenkatalog-lebenindeutschland.pdf'
    '?__blob=publicationFile&v=23'
)

if not PDF_PATH.exists():
    print(f'Downloading PDF from BAMF…')
    urllib.request.urlretrieve(PDF_URL, PDF_PATH)
    print(f'Saved to {PDF_PATH}')

pdf = fitz.open(PDF_PATH)
full_text = []
for i in range(1, len(pdf)):
    text = pdf[i].get_text('text')
    full_text.append(text)

text = '\n'.join(full_text)
text = text.replace('\u00a0', ' ')
text = re.sub(r'Seite \d+ von 191', '', text)
text = re.sub(r'\n{3,}', '\n\n', text)

state_headers = [
    'Fragen für das Bundesland Baden-Württemberg',
    'Fragen für das Bundesland Bayern',
    'Fragen für das Bundesland Berlin',
    'Fragen für das Bundesland Brandenburg',
    'Fragen für das Bundesland Bremen',
    'Fragen für das Bundesland Hamburg',
    'Fragen für das Bundesland Hessen',
    'Fragen für das Bundesland Mecklenburg-Vorpommern',
    'Fragen für das Bundesland Niedersachsen',
    'Fragen für das Bundesland Nordrhein-Westfalen',
    'Fragen für das Bundesland Rheinland-Pfalz',
    'Fragen für das Bundesland Saarland',
    'Fragen für das Bundesland Sachsen',
    'Fragen für das Bundesland Sachsen-Anhalt',
    'Fragen für das Bundesland Schleswig-Holstein',
    'Fragen für das Bundesland Thüringen',
]

state_map = {
    'Fragen für das Bundesland Baden-Württemberg': 'Baden-Württemberg',
    'Fragen für das Bundesland Bayern': 'Bayern',
    'Fragen für das Bundesland Berlin': 'Berlin',
    'Fragen für das Bundesland Brandenburg': 'Brandenburg',
    'Fragen für das Bundesland Bremen': 'Bremen',
    'Fragen für das Bundesland Hamburg': 'Hamburg',
    'Fragen für das Bundesland Hessen': 'Hessen',
    'Fragen für das Bundesland Mecklenburg-Vorpommern': 'Mecklenburg-Vorpommern',
    'Fragen für das Bundesland Niedersachsen': 'Niedersachsen',
    'Fragen für das Bundesland Nordrhein-Westfalen': 'Nordrhein-Westfalen',
    'Fragen für das Bundesland Rheinland-Pfalz': 'Rheinland-Pfalz',
    'Fragen für das Bundesland Saarland': 'Saarland',
    'Fragen für das Bundesland Sachsen': 'Sachsen',
    'Fragen für das Bundesland Sachsen-Anhalt': 'Sachsen-Anhalt',
    'Fragen für das Bundesland Schleswig-Holstein': 'Schleswig-Holstein',
    'Fragen für das Bundesland Thüringen': 'Thüringen',
}

# split sections
positions = []
for header in state_headers:
    idx = text.find(header)
    if idx != -1:
        positions.append((idx, header))
positions.sort()

if not positions:
    raise RuntimeError('No state headers found in PDF – the PDF layout may have changed.')

general_text = text[:positions[0][0]]
state_sections = []
for i, (pos, header) in enumerate(positions):
    end = positions[i+1][0] if i+1 < len(positions) else len(text)
    state_sections.append((state_map[header], text[pos:end]))

question_re = re.compile(r'Aufgabe\s+(\d+)\s*\n')


def normalize_spaces(s):
    s = s.replace(' / ', '/')
    s = re.sub(r'\s+([.,;:!?…])', r'\1', s)
    s = re.sub(r'\s{2,}', ' ', s)
    s = re.sub(r' ?\n ?', '\n', s)
    return s.strip()


def parse_section(section_text, category, state=None, id_offset=0, reset_local_numbers=False):
    parts = list(question_re.finditer(section_text))
    items = []
    for idx, m in enumerate(parts):
        start = m.start()
        end = parts[idx+1].start() if idx+1 < len(parts) else len(section_text)
        block = section_text[start:end].strip()
        local_num = idx + 1 if reset_local_numbers else int(m.group(1))
        lines = [ln.strip() for ln in block.splitlines()]
        if lines and lines[0].startswith('Aufgabe'):
            lines = lines[1:]
        lines = [ln for ln in lines if ln not in ('Teil I', 'Allgemeine Fragen', 'Teil II') and not ln.startswith('Fragen für')]
        question_lines = []
        option_lines = []
        in_options = False
        buffer_option = None
        for ln in lines:
            if not ln:
                continue
            if ln == '':
                in_options = True
                if buffer_option is not None:
                    option_lines.append(buffer_option.strip())
                    buffer_option = None
                continue
            if not in_options:
                question_lines.append(ln)
            else:
                if buffer_option is None:
                    buffer_option = ln
                else:
                    if len(option_lines) >= 3:
                        buffer_option += ' ' + ln
                    else:
                        if buffer_option.endswith(('/', 'der', 'die', 'das', 'den', 'dem', 'des', 'einen', 'einem', 'einer', 'eines', 'einem', 'mit', 'von', 'auf', 'bei', 'zu', 'im', 'in', 'am', 'vom', 'für', 'und', 'oder', 'einer/einen', 'Kandidatin/einen', 'Grundrecht', 'heißt', '…')) or ln[:1].islower() or ln.startswith(('und ', 'oder ', 'im ', 'in ', 'am ', 'bei ', 'mit ', 'von ', 'zu ', 'weder ', 'bestimmten ', 'nicht ', 'nur ', 'alle ', 'hier ')):
                            buffer_option += ' ' + ln
                        else:
                            option_lines.append(buffer_option.strip())
                            buffer_option = ln
        if buffer_option is not None:
            option_lines.append(buffer_option.strip())
        option_lines = option_lines[:4]
        item = {
            'id': id_offset + local_num,
            'number': id_offset + local_num,
            'localNumber': local_num,
            'category': category,
            'state': state,
            'question': normalize_spaces(' '.join(question_lines)),
            'options': [normalize_spaces(o) for o in option_lines],
        }
        items.append(item)
    return items


general_items = parse_section(general_text, 'general', None, 0)
state_items = []
offset = 300
for state, sec in state_sections:
    parsed = parse_section(sec, 'state', state, offset, reset_local_numbers=True)
    for i, item in enumerate(parsed, start=1):
        item['id'] = offset + i
        item['number'] = offset + i
        item['localNumber'] = i
    state_items.extend(parsed)
    offset += 10

all_items = general_items + state_items

for item in all_items:
    if item['question'].endswith('Bild 4'):
        item['question'] = re.sub(r' Bild 1 Bild 2 Bild 3 Bild 4$', '', item['question']).strip()
    item['isImageQuestion'] = item['question'].startswith('Welches Wappen gehört') or item['question'].startswith('Welches Bundesland ist')

with open(OUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(all_items, f, ensure_ascii=False, indent=2)

print(f'general: {len(general_items)}')
print(f'state:   {len(state_items)}')
print(f'total:   {len(all_items)}')
print(f'saved:   {OUT_PATH}')
