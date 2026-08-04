"""The Ledger of Petitions — a Lakebase-backed support desk on FastAPI.

Server-rendered HTML, no client framework. Every mutation is POST → redirect →
GET, so a refresh never resubmits a form and the expanded petition stays in the
URL, which makes it shareable.

The medieval surface is entirely in `static/ledger.css` and `templates/`. The
data layer beneath it is plain Lakebase SQL — see `ticketing/repository.py`.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ticketing import theme
from ticketing.database import DatabaseConfigurationError, create_pool
from ticketing.repository import (
    DatabaseOperationError,
    LedgerTally,
    TicketRepository,
)
from ticketing.validation import (
    ALLOWED_PRIORITIES,
    ALLOWED_STATUSES,
    MAX_DESCRIPTION,
    MAX_MESSAGE,
    MAX_NAME,
    MAX_TITLE,
    ValidationError,
    required_text,
)

logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="The Ledger of Petitions")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals.update(
    standing_label=theme.standing_label,
    urgency_label=theme.urgency_label,
)

# 303 forces the browser to follow a POST with a GET, which is what makes
# refresh-after-submit harmless.
SEE_OTHER = 303

# Every petition enters the ledger Open; only an amendment moves it on.
OPENING_STANDING = "open"


@lru_cache(maxsize=1)
def _repository() -> TicketRepository:
    return TicketRepository(create_pool())


def get_repository() -> TicketRepository:
    """Dependency seam — tests override this with an in-memory double."""
    return _repository()


def _back_link(
    standing: list[str],
    urgency: list[str],
    by: list[str],
    q: str,
    sort: str,
    open_id: int | None,
) -> str:
    """Rebuild the current view as a URL so redirects land where you left off."""
    params: list[tuple[str, str]] = []
    params += [("standing", value) for value in standing]
    params += [("urgency", value) for value in urgency]
    params += [("by", value) for value in by]
    if q:
        params.append(("q", q))
    if sort != "urgency":
        params.append(("sort", sort))
    if open_id is not None:
        params.append(("open", str(open_id)))
    return "/?" + urlencode(params) if params else "/"


def _safe_back(back: str) -> str:
    """Only ever redirect within this app — never to an attacker's URL."""
    return back if back.startswith("/") and not back.startswith("//") else "/"


def _render(
    request: Request,
    repository: TicketRepository,
    *,
    standing: list[str],
    urgency: list[str],
    by: list[str],
    q: str,
    sort: str,
    open_id: int | None,
    panel: str = "",
    flash: str | None = None,
    error: str | None = None,
    draft: dict | None = None,
    status_code: int = 200,
):
    tickets = repository.list_tickets()
    tally = repository.tally()

    # The petitioner list is whoever actually appears in the ledger, so the
    # filter cannot offer a name that matches nothing.
    petitioners = sorted({ticket.created_by for ticket in tickets}, key=str.casefold)

    needle = q.strip().lower()
    visible = [
        ticket
        for ticket in tickets
        if (not standing or ticket.status in standing)
        and (not urgency or ticket.priority in urgency)
        and (not by or ticket.created_by in by)
        and (not needle or needle in ticket.title.lower()
             or needle in ticket.description.lower())
    ]
    if sort == "urgency":
        visible.sort(key=lambda t: (theme.URGENCY_RANK.get(t.priority, 9), -t.ticket_id))

    messages = []
    changes = []
    if open_id is not None and any(t.ticket_id == open_id for t in visible):
        messages = repository.list_messages(open_id)
        changes = repository.list_status_changes(open_id)
    else:
        open_id = None

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        status_code=status_code,
        context={
            "tickets": visible,
            "total_count": len(tickets),
            "tally": tally,
            "messages": messages,
            "changes": changes,
            "open_id": open_id,
            "statuses": ALLOWED_STATUSES,
            "priorities": ALLOWED_PRIORITIES,
            "petitioners": petitioners,
            "standing": standing,
            "urgency": urgency,
            "by": by,
            "q": q,
            "sort": sort,
            "panel": panel,
            "flash": flash,
            "error": error,
            "form_open": bool(error and draft),
            "draft": draft or {"title": "", "description": "",
                               "created_by": "", "priority": "medium"},
            "back": _back_link(standing, urgency, by, q, sort, open_id),
            "link": lambda oid: _back_link(standing, urgency, by, q, sort, oid),
        },
    )


