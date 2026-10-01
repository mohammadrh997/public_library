import pytest


async def test_catalogue_is_public_and_starts_empty(client):
    response = await client.get("/books")
    assert response.status_code == 200
    assert response.json() == []


async def test_members_cannot_add_books(client, member_headers):
    response = await client.post(
        "/books",
        headers=member_headers,
        json={"title": "X", "author": "Y", "isbn": "1234567890", "total_copies": 1},
    )
    assert response.status_code == 403


async def test_librarian_can_add_a_book(client, book):
    assert book["title"] == "Dune"
    assert "id" in book


async def test_duplicate_isbn_is_a_conflict(client, librarian_headers, book):
    response = await client.post(
        "/books",
        headers=librarian_headers,
        json={"title": "Other", "author": "Other", "isbn": book["isbn"], "total_copies": 1},
    )
    assert response.status_code == 409


async def test_patch_changes_only_the_fields_sent(client, librarian_headers, book):
    response = await client.patch(
        f"/books/{book['id']}", headers=librarian_headers, json={"title": "Dune Messiah"}
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["title"] == "Dune Messiah"
    assert updated["author"] == book["author"]
    assert updated["total_copies"] == book["total_copies"]


async def test_missing_book_is_404(client):
    response = await client.get("/books/99999")
    assert response.status_code == 404


@pytest.mark.parametrize(
    "bad_payload",
    [
        {"title": "", "author": "A", "isbn": "1234567890", "total_copies": 1},
        {"title": "T", "author": "A", "isbn": "1234567890", "total_copies": -1},
        {"title": "T", "author": "A", "total_copies": 1},
    ],
)
async def test_invalid_books_are_rejected(client, librarian_headers, bad_payload):
    response = await client.post("/books", headers=librarian_headers, json=bad_payload)
    assert response.status_code == 422
