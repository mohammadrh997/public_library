async def test_member_can_borrow_a_book(client, member_headers, book):
    response = await client.post(f"/books/{book['id']}/borrow", headers=member_headers)
    assert response.status_code == 201
    assert response.json()["returned_at"] is None


async def test_cannot_borrow_the_same_book_twice(client, member_headers, book):
    await client.post(f"/books/{book['id']}/borrow", headers=member_headers)
    response = await client.post(f"/books/{book['id']}/borrow", headers=member_headers)
    assert response.status_code == 409


async def test_cannot_borrow_when_every_copy_is_out(
    client, librarian_headers, member_headers, other_member_headers
):
    created = await client.post(
        "/books",
        headers=librarian_headers,
        json={"title": "Rare", "author": "A", "isbn": "5555555555", "total_copies": 1},
    )
    book_id = created.json()["id"]
    await client.post(f"/books/{book_id}/borrow", headers=member_headers)
    response = await client.post(f"/books/{book_id}/borrow", headers=other_member_headers)
    assert response.status_code == 409


async def test_member_cannot_return_someone_elses_loan(
    client, member_headers, other_member_headers, book
):
    loan = (await client.post(f"/books/{book['id']}/borrow", headers=member_headers)).json()
    response = await client.post(f"/loans/{loan['id']}/return", headers=other_member_headers)
    assert response.status_code == 403


async def test_returning_twice_is_rejected(client, member_headers, book):
    loan = (await client.post(f"/books/{book['id']}/borrow", headers=member_headers)).json()
    await client.post(f"/loans/{loan['id']}/return", headers=member_headers)
    response = await client.post(f"/loans/{loan['id']}/return", headers=member_headers)
    assert response.status_code == 409


async def test_my_loans_include_book_details(client, member_headers, book):
    await client.post(f"/books/{book['id']}/borrow", headers=member_headers)
    response = await client.get("/loans/me", headers=member_headers)
    assert response.status_code == 200
    loans = response.json()
    assert len(loans) == 1
    assert loans[0]["book"]["title"] == "Dune"


async def test_overdue_report_is_librarian_only(client, member_headers):
    response = await client.get("/loans/overdue", headers=member_headers)
    assert response.status_code == 403
