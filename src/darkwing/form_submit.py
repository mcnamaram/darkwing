from __future__ import annotations

import asyncio
from playwright.async_api import async_playwright, BrowserContext
from dotenv import load_dotenv

import os

from darkwing.schema import (
    FLIGHTS_TRANSLATION,
    NESTING_STAGE_CODE_TO_TEXT,
    BILL_USE_CODE_TO_TEXT,
    AWAKE_CODE_TO_TEXT,
)

load_dotenv()

async def submit_csv_records(records, dry_run=False):
    """Submit a list of ObservationRecords to the Google Form.

    Returns a list of dicts with submission results for each record.
    Each dict contains:
        - 'record': the original ObservationRecord
        - 'status': 'success', 'dry-run', or 'error'
        - 'error': error message if status is 'error'
    """
    if dry_run:
        results = [
            {'record': rec, 'status': 'dry-run', 'error': None}
            for rec in records
        ]
        return results

    p, context = await load_form()
    try:
        results = []
        for rec in records:
            try:
                if dry_run:
                    results.append({
                        'record': rec,
                        'status': 'dry-run',
                        'error': None,
                    })
                else:
                    success = await submit_observation(
                        submitter_name=os.getenv("DARKWING_SUBMITTER_NAME"),
                        tower=rec.tower,
                        date_str=rec.date_str,
                        hour=rec.hour,
                        minutes_past_hour=rec.minutes_past_hour,
                        num_adults=rec.num_adults,
                        num_adults_other=rec.num_adults_other,
                        nesting_stage=rec.nesting_stage,
                        bill_use=rec.bill_use,
                        flights=rec.flights,
                        num_near_nest=rec.num_near_nest,
                        num_near_nest_other=rec.num_near_nest_other,
                        awake=rec.awake,
                        notes=rec.notes,
                        context=context
                    )
                    if success:
                        results.append({
                            'record': rec,
                            'status': 'success',
                            'error': None,
                        })
                    else:
                        results.append({
                            'record': rec,
                            'status': 'error',
                            'error': 'Submission failed',
                        })
                    await clear_form(context)
            except Exception as exc:
                results.append({
                    'record': rec,
                    'status': 'error',
                    'error': str(exc),
                })
    finally:
        await unload_form(p, context)

    return results


async def load_form():
    """Load the Google Form in a Playwright browser context.

    Returns a tuple of (playwright, context) — caller must call unload_form().
    """
    p = await async_playwright().start()
    user_data_dir = os.path.join(os.getcwd(), "google_profile")

    context = await p.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=os.getenv("DARKWING_HEADLESS", "true").lower() not in ("false", "0", "no"),
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        args=[
            "--disable-blink-features=AutomationControlled",
        ],
        ignore_default_args=["--enable-automation"],
        slow_mo=500,
    )
    await clear_form(context)
    return p, context

async def clear_form(context: BrowserContext):
    """Clear the form fields in the browser context."""
    form_url = os.getenv("DARKWING_FORM_URL")
    if not form_url:
        raise ValueError("DARKWING_FORM_URL not set in environment")

    page = context.pages[0]
    await page.goto(form_url)
    await page.wait_for_load_state("networkidle")
    await page.get_by_role("button", name="Clear form").click()
    await page.wait_for_timeout(500)
    await page.get_by_role("button", name="Clear form").click()


async def unload_form(p, context: BrowserContext):
    """Close the browser context and stop Playwright."""
    await context.close()
    await p.stop()

