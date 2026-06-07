# Mealie AI Importer

> 🇩🇪 [Deutsche Version](README.de.md)

---

## ⚠️ About This Project

This is a **private vibe-coding project** — I have not written or read a single line of code myself; the entire implementation was created in dialogue with Claude (Anthropic). Therefore, I am unfortunately unable to provide support, answer questions about the implementation, or make changes or improvements.

You are welcome to **fork** this project and use it as a starting point for your own work. However, I am unable to accept pull requests.

---

## Motivation

I faced the challenge of importing a recipe collection of around **1,000 PDF files** into [Mealie](https://mealie.io). I quickly realised that Mealie only reaches its full potential when the many fields for ingredient and recipe data are **filled in completely and carefully** — singular and plural forms of ingredients and units, aliases, categories, tags, images, and more. Doing this manually for 1,000 recipes was simply impossible. Hence this importer.

---

## What Is the Mealie AI Importer?

A self-developed tool that **automatically imports recipes from PDF files** into Mealie. It uses **artificial intelligence** (Claude by Anthropic) and the official **Mealie REST API** to recognise ingredients, quantities, units, and preparation steps from the PDF, match them against existing data — and fills in **all relevant fields** that Mealie offers for a high-quality recipe database.

### What Makes It Special?

- **Complete ingredient database**: For every new ingredient, singular, plural, and aliases are created. This produces a largely **duplicate-free ingredient database** and ensures that Mealie's quantity-scaling feature works correctly in language too ("1 carrot" vs. "2 carrots").
- **Complete unit management**: Units are created with singular, plural, and abbreviation (e.g. "tablespoon / tablespoons / tbsp").
- **Automatic classification**: Every recipe is automatically assigned a category and matching tags.
- **Images**: Automatic detection of recipe images in the PDF, upload of custom images with a built-in **cropping tool**.
- **Original PDF as attachment**: The source PDF is automatically saved as a file attachment on the recipe in Mealie.
- **Appetising description**: Claude automatically writes an appealing short description for each recipe.
- **Ingredient-to-step assignment**: The AI assigns ingredients to their respective preparation steps — the foundation for Mealie's step-by-step cooking view.
- **Full Mealie API integration**: The tool exclusively uses the official Mealie REST API.

---

## Workflow

```
📄 Upload PDF
      ↓
🤖 AI analysis (Claude extracts all recipe data)
      ↓
🔍 Automatic matching against existing Mealie data
   (ingredients, units, categories, tags)
      ↓
👁️ Review & fine-tune (interactive interface)
      ↓
✅ Transfer to Mealie via the official API
```

The entire process typically takes **2–4 minutes** per recipe.

---

## Category & Tag System

The tool works with the category and tag system configured in the respective Mealie instance. The assignment is done fully automatically by the AI based on the available options — no configuration is required.

A complete overview of the system used in this project (recipe categories, food categories, tag groups) can be found in 📄 [CATEGORIES.md](CATEGORIES.md).

---

## Analysis Features in Detail

### 1. PDF Extraction

The tool reads the **embedded text** directly from the PDF file (searchable PDF). It does not perform its own OCR — the PDF must contain an embedded text layer. Scanned recipe books without text recognition are not supported. Multi-page PDFs are fully processed.

### 2. AI Recipe Analysis

The AI analyses the extracted text and creates the complete recipe structure:

- Recipe title, description (written to be appetising), servings
- Preparation time, cook time, total time — if stated in the recipe
- Ingredients with quantities and units, grouped into sections
- Numbered preparation steps
- Assignment of ingredients to their respective preparation steps
- Recipe notes and tips

### 3. Food Matcher (Ingredient Matching)

Each recognised ingredient is matched against the existing Mealie ingredient database in three stages:

1. **Exact match** (normalised): String comparison after removing qualifiers ("fresh parsley" → "parsley"), case, and brackets
2. **Semantic shortlist**: A local embedding model (`paraphrase-multilingual-mpnet-base-v2`, ~1 GB, runs entirely locally) finds the 8 most semantically similar candidates
3. **AI decision**: Claude selects the best match from the shortlist — or returns none if uncertain

For **new ingredients** with no match, the AI automatically suggests singular, plural, aliases, and a food category.

### 4. Unit Matcher

Units are matched via a curated **normalisation table** ("tbsp", "tablespoon", "T." → same unit). Tablespoons and teaspoons are never confused. For unknown units, the AI decides.

### 5. Instruction Assignment

The AI assigns ingredients to each preparation step — the basis for Mealie's step-by-step cooking view.

### 6. Metadata Classification

Claude automatically selects a **recipe category** and suitable **tags** from the existing Mealie system.

---

## The "Review" Step — What Can You Do?

Before transferring to Mealie, an interactive interface allows you to review and adjust all recognised data:

### Recipe Summary
- Edit title, description, and serving count
- Adjust times
- Change category and tags

### Ingredients, Quantities & Units
- **Assign an ingredient to an existing Mealie ingredient** (dropdown with all options including search)
- For new ingredients: **adjust name, plural, aliases, and category** before creation
- Change units or assign to an existing unit
- Add notes to individual ingredients
- Mark ingredients as deleted

### Image
- Use the automatically detected **image from the PDF**
- **Upload a custom image** (JPG, PNG, WebP, up to 20 MB)
- Built-in **cropping tool** with freely selectable crop area and zoom

### Preparation Steps
- Edit individual step texts
- Adjust ingredient assignments per step

---

## AI Models, API & Costs

The tool currently uses exclusively the **Anthropic Claude API**. It can theoretically be switched to other providers via the settings and prompts configuration.

| Purpose | Model |
|---|---|
| Recipe analysis | claude-sonnet-4-6 |
| Ingredient matching | claude-sonnet-4-6 |
| Metadata classification | claude-sonnet-4-6 |
| Units & word forms | claude-haiku-4-5 |

**Cost per recipe**: approx. **$0.12 USD** (as of June 2026; depends on recipe length and number of new ingredients)

The embedding model for semantic ingredient matching runs **entirely locally** on the server — no ongoing costs. The model (~1 GB) is downloaded and cached automatically on first start.

---

## Self-Hosting

### Requirements

- A running **Mealie instance** with API access enabled
- **Docker** and Docker Compose
- **Anthropic API key** ([console.anthropic.com](https://console.anthropic.com))
- Server with **x86/amd64 architecture** (for the local embedding model)
- At least **2 GB free RAM** for the embedding model
- At least **2 GB free disk space** for the model cache

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/frank2604/mealie-ai-importer.git
cd mealie-ai-importer
```

**2. Create the configuration file**
```bash
cp config/settings.template.yaml config/settings.yaml
```

**3. Edit the configuration** (`config/settings.yaml`)
```yaml
mealie:
  base_url: http://your-mealie-instance:9925
  token: YOUR_MEALIE_API_TOKEN

llm:
  provider: anthropic
  api_key: sk-ant-...
  model: claude-sonnet-4-6
```

You can find your Mealie API token under: *Settings → Security → API Tokens*

**4. Start the containers**
```bash
docker compose up -d
```

**5. Open the UI**

The interface is available at `http://localhost:8001`.

### Important Notes

- `config/settings.yaml` contains sensitive data (API keys, Mealie token) and must **never** be committed to a public repository. The file is already listed in `.gitignore`.
- On first start, the tool downloads the embedding model (~1 GB). This may take a few minutes.
- The tool is designed for **one concurrent import** — parallel use by multiple people is not supported.

### Optional Remote Access (Cloudflare Tunnel + Authelia)

For internet access without opening ports on your router, **Cloudflare Tunnel** (free) combined with **Authelia** as a login gateway works well. Setup is not part of this project:

- [Cloudflare Tunnel documentation](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [Authelia](https://www.authelia.com/)

---

## Language

The user interface defaults to **German** and can be switched to **English**. However, the import process itself has only been tested with German-language recipes.

---

## Technical Stack

| Component | Technology |
|---|---|
| Backend | Python / FastAPI |
| Frontend | TypeScript / React / Vite / Tailwind CSS |
| AI | Anthropic Claude API |
| Semantic matching | fastembed (ONNX, local) |
| Deployment | Docker / Docker Compose |
| CI/CD | GitHub Actions → GitHub Container Registry |

---

## Known Limitations

- **PDF format**: The PDF must contain an embedded text layer (searchable PDF). Scanned recipe books without text recognition are not supported.
- **Language**: Tested exclusively with **German-language recipes**. The UI can be switched to English, but imports in English have never been tested.
- **Single user**: Only **one import can run at a time**.
- **Categories & tags**: Automatic tagging is based on the system configured in the respective Mealie instance.

---

## License

MIT License — free to use, modify, and distribute with attribution.

---

*Built with [Claude](https://claude.ai) by Anthropic — 100% vibe-coding.*
