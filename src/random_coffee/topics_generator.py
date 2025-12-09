"""
Topics generator module for Random Coffee Bot.

Fetches historical events from Wikipedia for the past 7 days and uses
ChatGPT to suggest interesting conversation topics.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import requests
from openai import OpenAI

logger = logging.getLogger("RandomCoffeeBot")


def get_past_week_dates(reference_date: Optional[datetime] = None) -> list[tuple[str, int]]:
    """
    Get the dates for the past 7 days including the reference date (Tuesday),
    but excluding the previous Tuesday.

    Args:
        reference_date: The reference date (typically Tuesday).
                       If None, uses current date.

    Returns:
        List of tuples (month_name, day) for 7 days:
        includes today (Tuesday), excludes previous Tuesday.
    """
    if reference_date is None:
        reference_date = datetime.now()

    dates = []
    # Include today (day 0) through 6 days ago, excluding 7 days ago (previous Tuesday)
    for i in range(7):
        date = reference_date - timedelta(days=i)
        month_name = date.strftime("%B")
        day = date.day
        dates.append((month_name, day))

    return dates


def fetch_wikipedia_page(month: str, day: int) -> Optional[str]:
    """
    Fetch content from a Wikipedia 'On this day' page.

    Args:
        month: Month name (e.g., "December")
        day: Day number (e.g., 7)

    Returns:
        Wikipedia page content as text, or None if fetch failed.
    """
    url = f"https://en.wikipedia.org/wiki/{month}_{day}"

    headers = {
        "User-Agent": "RandomCoffeeBot/1.0 (https://github.com/random-coffee-bot; contact@example.com) Python/requests"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Failed to fetch Wikipedia page for {month}_{day}: {e}")
        return None


def extract_events_from_page(client: OpenAI, page_content: str, month: str, day: int) -> list[str]:
    """
    Use ChatGPT to extract interesting events from a Wikipedia page.

    Args:
        client: OpenAI client instance
        page_content: Raw HTML content from Wikipedia
        month: Month name for context
        day: Day number for context

    Returns:
        List of up to 5 interesting events/facts.
    """
    prompt = f"""Analyze this Wikipedia page for {month} {day} and extract exactly 5 FUN and ENTERTAINING items.

Select items from these categories:
- Quirky or unusual holidays and observances (like "National Pizza Day" or fun cultural celebrations)
- Funny, bizarre, or surprising historical events (avoid wars, tragedies, political events)
- Celebrity birthdays (actors, musicians, comedians, athletes - people known for entertainment)
- Pop culture moments, weird world records, or amusing historical coincidences

Requirements:
- AVOID serious topics like wars, deaths, political events, tragedies
- Choose LIGHTHEARTED items that would make people smile or laugh
- Prefer fun facts, celebrity gossip, quirky holidays, and entertaining trivia
- Keep each item to 1-2 sentences with a fun/playful tone
- Make them great for casual, fun coffee conversation

Return exactly 5 items, one per line, without numbering or bullet points.

Wikipedia page content:
{page_content[:15000]}"""  # Limit content to avoid token limits

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a fun, upbeat assistant that finds entertaining and amusing facts from Wikipedia. You love pop culture, quirky holidays, celebrity trivia, and weird historical fun facts. You avoid serious, depressing, or heavy topics."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.8
        )

        content = response.choices[0].message.content
        if content:
            events = [line.strip() for line in content.strip().split('\n') if line.strip()]
            return events[:5]  # Ensure max 5 items
        return []
    except Exception as e:
        logger.error(f"Failed to extract events for {month} {day}: {e}")
        return []


def select_final_topics(client: OpenAI, all_events: list[str]) -> list[str]:
    """
    Use ChatGPT to select the 5 best conversation topics from all collected events.

    Args:
        client: OpenAI client instance
        all_events: List of all events collected from the past week

    Returns:
        List of 5 final conversation topics.
    """
    events_text = "\n".join(f"- {event}" for event in all_events)

    prompt = f"""From this list of fun facts and entertaining events from the past week, select the 5 MOST FUN and ENTERTAINING topics for a casual coffee conversation between colleagues.

Criteria for selection:
- FUN FACTOR: Must be lighthearted, amusing, or make people smile
- Conversation spark: Topics that lead to fun discussions, debates about favorites, or sharing personal stories
- Diversity: Mix of celebrity birthdays, quirky holidays, pop culture, and fun trivia
- AVOID anything serious, political, or depressing

Available topics:
{events_text}

Return exactly 5 topics, formatted as fun, playful conversation starters. Each should be 1-2 sentences with an upbeat tone that would make someone smile and want to chat about it!

Format each topic on its own line, without numbering or bullet points."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a fun, cheerful assistant helping colleagues find entertaining conversation topics for their weekly coffee chat. You love pop culture, celebrity gossip, quirky holidays, and amusing trivia. Keep everything light and fun!"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.9
        )

        content = response.choices[0].message.content
        if content:
            topics = [line.strip() for line in content.strip().split('\n') if line.strip()]
            return topics[:5]
        return []
    except Exception as e:
        logger.error(f"Failed to select final topics: {e}")
        return []


def generate_conversation_topics(openai_api_key: str, reference_date: Optional[datetime] = None) -> list[str]:
    """
    Main function to generate conversation topics based on the past week's events.

    This function:
    1. Gets dates for the past 7 days
    2. Fetches Wikipedia pages for each day
    3. Extracts 5 interesting events from each page using ChatGPT
    4. Selects the 5 best overall topics using ChatGPT

    Args:
        openai_api_key: OpenAI API key for ChatGPT requests
        reference_date: Reference date (typically Tuesday). If None, uses current date.

    Returns:
        List of 5 conversation topic suggestions.
    """
    client = OpenAI(api_key=openai_api_key)

    dates = get_past_week_dates(reference_date)
    logger.info(f"Fetching events for dates: {dates}")

    all_events = []

    for month, day in dates:
        logger.info(f"Processing {month} {day}")

        page_content = fetch_wikipedia_page(month, day)
        if page_content:
            events = extract_events_from_page(client, page_content, month, day)
            all_events.extend(events)
            logger.info(f"Extracted {len(events)} events for {month} {day}")
        else:
            logger.warning(f"Skipping {month} {day} due to fetch failure")

    if not all_events:
        logger.error("No events collected from any day")
        return []

    logger.info(f"Total events collected: {len(all_events)}")

    final_topics = select_final_topics(client, all_events)
    logger.info(f"Selected {len(final_topics)} final topics")

    return final_topics


def convert_markdown_to_slack(text: str) -> str:
    """
    Convert markdown formatting to Slack formatting.

    Args:
        text: Text with markdown formatting

    Returns:
        Text with Slack formatting.
    """
    import re
    # Convert **bold** to *bold* (Slack uses single asterisks for bold)
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    return text


def format_topics_for_slack(topics: list[str]) -> str:
    """
    Format the conversation topics for Slack message.

    Args:
        topics: List of conversation topics

    Returns:
        Formatted string ready for Slack message.
    """
    if not topics:
        return ""

    lines = [
        "\n🎉 *Fun Conversation Starters for This Week:* 🎉\n",
        "_Some entertaining things that happened this past week in history..._\n\n"
    ]

    for i, topic in enumerate(topics, 1):
        formatted_topic = convert_markdown_to_slack(topic)
        lines.append(f"{i}. {formatted_topic}\n")

    return "".join(lines)