async def submit_observation(
        submitter_name: str,
        tower: int,
        date_str: str,
        hour: int,
        minutes_past_hour: int,
        num_adults: int,
        num_adults_other: str | None,
        nesting_stage: str,
        bill_use: list[str],
        flights: list[str],
        num_near_nest: int,
        num_near_nest_other: str | None,
        awake: str,
        notes: str,
        context: BrowserContext | None = None
) -> bool:
    """Submit one observation record. Returns True on success."""
    # Expand short codes to long-form labels for form interaction
    nesting_stage_label = NESTING_STAGE_CODE_TO_TEXT[nesting_stage]
    bill_use_labels = [BILL_USE_CODE_TO_TEXT[b] for b in bill_use]
    flights_labels = [FLIGHTS_TRANSLATION[f] for f in flights]
    awake_label = AWAKE_CODE_TO_TEXT[awake]

    page = context.pages[0]

    # ── Header fields (direct role selectors) ──────────────────────────────
    await page.get_by_role("checkbox", name="Record").click()
    await page.get_by_role("textbox", name="Name (first, last)").fill(submitter_name)
    await page.get_by_role("radio", name=f"Tower {tower}").click()
    await page.get_by_role("textbox", name="Date").press_sequentially(date_str)
    await page.get_by_role("textbox", name="Hour of footage").fill(str(hour))
    await page.get_by_role("radio", name=f"{minutes_past_hour:02d}").click()

    # ── Adult swallows ──────────────────────────────────────────────────────
    swallows_group = page.get_by_role("radiogroup", name="How many adult Swifts are")
    if num_adults_other is not None:
        await swallows_group.get_by_label("Other response").fill(str(num_adults_other))
    else:
        await swallows_group.get_by_role("radio", name=f"{num_adults}", exact=True).click()

    # ── Nesting cycle ───────────────────────────────────────────────────────
    await page.get_by_role("radiogroup", name="Nesting Cycle"
    ).get_by_role("radio", name=nesting_stage_label, exact=True).click()

    # ── Bill use ─────────────────────────────────────────────────────────────
    bill_group = page.get_by_role("list", name="something in their bill")
    if "N/A or No" in bill_use_labels:
        await bill_group.get_by_role("checkbox", name="N/A or No", exact=True).click()
    else:
        for bill in bill_use_labels:
            await bill_group.get_by_role("checkbox", name=bill, exact=True).click()

    # ── Flights ──────────────────────────────────────────────────────────────
    flight_group = page.get_by_role("list", name="Did you observe any flight")
    if "None of the above" in flights_labels:
        await flight_group.get_by_role("checkbox", name="None of the above").click()
    else:
        for flight in flights_labels:
            await flight_group.get_by_role("checkbox", name=flight, exact=True).click()

    # ── Near nest ────────────────────────────────────────────────────────────
    near_group = page.get_by_role("radiogroup", name="two body-lengths")
    if num_near_nest_other is not None:
        if num_near_nest_other == "N/A or Zero":
            await near_group.get_by_role("radio", name="N/A or Zero").click()
        else:
            await near_group.get_by_label("Other response").fill(str(num_near_nest_other))
    else:
        await near_group.get_by_role("radio", name=f"{num_near_nest}").click()

    # ── Awake ────────────────────────────────────────────────────────────────
    await page.get_by_role("radio", name=awake_label, exact=True).click()

    # ── Notes ────────────────────────────────────────────────────────────────
    await page.get_by_role("textbox", name="Note any interesting").fill(notes)

    # ── Clear for next submission ───────────────────────────────────────────
    # await clear_form(context) # for testing, we don't clear the form to avoid losing the filled data
    
    # -- Submit the form
    await page.get_by_role("button", name="Submit").click()
    await page.wait_for_timeout(1000)

    return True


def test_submit_record() -> dict:
    """Test helper for submit_csv_records."""
    from unittest.mock import MagicMock
    context = MagicMock()
    page = MagicMock()
    context.pages = [page]
    return context


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m darkwing.form_submit <csv_file>")
        sys.exit(1)

    from pathlib import Path
    csv_path = Path(sys.argv[1])
    from darkwing.csv_io import read_csv
    records = read_csv(csv_path)

    results = asyncio.run(submit_csv_records(records))
    for r in results:
        print(f"{r['status']}: {r['record'].tower} {r['record'].date_str} {r['record'].time_of_day}")
