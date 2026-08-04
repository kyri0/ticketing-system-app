"""Parameterized Lakebase queries for support tickets and their messages."""

from __future__ import annotations

import logging

from dataclasses import dataclass
from datetime import datetime

import psycopg2

from ticketing.database import LakebasePool
from ticketing.validation import valid_priority, valid_status


logger = logging.getLogger(__name__)


class DatabaseOperationError(RuntimeError):
    """A database request failed without exposing connection details to the UI."""


def _fail(summary: str, error: Exception) -> DatabaseOperationError:
    """Log the full driver error, and surface Postgres's own words to the UI.

    A bare 'could not do the thing' is undiagnosable in a deployed app. The
    Postgres primary message names the real cause — a missing column, a failed
    CHECK, a denied privilege — without leaking host or credential details.
    """
    logger.exception(summary)
    detail = ""
    diagnostic = getattr(error, "diag", None)
    if diagnostic is not None:
        primary = getattr(diagnostic, "message_primary", None)
        code = getattr(diagnostic, "sqlstate", None)
        if primary:
            detail = f" {primary}" + (f" [{code}]" if code else "")
    return DatabaseOperationError(f"{summary}{detail}")


class TicketNotFoundError(DatabaseOperationError):
    """The requested ticket no longer exists."""


@dataclass(frozen=True)
class Ticket:
    ticket_id: int
    title: str
    status: str
    priority: str
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class LedgerTally:
    """Aggregate counts computed by the database, not by filtering in Python."""

    total: int
    by_status: dict[str, int]
    by_priority: dict[str, int]


@dataclass(frozen=True)
class TicketMessage:
    message_id: int
    ticket_id: int
    message_text: str
    author: str
    created_at: datetime


class TicketRepository:
    """Owns all direct access to the existing Lakebase tables.

    Schema (public):
        tickets(ticket_id BIGINT IDENTITY PK, title VARCHAR(255), status VARCHAR(50),
                created_by VARCHAR(255), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        ticket_messages(message_id BIGINT IDENTITY PK, ticket_id BIGINT FK -> tickets
                        ON DELETE CASCADE, message_text TEXT, author VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)

    Both primary keys are GENERATED ALWAYS AS IDENTITY, so the database assigns
    them and the application must never supply a value. created_at is likewise
    left to the column default.

    The pool yields psycopg2 connections with a RealDictCursor factory, so rows
    arrive as dicts. `with connection:` delimits a transaction and commits on a
    clean exit; it does not close the connection, which the pool reclaims.
    """

    def __init__(self, pool: LakebasePool):
        self._pool = pool

    def list_tickets(self) -> list[Ticket]:
        try:
            with self._pool.connection() as connection:
                with connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            SELECT ticket_id, title, status, priority, created_by, created_at
                            FROM public.tickets
                            ORDER BY created_at DESC, ticket_id DESC
                            """
                        )
                        return [Ticket(**row) for row in cursor.fetchall()]
        except psycopg2.Error as error:
            raise _fail("Could not load tickets from Lakebase.", error) from error

    def list_messages(self, ticket_id: int) -> list[TicketMessage]:
        try:
            with self._pool.connection() as connection:
                with connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            SELECT message_id, ticket_id, message_text, author, created_at
                            FROM public.ticket_messages
                            WHERE ticket_id = %s
                            ORDER BY created_at ASC, message_id ASC
                            """,
                            (ticket_id,),
                        )
                        return [TicketMessage(**row) for row in cursor.fetchall()]
        except psycopg2.Error as error:
            raise _fail("Could not load ticket messages from Lakebase.", error) from error

    def create_ticket(
        self, title: str, status: str, priority: str, created_by: str
    ) -> Ticket:
        valid_status(status)
        valid_priority(priority)
        try:
            with self._pool.connection() as connection:
                with connection:
                    with connection.cursor() as cursor:
                        # ticket_id is GENERATED ALWAYS AS IDENTITY and created_at
                        # defaults to CURRENT_TIMESTAMP; the database owns both.
                        cursor.execute(
                            """
                            INSERT INTO public.tickets (title, status, priority, created_by)
                            VALUES (%s, %s, %s, %s)
                            RETURNING ticket_id, title, status, priority, created_by, created_at
                            """,
                            (title, status, priority, created_by),
                        )
                        return Ticket(**cursor.fetchone())
        except psycopg2.Error as error:
            raise _fail("Could not create the ticket in Lakebase.", error) from error

    def add_message(self, ticket_id: int, message_text: str, author: str) -> TicketMessage:
        try:
            with self._pool.connection() as connection:
                with connection:
                    with connection.cursor() as cursor:
                        # message_id is GENERATED ALWAYS AS IDENTITY and created_at
                        # defaults to CURRENT_TIMESTAMP; the database owns both.
                        cursor.execute(
                            """
                            INSERT INTO public.ticket_messages
                                (ticket_id, message_text, author)
                            VALUES (%s, %s, %s)
                            RETURNING message_id, ticket_id, message_text, author, created_at
                            """,
                            (ticket_id, message_text, author),
                        )
                        return TicketMessage(**cursor.fetchone())
        except psycopg2.errors.ForeignKeyViolation as error:
            # fk_ticket_messages_ticket: the ticket was deleted concurrently.
            raise TicketNotFoundError("This ticket no longer exists.") from error
        except psycopg2.Error as error:
            raise _fail("Could not add the message in Lakebase.", error) from error

    def update_ticket(self, ticket_id: int, status: str, priority: str) -> Ticket:
        """Set standing and urgency together, so one submission is one write."""
        valid_status(status)
        valid_priority(priority)
        try:
            with self._pool.connection() as connection:
                with connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE public.tickets
                            SET status = %s, priority = %s
                            WHERE ticket_id = %s
                            RETURNING ticket_id, title, status, priority, created_by, created_at
                            """,
                            (status, priority, ticket_id),
                        )
                        row = cursor.fetchone()
                        if row is None:
                            raise TicketNotFoundError("This ticket no longer exists.")
                        return Ticket(**row)
        except psycopg2.errors.CheckViolation as error:
            # chk_tickets_priority rejected the value.
            raise _fail(f"The ledger does not recognise the urgency '{priority}'.", error) from error
        except psycopg2.Error as error:
            raise _fail("Could not update the ticket in Lakebase.", error) from error

    def tally(self) -> LedgerTally:
        """Count tickets by standing and urgency in one aggregate query."""
        try:
            with self._pool.connection() as connection:
                with connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            SELECT status, priority, COUNT(*) AS total
                            FROM public.tickets
                            GROUP BY status, priority
                            """
                        )
                        by_status: dict[str, int] = {}
                        by_priority: dict[str, int] = {}
                        total = 0
                        for row in cursor.fetchall():
                            count = int(row["total"])
                            total += count
                            by_status[row["status"]] = by_status.get(row["status"], 0) + count
                            by_priority[row["priority"]] = (
                                by_priority.get(row["priority"], 0) + count
                            )
                        return LedgerTally(total, by_status, by_priority)
        except psycopg2.Error as error:
            raise _fail("Could not tally the ledger in Lakebase.", error) from error

    def delete_ticket(self, ticket_id: int) -> None:
        """Delete a ticket. Its messages go with it via ON DELETE CASCADE."""
        try:
            with self._pool.connection() as connection:
                with connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "DELETE FROM public.tickets WHERE ticket_id = %s",
                            (ticket_id,),
                        )
                        if cursor.rowcount == 0:
                            raise TicketNotFoundError("This ticket no longer exists.")
        except psycopg2.Error as error:
            raise _fail("Could not delete the ticket in Lakebase.", error) from error
