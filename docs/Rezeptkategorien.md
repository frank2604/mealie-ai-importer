Rezept-Kategorie

# API-Call:
/api/organizers/categories

# Curl:
curl -X 'GET' \
  'https://mealie.local/api/organizers/categories?orderDirection=desc&page=1&perPage=50' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <Token eintragen>'

# Response body:
{
  "page": 1,
  "per_page": 50,
  "total": 2,
  "total_pages": 1,
  "items": [
    {
      "id": "6dd4d315-0bf9-45e4-840e-61683b904173",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Kategorie 2",
      "slug": "kategorie-2"
    },
    {
      "id": "9b440706-9fe6-4c0b-81c2-f28963e941ee",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Kategorie 1",
      "slug": "kategorie-1"
    }
  ],
  "next": null,
  "previous": null
}

# SSH-Skript zum Erzeugen im Terminal
export BASE_URL="https://mealie.local"
export TOKEN="<Token eintragen>"

KATS=(
"Frühstück & Brunch 🥐"
"Vorspeisen & Tapas 🥟"
"Salate & Bowls 🥗"
"Suppen & Eintöpfe 🍲"
"Hauptgerichte – Fleisch 🥩"
"Hauptgerichte – Fisch & Meer 🐟"
"Hauptgerichte – Vegetarisch/Vegan 🌱"
"Beilagen 🍚"
"Saucen, Dips & Dressings 🫙"
"Backen (Brot & Gebäck) 🍞"
"Desserts & Süßes 🍰"
"Getränke 🥤"
)

for NAME in "${KATS[@]}"; do
  curl -ksS -X POST "$BASE_URL/api/organizers/categories" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg n "$NAME" '{name:$n}')"
done

# Sicherung 20251012
{
  "page": 1,
  "per_page": 50,
  "total": 12,
  "total_pages": 1,
  "items": [
    {
      "id": "650b3013-9fe3-423f-9729-6e323bbc0c40",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Getränke 🥤",
      "slug": "getranke"
    },
    {
      "id": "27b679ff-26d7-4a60-8c97-657bcb149625",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Desserts & Süßes 🍰",
      "slug": "desserts-susses"
    },
    {
      "id": "a178c22d-ffa7-4164-ada8-bc05d0d83bb9",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Backen (Brot & Gebäck) 🍞",
      "slug": "backen-brot-geback"
    },
    {
      "id": "1cb7a631-cd2f-4127-9356-956888d7430c",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Saucen, Dips & Dressings 🫙",
      "slug": "saucen-dips-dressings"
    },
    {
      "id": "e162aef0-c9a4-4765-b8f1-0618a29e7713",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Beilagen 🍚",
      "slug": "beilagen"
    },
    {
      "id": "2c4fbbde-a292-4d93-9d12-24ed40c7256a",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptgerichte – Vegetarisch/Vegan 🌱",
      "slug": "hauptgerichte-vegetarisch-vegan"
    },
    {
      "id": "a5c9bec8-b8e8-45aa-b42e-88df68790fd9",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptgerichte – Fisch & Meer 🐟",
      "slug": "hauptgerichte-fisch-meer"
    },
    {
      "id": "c8b08673-ba91-4d4e-899b-77b9e9a4e733",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Hauptgerichte – Fleisch 🥩",
      "slug": "hauptgerichte-fleisch"
    },
    {
      "id": "9d7a9a24-b40d-462c-969a-79b0cd813eac",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Suppen & Eintöpfe 🍲",
      "slug": "suppen-eintopfe"
    },
    {
      "id": "49c013e3-2a37-4554-a9ef-0990636fbd2f",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Salate & Bowls 🥗",
      "slug": "salate-bowls"
    },
    {
      "id": "ba51e0ac-9bc4-4528-90cc-b30866b732f8",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Vorspeisen & Tapas 🥟",
      "slug": "vorspeisen-tapas"
    },
    {
      "id": "e4491d97-bbf6-477e-be34-7ba1e3e9b405",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "name": "Frühstück & Brunch 🥐",
      "slug": "fruhstuck-brunch"
    }
  ],
  "next": null,
  "previous": null
}