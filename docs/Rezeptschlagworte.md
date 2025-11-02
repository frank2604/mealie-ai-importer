Rezept-Schlagworte

# API-Call:
GET /api/organizers/tags

# Curl
curl -X 'GET' \
  'https://mealie.local/api/organizers/tags?orderDirection=desc&page=1&perPage=50' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <Token eintragen>'
  
# Response body
{
  "page": 1,
  "per_page": 50,
  "total": 2,
  "total_pages": 1,
  "items": [
    {
      "id": "74c46ed7-34c6-49e0-b5ca-5a09e71b0c55",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Schlagwort 1",
      "slug": "schlagwort-1"
    },
    {
      "id": "b4760452-1ea2-4394-8696-a38f9e16d93f",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Schlagwort 2",
      "slug": "schlagwort-2"
    }
  ],
  "next": null,
  "previous": null
}


# SSH-Skript zum Erzeuge im Terminal
export BASE_URL="https://mealie.local"
export TOKEN="<Token eintragen>"

post_tag(){ curl -ksS -X POST "$BASE_URL/api/organizers/tags" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$(jq -n --arg n "$1" '{name:$n}')">/dev/null && echo "$1"; }

KUECHE=("Italienisch 🇮🇹" "Spanisch 🇪🇸" "Deutsch 🇩🇪" "Französisch 🇫🇷" "Griechisch 🇬🇷" "Türkisch 🇹🇷" "Arabisch 🕌" "Indisch 🇮🇳" "Pakistanisch 🇵🇰" "Japanisch 🇯🇵" "Koreanisch 🇰🇷" "Chinesisch 🇨🇳" "Thai 🇹🇭" "Vietnamesisch 🇻🇳" "Mexikanisch 🇲🇽" "US-amerikanisch 🇺🇸" "Skandinavisch 🇸🇪" "Afrikanisch 🌍" "Fusion 🧪")
TECHNIK=("Ofen 🔥" "Pfanne 🍳" "Grill 🔥" "Schmoren 🍲" "Dünsten 🌫️" "Dämpfen 🧺" "Sous-vide 🥽" "Frittieren 🍟" "Backen 🥐" "Roh 🥗" "One-Pot 🫕" "Wok 🍜" "Airfryer 🛩️" "Slowcooker 🐢" "Fermentieren 🧫" "Marinieren 🧂")
PROTEIN=("Rind 🐄" "Schwein 🐖" "Geflügel 🐔" "Lamm 🐑" "Wild 🦌" "Fisch 🐟" "Meeresfrüchte 🦐" "Ei 🥚" "Tofu 🧱" "Tempeh 🫘" "Hülsenfrüchte 🌱" "Käse 🧀" "Ohne Proteinangabe 🚫")
HAUPTZUTAT=("Kartoffel 🥔" "Süßkartoffel 🍠" "Reis 🍚" "Pasta 🍝" "Couscous 🍽️" "Bulgur 🥣" "Linsen 🟠" "Kichererbsen 🟡" "Bohnen 🫘" "Quinoa 🌾" "Kürbis 🎃" "Zucchini 🥒" "Tomate 🍅" "Paprika 🫑" "Aubergine 🍆" "Spinat 🥬" "Blumenkohl 🥦" "Brokkoli 🥦" "Pilze 🍄")
ERNAEHRUNG=("Vegetarisch 🌿" "Vegan 🌱" "Flexitarisch 🤝" "Pescetarisch 🐟" "Glutenfrei 🚫🌾" "Laktosefrei 🚫🥛" "Low-Carb 📉" "High-Protein 💪" "Keto 🧈" "Paleo 🪨" "Zuckerreduziert 🧂" "Clean Eating ✨")
ANLASS=("Feierabend ⏱️" "Gäste 🥂" "Party 🎉" "Buffet 🧆" "Meal-Prep 📦" "Büro/Lunchbox 👜" "Picknick 🧺" "Kinderfreundlich 🧸" "Festlich 🎀" "Sport/Recovery 🏃")
SAISON=("Frühling 🌸" "Sommer ☀️" "Herbst 🍂" "Winter ❄️" "Weihnachten 🎄" "Ostern 🐣" "Grillzeit 🔥")
FORM=("Bowl 🥗" "Curry 🍛" "Eintopf 🍲" "Auflauf 🧀" "Pfannengericht 🍳" "Pasta-Gericht 🍝" "Pizza 🍕" "Quiche 🥧" "Tarte 🥧" "Wrap 🌯" "Burger 🍔" "Sandwich 🥪" "Suppe 🥣" "Salat 🥗" "Tapas/Mezze 🍢")
AUFWAND=("Schnell (≤ 20 min) ⚡" "Mittel (30–60 min) ⏳" "Aufwendig (60+ min) 🧰" "Few-Ingredients (≤ 5) 5️⃣" "One-Sheet/Tray 🍽️")
SCHAERFE=("Mild 🙂" "Mittel 🌶️" "Scharf 🔥" "Extra scharf 🔥🔥")
GERAET=("Thermomix ⚙️" "Reiskocher 🍚" "Airfryer 🛩️" "Dutch-Oven 🍲" "Grill 🔥" "Waffeleisen 🧇" "Mikrowelle 📡" "Schnellkochtopf ⏱️" "Brotbackautomat 🍞")
TAGESZEIT=("Frühstück ☀️" "Brunch 🥐" "Lunch 🥗" "Dinner 🌙" "Mitternachtssnack 🌌")

for v in "${KUECHE[@]}"; do post_tag "Küche | $v"; done
for v in "${TECHNIK[@]}"; do post_tag "Technik | $v"; done
for v in "${PROTEIN[@]}"; do post_tag "Protein | $v"; done
for v in "${HAUPTZUTAT[@]}"; do post_tag "Hauptzutat | $v"; done
for v in "${ERNAEHRUNG[@]}"; do post_tag "Ernährung | $v"; done
for v in "${ANLASS[@]}"; do post_tag "Anlass | $v"; done
for v in "${SAISON[@]}"; do post_tag "Saison | $v"; done
for v in "${FORM[@]}"; do post_tag "Form | $v"; done
for v in "${AUFWAND[@]}"; do post_tag "Aufwand | $v"; done
for v in "${SCHAERFE[@]}"; do post_tag "Schärfe | $v"; done
for v in "${GERAET[@]}"; do post_tag "Gerät | $v"; done
for v in "${TAGESZEIT[@]}"; do post_tag "Tageszeit | $v"; done

# Sicherung 20251012
{
  "page": 1,
  "per_page": 500,
  "total": 134,
  "total_pages": 1,
  "items": [
    {
      "id": "77e8d4e7-99b8-4ffa-ad5f-1fbc9c0f1b96",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Tageszeit | Mitternachtssnack 🌌",
      "slug": "tageszeit-mitternachtssnack"
    },
    {
      "id": "539f721a-a8e8-4c15-a7b4-deefcfb27f3a",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Tageszeit | Dinner 🌙",
      "slug": "tageszeit-dinner"
    },
    {
      "id": "2be726af-d1cd-432a-a17a-6ed8b2fad868",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Tageszeit | Lunch 🥗",
      "slug": "tageszeit-lunch"
    },
    {
      "id": "7c37eb32-c754-4ef6-95a8-6a5ead22a06d",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Tageszeit | Brunch 🥐",
      "slug": "tageszeit-brunch"
    },
    {
      "id": "7752f977-491d-4c36-8906-e6bbc87d38ed",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Tageszeit | Frühstück ☀️",
      "slug": "tageszeit-fruhstuck"
    },
    {
      "id": "a8a4a379-7e98-4c1d-b658-0141d037fa3e",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Gerät | Brotbackautomat 🍞",
      "slug": "gerat-brotbackautomat"
    },
    {
      "id": "b3c40a14-0739-4aa3-b083-3fe5689004db",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Gerät | Schnellkochtopf ⏱️",
      "slug": "gerat-schnellkochtopf"
    },
    {
      "id": "3f247e09-ebf5-4114-8f66-dc099132a4f3",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Gerät | Mikrowelle 📡",
      "slug": "gerat-mikrowelle"
    },
    {
      "id": "f5d3f88c-29a8-4885-9096-5a19e559384c",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Gerät | Waffeleisen 🧇",
      "slug": "gerat-waffeleisen"
    },
    {
      "id": "b673c7a1-12e3-43cf-a817-914b92e7a124",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Gerät | Grill 🔥",
      "slug": "gerat-grill"
    },
    {
      "id": "3b226a44-1881-4446-a585-d583ffa4d9cf",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Gerät | Dutch-Oven 🍲",
      "slug": "gerat-dutch-oven"
    },
    {
      "id": "956c2348-efb1-4605-8222-65b3c1d551a5",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Gerät | Airfryer 🛩️",
      "slug": "gerat-airfryer"
    },
    {
      "id": "e2bbf7bb-c780-422d-a020-ef59b37daabc",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Gerät | Reiskocher 🍚",
      "slug": "gerat-reiskocher"
    },
    {
      "id": "b224774e-2b68-4d0d-b439-d88bad5e4669",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Gerät | Thermomix ⚙️",
      "slug": "gerat-thermomix"
    },
    {
      "id": "8369fa48-8fb6-4ab4-bba0-4683af15b1db",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Schärfe | Extra scharf 🔥🔥",
      "slug": "scharfe-extra-scharf"
    },
    {
      "id": "20529bfe-76e9-444e-984e-9be15e7a6eda",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Schärfe | Scharf 🔥",
      "slug": "scharfe-scharf"
    },
    {
      "id": "4f3e6bd7-bc99-45eb-8975-249c465c3d8b",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Schärfe | Mittel 🌶️",
      "slug": "scharfe-mittel"
    },
    {
      "id": "d5a8b13a-11cb-4d0c-893f-d2c99204eaea",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Schärfe | Mild 🙂",
      "slug": "scharfe-mild"
    },
    {
      "id": "fc6299e5-1296-4d89-a920-547b796c217a",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Aufwand | One-Sheet/Tray 🍽️",
      "slug": "aufwand-one-sheet-tray"
    },
    {
      "id": "011606fa-384b-452b-aaa4-0a0812aa098d",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Aufwand | Few-Ingredients (≤ 5) 5️⃣",
      "slug": "aufwand-few-ingredients-5-5"
    },
    {
      "id": "d8590c06-ad00-41ed-8b25-c608bed99b7e",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Aufwand | Aufwendig (60+ min) 🧰",
      "slug": "aufwand-aufwendig-60-min"
    },
    {
      "id": "9ab0a230-6e50-4cc3-bdbe-f44d5457e15c",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Aufwand | Mittel (30–60 min) ⏳",
      "slug": "aufwand-mittel-30-60-min"
    },
    {
      "id": "15e80728-68c2-420f-b908-4d7f6b03281a",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Aufwand | Schnell (≤ 20 min) ⚡",
      "slug": "aufwand-schnell-20-min"
    },
    {
      "id": "e109d7e2-dbad-4bd7-88b9-e0187c06853c",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Form | Tapas/Mezze 🍢",
      "slug": "form-tapas-mezze"
    },
    {
      "id": "f9ec0e0e-1623-4753-9a01-2d072843aca5",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Form | Salat 🥗",
      "slug": "form-salat"
    },
    {
      "id": "0ef6a4e1-ad96-4595-bc7f-a304f9a03599",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Form | Suppe 🥣",
      "slug": "form-suppe"
    },
    {
      "id": "d6442b73-b4d8-4c13-97d6-21da9b46fffb",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Form | Sandwich 🥪",
      "slug": "form-sandwich"
    },
    {
      "id": "178cfcdb-a562-4fa1-baf2-727e51b6eda6",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Form | Burger 🍔",
      "slug": "form-burger"
    },
    {
      "id": "17663b69-deb0-45f0-bf9c-e13bdc5a4a12",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Form | Wrap 🌯",
      "slug": "form-wrap"
    },
    {
      "id": "93629e83-7868-46d5-883c-3abc317c4ff5",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Form | Tarte 🥧",
      "slug": "form-tarte"
    },
    {
      "id": "273217f8-9f99-49bd-aa72-38f0fd953610",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Form | Quiche 🥧",
      "slug": "form-quiche"
    },
    {
      "id": "bbec333b-08a2-467c-9f67-7e8a896c3610",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Form | Pizza 🍕",
      "slug": "form-pizza"
    },
    {
      "id": "db041879-fefd-4b2c-8e4a-733d9b040d7f",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Form | Pasta-Gericht 🍝",
      "slug": "form-pasta-gericht"
    },
    {
      "id": "934e7b20-c521-40c9-a09c-5bc9706f9542",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Form | Pfannengericht 🍳",
      "slug": "form-pfannengericht"
    },
    {
      "id": "11775025-b6b7-4103-b93f-28b118364a60",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Form | Auflauf 🧀",
      "slug": "form-auflauf"
    },
    {
      "id": "9300a07c-1efb-4790-a7d8-6e5403c1da9d",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Form | Eintopf 🍲",
      "slug": "form-eintopf"
    },
    {
      "id": "f613b64b-7f1c-461a-9e14-aab10e49d7c8",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Form | Curry 🍛",
      "slug": "form-curry"
    },
    {
      "id": "2c830b67-56e5-4eeb-b4fd-ac329c8180dd",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Form | Bowl 🥗",
      "slug": "form-bowl"
    },
    {
      "id": "96956c83-8d1e-4690-83d4-0104ab56ec92",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Saison | Grillzeit 🔥",
      "slug": "saison-grillzeit"
    },
    {
      "id": "3467c147-3d3a-44ad-8cac-95aeeaa52b5f",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Saison | Ostern 🐣",
      "slug": "saison-ostern"
    },
    {
      "id": "ae5a8dda-ebe7-4fd5-a0d2-924665f00cc6",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Saison | Weihnachten 🎄",
      "slug": "saison-weihnachten"
    },
    {
      "id": "dc6070bd-0ac5-487c-8756-9170e2e85b34",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Saison | Winter ❄️",
      "slug": "saison-winter"
    },
    {
      "id": "f580714e-8ea4-47e6-a6be-2c7e133a52bb",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Saison | Herbst 🍂",
      "slug": "saison-herbst"
    },
    {
      "id": "4a15942e-a766-4c3e-b6f8-0c3466f54ec7",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Saison | Sommer ☀️",
      "slug": "saison-sommer"
    },
    {
      "id": "62cf1ee1-75a7-4eeb-bfd7-bf1f7de26bf0",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Saison | Frühling 🌸",
      "slug": "saison-fruhling"
    },
    {
      "id": "b37c0951-d0ca-4b90-858a-82094534e699",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Anlass | Sport/Recovery 🏃",
      "slug": "anlass-sport-recovery"
    },
    {
      "id": "0c9b832c-017a-4ddd-9c7f-9c6903b990fc",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Anlass | Festlich 🎀",
      "slug": "anlass-festlich"
    },
    {
      "id": "2a0a8063-22dd-4b3b-a4ee-6bb3a8fe12ff",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Anlass | Kinderfreundlich 🧸",
      "slug": "anlass-kinderfreundlich"
    },
    {
      "id": "db7fb472-0133-4bd9-b8e9-cc6ffae9c3ce",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Anlass | Picknick 🧺",
      "slug": "anlass-picknick"
    },
    {
      "id": "5326e7e9-633f-4f86-ba22-31ddddd4b418",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Anlass | Büro/Lunchbox 👜",
      "slug": "anlass-buro-lunchbox"
    },
    {
      "id": "e7d63f1b-0d94-4858-8e56-0d4810afc8b8",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Anlass | Meal-Prep 📦",
      "slug": "anlass-meal-prep"
    },
    {
      "id": "d366d059-4a3c-4878-a412-aa218d591175",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Anlass | Buffet 🧆",
      "slug": "anlass-buffet"
    },
    {
      "id": "39338dd1-1c4a-417c-a3bb-85317784985c",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Anlass | Party 🎉",
      "slug": "anlass-party"
    },
    {
      "id": "57fdcf49-1490-492d-853d-e90898ad08fb",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Anlass | Gäste 🥂",
      "slug": "anlass-gaste"
    },
    {
      "id": "a23e2e57-ae7a-459b-952b-119334b04f48",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Anlass | Feierabend ⏱️",
      "slug": "anlass-feierabend"
    },
    {
      "id": "5293e5ac-ce33-4e07-80b4-31c02ea14397",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Ernährung | Clean Eating ✨",
      "slug": "ernahrung-clean-eating"
    },
    {
      "id": "8dd5e0d9-89df-4922-bddc-a4da0972eba5",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Ernährung | Zuckerreduziert 🧂",
      "slug": "ernahrung-zuckerreduziert"
    },
    {
      "id": "8b28de15-7211-4106-b569-36cc739e7ea2",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Ernährung | Paleo 🪨",
      "slug": "ernahrung-paleo"
    },
    {
      "id": "e7d63299-baf7-40a7-bdc9-8588666f23a2",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Ernährung | Keto 🧈",
      "slug": "ernahrung-keto"
    },
    {
      "id": "6b6c225a-f74e-4366-a61b-deb6afccdb3c",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Ernährung | High-Protein 💪",
      "slug": "ernahrung-high-protein"
    },
    {
      "id": "dd0f993c-ec19-439a-a9a1-fe10cf2df81c",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Ernährung | Low-Carb 📉",
      "slug": "ernahrung-low-carb"
    },
    {
      "id": "aa0c42a2-28a0-4510-9e67-ce672966655b",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Ernährung | Laktosefrei 🚫🥛",
      "slug": "ernahrung-laktosefrei"
    },
    {
      "id": "ceb54f28-21a4-4a48-a790-6fed9a562160",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Ernährung | Glutenfrei 🚫🌾",
      "slug": "ernahrung-glutenfrei"
    },
    {
      "id": "16699ada-2b75-4081-a2e5-4c7fa0747d4f",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Ernährung | Pescetarisch 🐟",
      "slug": "ernahrung-pescetarisch"
    },
    {
      "id": "87a08747-22db-49ea-803f-7df490676378",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Ernährung | Flexitarisch 🤝",
      "slug": "ernahrung-flexitarisch"
    },
    {
      "id": "6874b6c7-7e98-4fac-883f-f4250e3dad62",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Ernährung | Vegan 🌱",
      "slug": "ernahrung-vegan"
    },
    {
      "id": "bcb3bb6e-a4b1-4a19-b9db-a7fa3429dfeb",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Ernährung | Vegetarisch 🌿",
      "slug": "ernahrung-vegetarisch"
    },
    {
      "id": "0f94c939-f5d1-482b-83de-331617c0965b",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Pilze 🍄",
      "slug": "hauptzutat-pilze"
    },
    {
      "id": "3c994c94-4aad-4328-a420-ac5ea64fedc3",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Brokkoli 🥦",
      "slug": "hauptzutat-brokkoli"
    },
    {
      "id": "eb2b2239-fc05-403c-856d-88c52592e415",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Blumenkohl 🥦",
      "slug": "hauptzutat-blumenkohl"
    },
    {
      "id": "aa55e16f-e391-47d7-9d9f-a046a7393508",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Spinat 🥬",
      "slug": "hauptzutat-spinat"
    },
    {
      "id": "343b0690-a98f-4656-9d60-98e56b4dd8f7",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Aubergine 🍆",
      "slug": "hauptzutat-aubergine"
    },
    {
      "id": "d6e06c60-b3fe-4df4-8259-11fff10b0c86",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Paprika 🫑",
      "slug": "hauptzutat-paprika"
    },
    {
      "id": "5a37d6eb-8601-432c-b42a-9bcc6787722a",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Tomate 🍅",
      "slug": "hauptzutat-tomate"
    },
    {
      "id": "48a99c9c-3163-4825-872c-548d01aeb478",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Zucchini 🥒",
      "slug": "hauptzutat-zucchini"
    },
    {
      "id": "3fc654b5-01dd-4c9a-9f38-4f095839325c",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Kürbis 🎃",
      "slug": "hauptzutat-kurbis"
    },
    {
      "id": "65ce4841-c1c0-44c6-b951-f0b98eb83117",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Quinoa 🌾",
      "slug": "hauptzutat-quinoa"
    },
    {
      "id": "86d8bd13-e947-4900-ad7d-3f4b1841c88a",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Bohnen 🫘",
      "slug": "hauptzutat-bohnen"
    },
    {
      "id": "4188fe01-a164-4e82-8e3e-6592ea4654d8",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Kichererbsen 🟡",
      "slug": "hauptzutat-kichererbsen"
    },
    {
      "id": "93b1ff1a-a0b9-4d6a-986d-41f914687ebe",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Linsen 🟠",
      "slug": "hauptzutat-linsen"
    },
    {
      "id": "b07f5262-fd7b-4486-ba98-f201c3bd2986",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Bulgur 🥣",
      "slug": "hauptzutat-bulgur"
    },
    {
      "id": "ec38d75b-4e5e-40d5-85ee-5e6c5a7ce845",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Couscous 🍽️",
      "slug": "hauptzutat-couscous"
    },
    {
      "id": "949861ba-7076-469c-8f66-941a8d6999bb",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Pasta 🍝",
      "slug": "hauptzutat-pasta"
    },
    {
      "id": "44190fcc-9dd0-4ad8-b122-afd5d4148060",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Reis 🍚",
      "slug": "hauptzutat-reis"
    },
    {
      "id": "fe18be0b-b39b-4d5d-a673-87eaafcec6cf",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Süßkartoffel 🍠",
      "slug": "hauptzutat-susskartoffel"
    },
    {
      "id": "dcfa7f6d-a00c-4413-8079-29dd9f2774be",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptzutat | Kartoffel 🥔",
      "slug": "hauptzutat-kartoffel"
    },
    {
      "id": "cad40246-a48b-4f80-b2a2-61c953909f07",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Protein | Ohne Proteinangabe 🚫",
      "slug": "protein-ohne-proteinangabe"
    },
    {
      "id": "036e0319-f9b4-4a60-b96d-2039646f9dd1",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Protein | Käse 🧀",
      "slug": "protein-kase"
    },
    {
      "id": "c75f00ea-dbc4-44d9-ab45-13a0ab0cbb22",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Protein | Hülsenfrüchte 🌱",
      "slug": "protein-hulsenfruchte"
    },
    {
      "id": "f3a72eb9-954a-4cd8-bb54-ab24fd010e98",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Protein | Tempeh 🫘",
      "slug": "protein-tempeh"
    },
    {
      "id": "c16d09d7-79fc-4500-a208-35a61b90985c",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Protein | Tofu 🧱",
      "slug": "protein-tofu"
    },
    {
      "id": "516f7542-54cf-4995-b1ad-2a0943ea73d2",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Protein | Ei 🥚",
      "slug": "protein-ei"
    },
    {
      "id": "58fd0d6d-f509-40c1-8b93-6dabff6b7dd6",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Protein | Meeresfrüchte 🦐",
      "slug": "protein-meeresfruchte"
    },
    {
      "id": "5a1f5b9e-c9f2-446d-a2d6-3bc24653785a",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Protein | Fisch 🐟",
      "slug": "protein-fisch"
    },
    {
      "id": "9c277001-49ea-487e-8028-3510104d90fa",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Protein | Wild 🦌",
      "slug": "protein-wild"
    },
    {
      "id": "d247e3d7-bc0a-4f41-af41-e90593a114b6",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Protein | Lamm 🐑",
      "slug": "protein-lamm"
    },
    {
      "id": "13678615-0773-49e3-8fd6-a7183885309f",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Protein | Geflügel 🐔",
      "slug": "protein-geflugel"
    },
    {
      "id": "872a782d-9b38-496c-9e16-f12ca3eff6b9",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Protein | Schwein 🐖",
      "slug": "protein-schwein"
    },
    {
      "id": "2c969c5c-b211-4fc3-89cb-a634fc27f5cd",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Protein | Rind 🐄",
      "slug": "protein-rind"
    },
    {
      "id": "050ee135-c6ef-4b9d-8c53-7a315abbac53",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Technik | Marinieren 🧂",
      "slug": "technik-marinieren"
    },
    {
      "id": "7493ebe1-d6cf-4a75-80b8-928603698805",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Technik | Fermentieren 🧫",
      "slug": "technik-fermentieren"
    },
    {
      "id": "3f8ec89d-ef02-4096-9f42-1fdf1d598c38",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Technik | Slowcooker 🐢",
      "slug": "technik-slowcooker"
    },
    {
      "id": "692a3ec1-e18a-40c9-add8-1900ec6db057",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Technik | Airfryer 🛩️",
      "slug": "technik-airfryer"
    },
    {
      "id": "2504a5c6-9a98-4bb8-90a7-e07cc33c687d",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Technik | Wok 🍜",
      "slug": "technik-wok"
    },
    {
      "id": "f779057f-e85d-48f4-8fe4-9091c78e0884",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Technik | One-Pot 🫕",
      "slug": "technik-one-pot"
    },
    {
      "id": "ac82a09b-cc45-4d48-89c1-d52bc2d00c4b",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Technik | Roh 🥗",
      "slug": "technik-roh"
    },
    {
      "id": "b17cb8bc-45a1-4fa0-bf1c-605eb31d324e",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Technik | Backen 🥐",
      "slug": "technik-backen"
    },
    {
      "id": "8fa3970b-ec6b-4b98-b4e9-173b982690e1",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Technik | Frittieren 🍟",
      "slug": "technik-frittieren"
    },
    {
      "id": "7174e352-43d5-4d0f-a26b-13d5ccafbc2f",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Technik | Sous-vide 🥽",
      "slug": "technik-sous-vide"
    },
    {
      "id": "6c65e936-b642-4cca-9f86-d438ea5530e4",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Technik | Dämpfen 🧺",
      "slug": "technik-dampfen"
    },
    {
      "id": "a4ec15de-4f99-46e6-8115-0bb16752538b",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Technik | Dünsten 🌫️",
      "slug": "technik-dunsten"
    },
    {
      "id": "89f490cf-36a0-4e03-a5b2-442ef7317714",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Technik | Schmoren 🍲",
      "slug": "technik-schmoren"
    },
    {
      "id": "aa23235b-594b-48d0-87bc-b5d1de454196",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Technik | Grill 🔥",
      "slug": "technik-grill"
    },
    {
      "id": "de422906-bd1d-4fc3-852f-a5e7b105a6e2",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Technik | Pfanne 🍳",
      "slug": "technik-pfanne"
    },
    {
      "id": "6d9ea018-b689-4ed0-88c0-1e2f5b78fd58",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Technik | Ofen 🔥",
      "slug": "technik-ofen"
    },
    {
      "id": "9e9364d5-650b-4a00-83d6-e9be8dbb13fc",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Fusion 🧪",
      "slug": "kuche-fusion"
    },
    {
      "id": "95680f09-59cd-48ee-9641-49d5c45e81e1",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Afrikanisch 🌍",
      "slug": "kuche-afrikanisch"
    },
    {
      "id": "d9d2c980-6372-4dab-8687-dc920a18d9d4",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Skandinavisch 🇸🇪",
      "slug": "kuche-skandinavisch"
    },
    {
      "id": "41d4b009-125c-473b-a0c6-725b28a2cf40",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | US-amerikanisch 🇺🇸",
      "slug": "kuche-us-amerikanisch"
    },
    {
      "id": "00b8da5d-5123-4a49-93ff-05fcb4128b75",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Mexikanisch 🇲🇽",
      "slug": "kuche-mexikanisch"
    },
    {
      "id": "967ef948-db73-47d9-afc9-be673c76579b",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Vietnamesisch 🇻🇳",
      "slug": "kuche-vietnamesisch"
    },
    {
      "id": "386ef81c-de75-4df8-906a-6fd24ca25939",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Thai 🇹🇭",
      "slug": "kuche-thai"
    },
    {
      "id": "df6f01c9-69a6-4f87-b6a1-799e6c70b1bc",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Chinesisch 🇨🇳",
      "slug": "kuche-chinesisch"
    },
    {
      "id": "c0ef5d5a-7e51-4171-9251-3a63b1a7b8a7",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Koreanisch 🇰🇷",
      "slug": "kuche-koreanisch"
    },
    {
      "id": "09de7e0f-17f5-4afb-aa41-09cb6472dc34",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Japanisch 🇯🇵",
      "slug": "kuche-japanisch"
    },
    {
      "id": "b582387d-c6f1-48bb-8b1d-1fe0e7ecb482",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Pakistanisch 🇵🇰",
      "slug": "kuche-pakistanisch"
    },
    {
      "id": "00adfec7-ba28-4604-a028-85d2c1695a79",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Indisch 🇮🇳",
      "slug": "kuche-indisch"
    },
    {
      "id": "cfb0b73b-e1a6-446a-8944-bd1837aaf417",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Arabisch 🕌",
      "slug": "kuche-arabisch"
    },
    {
      "id": "ec4cd617-22ac-412f-9dd9-55fecb953f03",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Türkisch 🇹🇷",
      "slug": "kuche-turkisch"
    },
    {
      "id": "c89b6551-f2fd-496e-b7d2-f1ff829e5c4b",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Griechisch 🇬🇷",
      "slug": "kuche-griechisch"
    },
    {
      "id": "5752fac1-8e94-4d96-b0a0-b920394396f8",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Französisch 🇫🇷",
      "slug": "kuche-franzosisch"
    },
    {
      "id": "89a32903-f169-4f75-8975-9c8fe40002a0",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Deutsch 🇩🇪",
      "slug": "kuche-deutsch"
    },
    {
      "id": "c5a29c43-ebbe-4e68-be51-88a2aa321115",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Spanisch 🇪🇸",
      "slug": "kuche-spanisch"
    },
    {
      "id": "9063f3bf-6806-49fc-a925-378b15dcc154",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Küche | Italienisch 🇮🇹",
      "slug": "kuche-italienisch"
    }
  ],
  "next": null,
  "previous": null
}