@app.get("/petitions/{ticket_id}/card")
def petition_card(
    request: Request,
    ticket_id: int,
    back: str = "/",
    repository: TicketRepository = Depends(get_repository),
):
    """Render one petition card on its own.

    ledger.js fetches this and splices it into the table, so expanding a
    petition does not repaint the whole page. The same markup is rendered
    server-side into the full page, so both paths stay identical.
    """
    ticket = next(
        (t for t in repository.list_tickets() if t.ticket_id == ticket_id), None
    )
    if ticket is None:
        return HTMLResponse("", status_code=404)
    return templates.TemplateResponse(
        request=request,
        name="_card.html",
        context={
            "ticket": ticket,
            "messages": repository.list_messages(ticket_id),
            "changes": repository.list_status_changes(ticket_id),
            "statuses": ALLOWED_STATUSES,
            "priorities": ALLOWED_PRIORITIES,
            "back": _safe_back(back),
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Cheap liveness probe that does not touch the database."""
    return {"status": "ok"}


@app.get("/")
def ledger(
    request: Request,
    standing: list[str] = Query(default=[]),
    urgency: list[str] = Query(default=[]),
    by: list[str] = Query(default=[]),
    q: str = "",
    sort: str = "urgency",
    panel: str = "",
    open: int | None = None,
    msg: str | None = None,
    n: str | None = None,
    repository: TicketRepository = Depends(get_repository),
):
    # Ignore anything the URL invents, so a hand-edited query string cannot
    # smuggle values past validation.
    standing = [s for s in standing if s in ALLOWED_STATUSES]
    urgency = [u for u in urgency if u in ALLOWED_PRIORITIES]
    by = [b for b in by if b][:20]
    sort = sort if sort in ("urgency", "recent") else "urgency"
    panel = panel if panel in ("standing", "urgency", "by") else ""

    try:
        return _render(
            request,
            repository,
            standing=standing,
            urgency=urgency,
            by=by,
            q=q,
            sort=sort,
            open_id=open,
            panel=panel,
            flash=theme.flash_text(msg, n),
        )
    except (DatabaseConfigurationError, DatabaseOperationError) as error:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            status_code=503,
            context={
                "tickets": [], "total_count": 0, "messages": [], "changes": [], "open_id": None,
                "tally": LedgerTally(0, {}, {}),
                "statuses": ALLOWED_STATUSES, "priorities": ALLOWED_PRIORITIES,
                "petitioners": [],
                "standing": [], "urgency": [], "by": [], "q": "", "sort": "urgency",
                "panel": "",
                "flash": None, "error": str(error), "form_open": False,
                "draft": {"title": "", "description": "", "created_by": "", "priority": "medium"},
                "back": "/", "link": lambda oid: "/",
            },
        )


@app.post("/petitions")
def enter_petition(
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    created_by: str = Form(""),
    priority: str = Form("medium"),
    repository: TicketRepository = Depends(get_repository),
):
    # A petition always enters the ledger Open. The standing is not the
    # petitioner's to choose, so the form does not offer it and the route does
    # not read it — a crafted POST cannot create a pre-Settled petition.
    try:
        clean_title = required_text(title, "Title", max_length=MAX_TITLE)
        clean_body = required_text(description, "Grievance", max_length=MAX_DESCRIPTION)
        clean_by = required_text(created_by, "Petitioner", max_length=MAX_NAME)
        ticket = repository.create_ticket(
            clean_title, clean_body, OPENING_STANDING, priority, clean_by
        )
    except (ValidationError, DatabaseOperationError) as error:
        # Re-render with the typed values intact rather than redirecting away
        # from work the petitioner just did.
        return _render(
            request, repository,
            standing=[], urgency=[], by=[], q="", sort="urgency", open_id=None,
            error=str(error),
            draft={"title": title, "description": description,
                   "created_by": created_by, "priority": priority},
            status_code=400,
        )
    return RedirectResponse(
        f"/?{urlencode({'open': ticket.ticket_id, 'msg': 'entered', 'n': ticket.ticket_id})}",
        status_code=SEE_OTHER,
    )


@app.post("/petitions/{ticket_id}/messages")
def append_testimony(
    ticket_id: int,
    author: str = Form(""),
    message_text: str = Form(""),
    back: str = Form("/"),
    repository: TicketRepository = Depends(get_repository),
):
    target = _safe_back(back)
    try:
        clean_author = required_text(author, "Hand", max_length=MAX_NAME)
        clean_text = required_text(message_text, "Testimony", max_length=MAX_MESSAGE)
        repository.add_message(ticket_id, clean_text, clean_author)
    except (ValidationError, DatabaseOperationError) as error:
        logging.warning("append failed on %s: %s", ticket_id, error)
        return RedirectResponse(target, status_code=SEE_OTHER)
    joiner = "&" if "?" in target else "?"
    return RedirectResponse(
        f"{target}{joiner}{urlencode({'msg': 'appended', 'n': ticket_id})}",
        status_code=SEE_OTHER,
    )


@app.post("/petitions/{ticket_id}")
def alter_petition(
    ticket_id: int,
    status: str = Form("open"),
    priority: str = Form("medium"),
    hand: str = Form(""),
    back: str = Form("/"),
    repository: TicketRepository = Depends(get_repository),
):
    target = _safe_back(back)
    try:
        # Without a hand the history reads "unknown", which makes the log
        # worthless — so it is required rather than defaulted.
        clean_hand = required_text(hand, "Hand", max_length=MAX_NAME)
        repository.update_ticket(ticket_id, status, priority, clean_hand)
    except (ValidationError, DatabaseOperationError) as error:
        logging.warning("alter failed on %s: %s", ticket_id, error)
        return RedirectResponse(target, status_code=SEE_OTHER)
    joiner = "&" if "?" in target else "?"
    return RedirectResponse(
        f"{target}{joiner}{urlencode({'msg': 'amended', 'n': ticket_id})}",
        status_code=SEE_OTHER,
    )


@app.post("/petitions/{ticket_id}/delete")
def strike_petition(
    ticket_id: int,
    sworn: str = Form(""),
    repository: TicketRepository = Depends(get_repository),
):
    # The checkbox is `required` in the markup; this is the server-side half of
    # the confirmation, since markup is trivially bypassed.
    if sworn != "yes":
        return RedirectResponse("/", status_code=SEE_OTHER)
    try:
        repository.delete_ticket(ticket_id)
    except DatabaseOperationError as error:
        logging.warning("strike failed on %s: %s", ticket_id, error)
        return RedirectResponse("/", status_code=SEE_OTHER)
    return RedirectResponse(
        f"/?{urlencode({'msg': 'struck', 'n': ticket_id})}", status_code=SEE_OTHER
    )
