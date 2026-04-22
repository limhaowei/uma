import calendar
import logging
from datetime import datetime
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = "https://uma.moe/api/v4/circles"


async def _fetch_month(
    session: aiohttp.ClientSession, circle_id: str, year: int, month: int
) -> Optional[dict]:
    params = {"circle_id": circle_id, "year": year, "month": month}
    async with session.get(
        BASE_URL, params=params, timeout=aiohttp.ClientTimeout(total=30)
    ) as resp:
        if resp.status != 200:
            text = await resp.text()
            logger.error(f"Uma.moe API {resp.status} for {year}-{month:02d}: {text[:200]}")
            return None
        return await resp.json()


def _parse_members(raw_members: list, data_day: int) -> list:
    """
    Convert Uma.moe's lifetime-cumulative daily_fans array into monthly earned fans.

    daily_fans is 0-indexed: index 0 = day 1, index N-1 = day N.
    Join day is the first index where fans > 0 (1-based day number).
    Monthly earned = fans[data_day - 1] - fans[join_day - 1].
    """
    results = []
    day_index = data_day - 1

    for member in raw_members:
        viewer_id = member.get("viewer_id")
        trainer_name = member.get("trainer_name")
        lifetime_fans = member.get("daily_fans", [])

        if not viewer_id or not trainer_name:
            continue
        if day_index >= len(lifetime_fans):
            continue

        current_lifetime = lifetime_fans[day_index]
        # Member has left the club
        if current_lifetime == 0:
            continue

        # Find join day: first index with non-zero fans (1-based)
        join_day = 1
        starting_lifetime = 0
        for idx, fans in enumerate(lifetime_fans[: data_day], start=1):
            if fans > 0:
                join_day = idx
                starting_lifetime = fans
                break

        monthly_earned = current_lifetime - starting_lifetime

        # Fans earned on data_day specifically (0 if it's their first day)
        if data_day > join_day and data_day >= 2:
            prev_lifetime = lifetime_fans[data_day - 2]
            daily_earned = current_lifetime - prev_lifetime
        else:
            daily_earned = monthly_earned

        results.append(
            {
                "trainer_name": trainer_name,
                "monthly_earned": monthly_earned,
                "daily_earned": daily_earned,
                "join_day": join_day,
            }
        )

    results.sort(key=lambda m: m["monthly_earned"], reverse=True)
    return results


async def fetch_club_data(circle_id: str) -> dict:
    """
    Fetch and parse club member data from the Uma.moe API.

    Returns a dict:
        {
            "members": [{"trainer_name", "monthly_earned", "join_day"}, ...],
            "data_day": int  # which day-of-month the data represents
        }

    Handles two edge cases automatically:
      - Day 1 of the month: the new month isn't populated yet, so the previous
        month is fetched and its last day is used.
      - Data not yet published for today (~15:10 UTC update): falls back to
        the previous day's data.
    """
    now = datetime.now()
    year, month, today = now.year, now.month, now.day

    # Day 1: fetch the previous month's final day
    if today == 1:
        if month == 1:
            year, month = year - 1, 12
        else:
            month -= 1
        data_day = calendar.monthrange(year, month)[1]
        logger.info(f"Day 1: fetching previous month {year}-{month:02d}, data_day={data_day}")
    else:
        data_day = today

    async with aiohttp.ClientSession() as session:
        data = await _fetch_month(session, circle_id, year, month)

    if not data or "members" not in data:
        raise ValueError("Invalid or empty response from Uma.moe API")

    raw_members = data["members"]

    # Check whether today's slot in the array is actually populated yet
    if today > 1:
        today_index = today - 1
        has_today = any(
            len(m.get("daily_fans", [])) > today_index
            and m["daily_fans"][today_index] > 0
            for m in raw_members
        )
        if not has_today:
            data_day = today - 1
            logger.info(
                f"Day {today} data not available yet (Uma.moe updates ~15:10 UTC). "
                f"Falling back to day {data_day}."
            )

    members = _parse_members(raw_members, data_day)
    monthly_rank = (data.get("circle") or {}).get("monthly_rank")
    return {"members": members, "data_day": data_day, "monthly_rank": monthly_rank}
