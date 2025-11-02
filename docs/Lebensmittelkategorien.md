Lebensmittelkategorien

# API Call:
GET /api/groups/labels

# Curl
curl -X 'GET' \
  'https://mealie.local/api/groups/labels?orderDirection=desc&page=1&perPage=50' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0OGZmNzI2MS04MTdhLTQzYTktODlkZS02M2VlNjlkZDRhM2UiLCJleHAiOjE3NjAzNzg2NzIsImlzcyI6Im1lYWxpZSJ9.s4vImVaJ-9YNsSQEqc6SF0NBT_iiUS9yYhSqJj13XVA'
  
# Response body:
{
  "page": 1,
  "per_page": 50,
  "total": 2,
  "total_pages": 1,
  "items": [
    {
      "name": "Lebensmittelkategorie 2",
      "color": "#7595C4",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "dc5496cc-468e-4b86-bef4-8dd5f5d88752"
    },
    {
      "name": "Lebensmittelkategorie 1",
      "color": "#9D3737",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "3256dea7-8566-4738-92e4-edb541a337d2"
    }
  ],
  "next": null,
  "previous": null
}

# Sicherung 20251012
{
  "page": 1,
  "per_page": 500,
  "total": 17,
  "total_pages": 1,
  "items": [
    {
      "name": "Würzmittel 🧂",
      "color": "#C58C85",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "36be9b8c-4dd6-4f59-abc0-4715a742566d"
    },
    {
      "name": "Wurstwaren 🥓",
      "color": "#D36B5F",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "cf095fa9-128c-4699-946e-4da8c4d87d7b"
    },
    {
      "name": "Tiefkühlware ❄️",
      "color": "#5DADEC",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "7206a457-7b61-4291-9a5a-2add225233c6"
    },
    {
      "name": "Süßwaren 🍫",
      "color": "#A0522D",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "f7d4b921-b296-461e-8ebd-73caa28a78f5"
    },
    {
      "name": "Sonstiges 🗂",
      "color": "#B0BEC5",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "1df1c72a-fb63-4be7-a4e3-a0e01a41ea1a"
    },
    {
      "name": "Snacks 🍿",
      "color": "#F5C518",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "54ba9c5a-8b1e-4a68-bebb-c4a5775e205f"
    },
    {
      "name": "Obst & Gemüse 🍎",
      "color": "#7BB661",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "d1cd4704-d9b1-4019-906f-4e3fc67e040a"
    },
    {
      "name": "Milchprodukte 🥛",
      "color": "#AEE1F9",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "033fbe17-9b70-459f-868e-3f4f8fa34b1e"
    },
    {
      "name": "Konserven 🥫",
      "color": "#6C757D",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "12ad7907-8a98-4b62-9280-75543a1c9634"
    },
    {
      "name": "Gewürze 🌿",
      "color": "#9B5E2E",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "36348daf-72bb-4b31-ab8e-43ec1334071d"
    },
    {
      "name": "Getreide & Hülsenfrüchte 🌾",
      "color": "#CDAA6D",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "7a5188a1-c0fb-4527-910e-ee13f7c8b447"
    },
    {
      "name": "Getränke 🧃",
      "color": "#FFA552",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "e2016681-434c-488e-aefa-5b9bece3bbd9"
    },
    {
      "name": "Fleisch 🥩",
      "color": "#C14953",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "d544476e-8baa-434b-87d3-66cb979cea2d"
    },
    {
      "name": "Fisch & Meeresfrüchte 🐟",
      "color": "#4F9DA6",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "f18d40ff-6baf-41fa-89b2-01f306240cc8"
    },
    {
      "name": "Backzutaten 🧁",
      "color": "#E0BBE4",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "5c0671c9-16ee-40fb-b721-0401e9b2267f"
    },
    {
      "name": "Backwaren 🥖",
      "color": "#D4A373",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "fa1ee8c7-ff12-435d-b213-bd9233b7a37a"
    },
    {
      "name": "Alkohol 🍻",
      "color": "#B5651D",
      "groupId": "5977364f-4465-4f7a-b672-b97ab1801232",
      "id": "7c260419-4a87-440b-8b4d-cec090a65078"
    }
  ],
  "next": null,
  "previous": null
}