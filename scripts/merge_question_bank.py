"""
Merge PDF questions with scraped BAMF answers into questions.json.

Expects these files in the repo root (produced by the other two scripts):
  question_bank_from_pdf.json  – questions + options, no correct answers
  answers_general.json         – correct answers for questions 1-300
  state_answers_<State>.json   – correct answers for each state section (×16)

Writes:
  questions.json               – final merged file served by index.html
"""
import json
import glob
import os
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

pdf_questions  = json.loads((ROOT / 'question_bank_from_pdf.json').read_text(encoding='utf-8'))
general_answers = {
    item['number']: item
    for item in json.loads((ROOT / 'answers_general.json').read_text(encoding='utf-8'))
}

state_answers = {}
for path in glob.glob(str(ROOT / 'state_answers_*.json')):
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    safe = os.path.basename(path)[len('state_answers_'):-len('.json')]
    state_name = safe.replace('_', ' ')
    # Repair German state names that lost special characters in filenames
    fixes = {
        'Baden Württemberg':    'Baden-Württemberg',
        'Mecklenburg Vorpommern': 'Mecklenburg-Vorpommern',
        'Nordrhein Westfalen':  'Nordrhein-Westfalen',
        'Rheinland Pfalz':      'Rheinland-Pfalz',
        'Sachsen Anhalt':       'Sachsen-Anhalt',
        'Schleswig Holstein':   'Schleswig-Holstein',
    }
    state_name = fixes.get(state_name, state_name)
    state_answers[state_name] = {301 + i: item for i, item in enumerate(raw)}

# Normalize Thüringen if filename encoding was mangled
if 'Thüringen' not in state_answers:
    for k in list(state_answers):
        if 'Th' in k and 'ringen' in k:
            state_answers['Thüringen'] = state_answers[k]

for q in pdf_questions:
    if q['category'] == 'general':
        ans = general_answers.get(q['number'])
    else:
        ans = state_answers.get(q['state'], {}).get(300 + q['localNumber'])

    if not ans:
        q['correctIndex'] = None
        q['imageUrl'] = None
    else:
        q['correctIndex'] = ans['correctIndex']
        q['imageUrl'] = ans.get('imageUrl')
        if len(ans.get('options', [])) == 4:
            q['officialOptions'] = ans['options']

out = ROOT / 'questions.json'
out.write_text(json.dumps(pdf_questions, ensure_ascii=False, indent=2), encoding='utf-8')

missing = [q for q in pdf_questions if q['correctIndex'] is None]
print(f'total:   {len(pdf_questions)}')
print(f'missing: {len(missing)}')
print(f'saved:   {out}')
if missing:
    print('sample missing:', [q["number"] for q in missing[:5]])
