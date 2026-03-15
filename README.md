# Einbürgerungstest Simulator

A free, open-source practice simulator for the official German citizenship test (*Einbürgerungstest*).
All 460 questions — 300 general + 10 per state — sourced directly from the official [BAMF question catalogue](https://www.bamf.de/DE/Themen/Integration/ZugewanderteTeilnehmende/Einbuergerung/einbuergerung-node.html).

**[→ Open the simulator](https://koyto7.github.io/einburgerungstest-simulator/)**

Features:
- Full exam simulation (33 random questions, 60-minute timer)
- State-specific questions for all 16 German states
- Error tracking and learning history (stored locally in your browser)
- Dark mode
- No account, no tracking, no server

---

## Local development

The app is a single `index.html` that fetches `questions.json` at runtime.
Because of browser CORS restrictions, a local HTTP server is required (not `file://`):

```bash
python3 -m http.server 8080
# then open http://localhost:8080
```

---

## How questions.json is kept up to date

A GitHub Actions workflow runs on the **1st of every month** and automatically:

1. Downloads the latest official BAMF PDF
2. Parses all questions from it
3. Scrapes the correct answers from [oet.bamf.de](https://oet.bamf.de)
4. Merges everything into `questions.json`
5. Commits and pushes the updated file

You can also trigger it manually from the **Actions** tab → **Update questions.json** → **Run workflow**.

---

## Regenerating questions.json manually

### Prerequisites

```bash
# Node dependencies (Playwright)
npm install
npx playwright install chromium

# Python dependencies (PyMuPDF via uv)
pip install uv
uv sync
```

### Run the pipeline

```bash
# 1. Download PDF and extract questions (saves question_bank_from_pdf.json)
uv run python scripts/parse_pdf_questions.py

# 2. Scrape correct answers for general questions 1–300
npm run scrape:general

# 3. Scrape correct answers for each state (10 questions each)
for state in "Baden-Württemberg" "Bayern" "Berlin" "Brandenburg" "Bremen" \
             "Hamburg" "Hessen" "Mecklenburg-Vorpommern" "Niedersachsen" \
             "Nordrhein-Westfalen" "Rheinland-Pfalz" "Saarland" "Sachsen" \
             "Sachsen-Anhalt" "Schleswig-Holstein" "Thüringen"; do
  safe="${state// /_}"
  node scripts/extract_answers_chunked.js "$state" 1 10 "./state_answers_${safe}.json"
done

# 4. Merge everything → questions.json
npm run merge
```

The scraping step takes 40–80 minutes depending on network speed (one browser request per question).

---

## Project structure

```
index.html                          # The app — fetches questions.json at runtime
questions.json                      # Question bank (committed, updated monthly by CI)
scripts/
  parse_pdf_questions.py            # Download PDF + extract questions
  extract_answers_chunked.js        # Scrape correct answers from oet.bamf.de
  update_questions.py               # Diff-based update: merge, compare, validate, apply
  validate_questions.py             # Quality checks for questions.json
.github/workflows/
  update-questions.yml              # Monthly CI workflow
```

---

## Data sources

Questions and answers are sourced from official German government resources:

- **Question catalogue (PDF):** [BAMF Gesamtfragenkatalog](https://www.bamf.de/SharedDocs/Anlagen/DE/Integration/Einbuergerung/gesamtfragenkatalog-lebenindeutschland.pdf?__blob=publicationFile&v=23)
- **Online test portal:** [oet.bamf.de](https://oet.bamf.de/ords/oetut/f?p=514:1:0)

These are public government documents made available for the purpose of helping people prepare for the citizenship test.

---

## Contributing

Pull requests are welcome. If the BAMF website changes its HTML structure and the scraper breaks, please open an issue or submit a fix to `scripts/extract_answers_chunked.js`.

## License

MIT — see [LICENSE](LICENSE).
