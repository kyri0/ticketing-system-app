"""End-to-end HTTP tests for the ledger, with an in-memory repository."""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app import app, get_repository
from ticketing.repository import LedgerTally, Ticket, TicketMessage

NOW = dt.datetime(2026, 3, 14, 18, 30)


class FakeRepository:
    def __init__(self):
        self.tickets = [
            Ticket(41, "Portcullis jams on the north gate", "open", "urgent", "Gareth", NOW),
            Ticket(39, "Scribe requests <b>fresh</b> vellum", "in_progress", "high", "Alys", NOW),
            Ticket(36, "Moat is somewhat malodorous", "resolved", "low", "Hob", NOW),
        ]
        self.messages = {
            41: [
                TicketMessage(1, 41, "The chain has slipped its housing.", "Gareth", NOW),
                TicketMessage(2, 41, "A smith is sent for.", "Steward", NOW),
            ]
        }
        self.deleted: list[int] = []
        self.updated: list[tuple] = []

    def list_tickets(self):
        return list(self.tickets)

    def list_messages(self, ticket_id):
        return list(self.messages.get(ticket_id, []))

    def tally(self):
        by_status, by_priority = {}, {}
        for t in self.tickets:
            by_status[t.status] = by_status.get(t.status, 0) + 1
            by_priority[t.priority] = by_priority.get(t.priority, 0) + 1
        return LedgerTally(len(self.tickets), by_status, by_priority)

    def create_ticket(self, title, status, priority, created_by):
        ticket = Ticket(99, title, status, priority, created_by, NOW)
        self.tickets.append(ticket)
        return ticket

    def add_message(self, ticket_id, message_text, author):
        message = TicketMessage(9, ticket_id, message_text, author, NOW)
        self.messages.setdefault(ticket_id, []).append(message)
        return message

    def update_ticket(self, ticket_id, status, priority):
        self.updated.append((ticket_id, status, priority))
        return self.tickets[0]

    def delete_ticket(self, ticket_id):
        self.deleted.append(ticket_id)


@pytest.fixture
def repo():
    fake = FakeRepository()
    app.dependency_overrides[get_repository] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def client(repo):
    return TestClient(app)


def test_ledger_lists_every_petition(client):
    page = client.get("/").text
    assert "Portcullis jams on the north gate" in page
    assert "Moat is somewhat malodorous" in page
    assert "Showing 3 of 3 petitions" in page


def test_lexicon_is_displayed_not_the_stored_values(client):
    page = client.get("/").text
    assert "Dire" in page and "Underway" in page and "Trifling" in page
    assert ">in_progress<" not in page


def test_titles_are_escaped(client):
    page = client.get("/").text
    assert "<b>fresh</b>" not in page
    assert "&lt;b&gt;fresh&lt;/b&gt;" in page


def test_thread_hidden_until_petition_is_opened(client):
    assert "A smith is sent for." not in client.get("/").text
    assert "A smith is sent for." in client.get("/?open=41").text


def test_open_petition_shows_drop_cap_on_first_entry_only(client):
    page = client.get("/?open=41").text
    assert page.count('class="entry first"') == 1
    assert page.count('class="entry"') == 1


def test_filter_by_standing(client):
    page = client.get("/?standing=open").text
    assert "Showing 1 of 3 petitions" in page
    assert "Moat is somewhat malodorous" not in page


def test_filter_by_urgency(client):
    assert "Showing 1 of 3 petitions" in client.get("/?urgency=urgent").text


def test_search_matches_title(client):
    assert "Showing 1 of 3 petitions" in client.get("/?q=moat").text


def test_unknown_filter_values_are_ignored(client):
    assert "Showing 3 of 3 petitions" in client.get("/?standing=bogus&sort=sideways").text


def test_urgency_sort_puts_the_direst_first(client):
    page = client.get("/").text
    assert page.index("Portcullis") < page.index("Scribe") < page.index("Moat")


def test_statistics_are_rendered(client):
    page = client.get("/").text
    assert "Petitions" in page and "By urgency" in page


def test_create_redirects_and_opens_the_new_petition(client, repo):
    response = client.post(
        "/petitions",
        data={"title": "Drawbridge sticks", "created_by": "Hal",
              "priority": "high", "status": "open"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "open=99" in response.headers["location"]
    assert repo.tickets[-1].title == "Drawbridge sticks"


def test_create_rejects_blank_title_and_keeps_what_was_typed(client, repo):
    response = client.post(
        "/petitions",
        data={"title": "   ", "created_by": "Hal", "priority": "high", "status": "open"},
    )
    assert response.status_code == 400
    assert "Petition is required." in response.text
    assert 'value="Hal"' in response.text
    assert len(repo.tickets) == 3


def test_create_rejects_overlong_title(client):
    response = client.post(
        "/petitions",
        data={"title": "x" * 300, "created_by": "Hal", "priority": "low", "status": "open"},
    )
    assert response.status_code == 400
    assert "255 characters" in response.text


def test_append_testimony(client, repo):
    response = client.post(
        "/petitions/41/messages",
        data={"author": "Hal", "message_text": "Mended.", "back": "/?open=41"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "msg=appended" in response.headers["location"]
    assert repo.messages[41][-1].message_text == "Mended."


def test_append_rejects_empty_testimony(client, repo):
    client.post("/petitions/41/messages",
                data={"author": "Hal", "message_text": "  ", "back": "/?open=41"},
                follow_redirects=False)
    assert len(repo.messages[41]) == 2


def test_alter_updates_standing_and_urgency(client, repo):
    client.post("/petitions/41",
                data={"status": "resolved", "priority": "low", "back": "/?open=41"},
                follow_redirects=False)
    assert repo.updated == [(41, "resolved", "low")]


def test_delete_requires_the_oath(client, repo):
    client.post("/petitions/41/delete", data={}, follow_redirects=False)
    assert repo.deleted == []

    client.post("/petitions/41/delete", data={"sworn": "yes"}, follow_redirects=False)
    assert repo.deleted == [41]


def test_redirect_target_cannot_leave_the_app(client):
    response = client.post(
        "/petitions/41/messages",
        data={"author": "Hal", "message_text": "Hi", "back": "https://evil.test/steal"},
        follow_redirects=False,
    )
    assert response.headers["location"].startswith("/")


def test_flash_text_comes_from_codes_not_the_url(client):
    assert "Petition 41 entered in the ledger." in client.get("/?msg=entered&n=41").text
    assert "<script>" not in client.get("/?msg=<script>alert(1)</script>&n=1").text


def test_health_needs_no_database():
    assert TestClient(app).get("/health").json() == {"status": "ok"}
