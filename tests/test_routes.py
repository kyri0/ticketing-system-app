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


def test_statistics_are_rendered_as_three_panels(client):
    page = client.get("/").text
    assert page.count('class="panel-tally') == 3
    assert 'class="panel-tally total"' in page
    assert "By standing" in page and "By urgency" in page
    assert "in all" not in page


def test_total_is_its_own_card_at_the_start(client):
    page = client.get("/").text
    assert page.index('panel-tally total') < page.index("By standing")


def test_both_breakdowns_show_every_bucket(client):
    page = client.get("/").text
    for label in ("Open", "Underway", "Settled", "Trifling", "Ordinary", "Pressing", "Dire"):
        assert label in page
    # one count element per bucket, standing and urgency alike
    assert page.count('class="v s-') == 3 and page.count('class="v u-') == 4


def test_create_redirects_and_opens_the_new_petition(client, repo):
    response = client.post(
        "/petitions",
        data={"title": "Drawbridge sticks", "created_by": "Hal", "priority": "high"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "open=99" in response.headers["location"]
    assert repo.tickets[-1].title == "Drawbridge sticks"


def test_new_petitions_always_enter_open(client, repo):
    client.post(
        "/petitions",
        data={"title": "Wolves at the gate", "created_by": "Hal", "priority": "urgent"},
        follow_redirects=False,
    )
    assert repo.tickets[-1].status == "open"


def test_standing_cannot_be_chosen_at_creation(client, repo):
    """A crafted POST must not be able to file a petition already Settled."""
    client.post(
        "/petitions",
        data={"title": "Sneaky", "created_by": "Hal", "priority": "low",
              "status": "resolved"},
        follow_redirects=False,
    )
    assert repo.tickets[-1].status == "open"


def test_creation_form_offers_no_standing_control(client):
    dialog = client.get("/").text.split('<dialog')[1]
    assert 'name="status"' not in dialog


def test_filter_by_petitioner(client):
    page = client.get("/?by=Gareth").text
    assert "Showing 1 of 3 petitions" in page
    assert "Portcullis jams on the north gate" in page
    assert "Moat is somewhat malodorous" not in page


def test_petitioner_filter_lists_only_names_in_the_ledger(client):
    page = client.get("/").text
    for name in ("Gareth", "Alys", "Hob"):
        assert f'name="by" value="{name}"' in page


def test_petitioner_filter_combines_with_other_filters(client):
    assert "Showing 0 of 3 petitions" in client.get("/?by=Gareth&standing=resolved").text


def test_petitioner_filter_survives_a_redirect(client):
    response = client.post(
        "/petitions/41/messages",
        data={"author": "Hal", "message_text": "Noted.", "back": "/?by=Gareth&open=41"},
        follow_redirects=False,
    )
    assert "by=Gareth" in response.headers["location"]


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


def test_filters_still_work_without_javascript(client):
    """The Sift button must survive in the markup as the no-JS fallback."""
    assert 'id="sift-go"' in client.get("/").text


def test_open_panel_is_remembered_so_several_boxes_can_be_ticked(client):
    page = client.get("/?panel=urgency&urgency=urgent").text
    assert 'data-panel="urgency" open' in page
    assert 'data-panel="standing" open' not in page


def test_unknown_panel_value_is_ignored(client):
    page = client.get("/?panel=../etc/passwd").text
    assert "open>" not in page.split('<p class="rule">Sift')[1][:400]


def test_create_panel_is_a_modal_opened_from_the_sidebar(client):
    page = client.get("/").text
    assert page.index('id="summon"') < page.index('<main class="main">')
    assert '<dialog id="scriptorium"' in page
    # closed by default, and the dialog sits outside the main column
    assert '<dialog id="scriptorium" class="scriptorium" >' in page


def test_failed_creation_reopens_the_modal_with_values_intact(client):
    response = client.post(
        "/petitions", data={"title": "  ", "created_by": "Hal", "priority": "high"}
    )
    assert response.status_code == 400
    dialog = response.text.split('<dialog')[1]
    assert "open>" in dialog.split('>')[0] + ">"
    assert 'value="Hal"' in dialog


def test_petitioner_appears_in_the_ledger_rows(client):
    page = client.get("/").text
    header = page.split("<tbody>")[0]
    assert "Petitioner" in header
    assert '<td class="col-p">Gareth</td>' in page


def test_petitioner_is_a_labelled_fact_in_the_open_card(client):
    card = client.get("/?open=41").text.split('class="card"')[1]
    assert "<dt>Petitioner</dt>" in card and "<dd>Gareth</dd>" in card


def test_standing_stays_in_its_own_column(client):
    page = client.get("/").text
    assert '<th class="col-s">Standing</th>' in page
    assert '<td class="col-s">' in page


def test_health_needs_no_database():
    assert TestClient(app).get("/health").json() == {"status": "ok"}
