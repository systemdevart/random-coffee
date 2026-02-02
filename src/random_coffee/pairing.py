"""
Pairing module for Random Coffee bot.

This module can be run standalone to test and modify the pairing algorithm
without posting messages to Slack.
"""

import re
import random
import logging
from datetime import datetime, timedelta
from typing import Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger("RandomCoffeeBot")


def get_channel_id(client: WebClient, channel: str) -> Optional[str]:
    """Get channel ID from channel name."""
    if channel.startswith("#"):
        channel = channel[1:]

    response = client.conversations_list(types="public_channel,private_channel")
    for ch in response["channels"]:
        if ch["name"] == channel:
            return ch["id"]
    return None


def fetch_recent_pairs(
    client: WebClient, channel: str, days: int = 40
) -> set[tuple[str, str]]:
    """
    Fetch recently paired users from channel messages.

    Args:
        client: Slack WebClient instance
        channel: Channel name
        days: Number of days to look back (default 40)

    Returns:
        Set of tuples (user_id_1, user_id_2) representing blocked pairs
    """
    channel_id = get_channel_id(client, channel)
    if not channel_id:
        logger.warning(f"Channel {channel} not found, no history available")
        return set()

    oldest = datetime.now() - timedelta(days=days)
    oldest_ts = oldest.timestamp()

    try:
        response = client.conversations_history(
            channel=channel_id,
            oldest=str(oldest_ts),
            limit=200,
        )
        messages = response.get("messages", [])
        logger.info(f"Fetched {len(messages)} messages from last {days} days")

    except SlackApiError as e:
        logger.error(f"Error fetching channel history: {e.response['error']}")
        return set()

    # Pattern to match user mentions like <@U059CM6C7J9>
    user_pattern = re.compile(r"<@(U[A-Z0-9]+)>")
    coffee_indicators = ["coffee lovers", "random coffee", "pairings"]

    blocked_pairs: set[tuple[str, str]] = set()

    for msg in messages:
        text = msg.get("text", "").lower()

        # Check if this is a Random Coffee message
        if not any(indicator in text for indicator in coffee_indicators):
            continue

        # Parse pairs from each line
        # Format: "1. <@U1> & <@U2>" or "1. <@U1>, <@U2> & <@U3> (trio)"
        lines = msg.get("text", "").split("\n")
        for line in lines:
            mentions = user_pattern.findall(line)
            if len(mentions) >= 2:
                # Add all combinations as blocked (handles trios)
                for i in range(len(mentions)):
                    for j in range(i + 1, len(mentions)):
                        pair = tuple(sorted([mentions[i], mentions[j]]))
                        blocked_pairs.add(pair)

    logger.info(f"Found {len(blocked_pairs)} blocked pairs from recent history")
    return blocked_pairs


EXCLUDED_USERNAMES = [
    "admin",
    "v2v@dubformer.ai",
    "Eugene Gritskevich",
    "eg@dubformer.ai",
]


def get_channel_members(client: WebClient, channel: str) -> list[dict]:
    """
    Fetch members from a Slack channel.

    Args:
        client: Slack WebClient instance
        channel: Channel name (with or without # prefix)

    Returns:
        List of member dicts with 'id' and 'name' keys
    """
    try:
        if channel.startswith("#"):
            channel = channel[1:]

        response = client.conversations_list(types="public_channel,private_channel")
        channel_id = None
        for ch in response["channels"]:
            if ch["name"] == channel:
                channel_id = ch["id"]
                break

        if not channel_id:
            logger.error(f"Channel {channel} not found")
            return []

        members_response = client.conversations_members(channel=channel_id)
        member_ids = members_response["members"]

        members = []
        for member_id in member_ids:
            user_info = client.users_info(user=member_id)
            user = user_info["user"]
            username = user.get("name", "")
            display_name = user.get("profile", {}).get("display_name", "")
            real_name = user.get("real_name", "")

            # Skip bots, deleted users, and excluded usernames
            if (
                not user.get("is_bot", False)
                and not user.get("deleted", False)
                and username.lower()
                not in [name.lower() for name in EXCLUDED_USERNAMES]
                and display_name.lower()
                not in [name.lower() for name in EXCLUDED_USERNAMES]
                and real_name.lower()
                not in [name.lower() for name in EXCLUDED_USERNAMES]
            ):
                members.append(
                    {
                        "id": user["id"],
                        "name": user.get("real_name", user.get("name", "Unknown")),
                    }
                )
            else:
                logger.info(f"Excluded user from pairing: {username}")

        logger.info(f"Found {len(members)} members in channel {channel}")
        return members

    except SlackApiError as e:
        logger.error(f"Error fetching channel members: {e.response['error']}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching channel members: {str(e)}")
        raise


def create_pairs(
    members: list[dict], blocked_pairs: Optional[set[tuple[str, str]]] = None
) -> list[list[dict]]:
    """
    Create random pairs from a list of members, avoiding blocked pairs.

    Uses a greedy matching algorithm:
    1. Build list of all allowed pairs (not in blocked set)
    2. Shuffle and greedily select pairs

    If there's an odd number of members, one random pair becomes a trio.

    Args:
        members: List of member dicts with 'id' and 'name' keys
        blocked_pairs: Set of (user_id_1, user_id_2) tuples to avoid

    Returns:
        List of pairs/trios (each is a list of member dicts)
    """
    if blocked_pairs is None:
        blocked_pairs = set()

    # Build member lookup by ID
    member_by_id = {m["id"]: m for m in members}
    member_ids = list(member_by_id.keys())

    # Build list of all allowed pairs
    allowed_pairs = []
    for i, id1 in enumerate(member_ids):
        for id2 in member_ids[i + 1 :]:
            pair_key = tuple(sorted([id1, id2]))
            if pair_key not in blocked_pairs:
                allowed_pairs.append((id1, id2))

    logger.info(
        f"Total possible pairs: {len(member_ids) * (len(member_ids) - 1) // 2}, "
        f"allowed (not blocked): {len(allowed_pairs)}"
    )

    # Shuffle allowed pairs for randomness
    random.shuffle(allowed_pairs)

    # Greedy matching: pick pairs, mark users as taken
    taken: set[str] = set()
    pairs: list[list[dict]] = []

    for id1, id2 in allowed_pairs:
        if id1 not in taken and id2 not in taken:
            pairs.append([member_by_id[id1], member_by_id[id2]])
            taken.add(id1)
            taken.add(id2)

    # Handle unpaired members (if any couldn't be matched due to blocking)
    unpaired = [member_by_id[mid] for mid in member_ids if mid not in taken]

    if len(unpaired) == 1 and len(pairs) > 0:
        # Odd member - add to a random pair as trio
        random_pair_index = random.randint(0, len(pairs) - 1)
        pairs[random_pair_index].append(unpaired[0])
        logger.info(
            f"Added odd member {unpaired[0]['name']} to pair {random_pair_index + 1} (now a trio)"
        )
    elif len(unpaired) > 1:
        # Multiple unpaired - pair them together (they were blocked with everyone else)
        logger.warning(
            f"{len(unpaired)} members couldn't be paired with non-blocked partners, "
            f"pairing them together: {[m['name'] for m in unpaired]}"
        )
        for i in range(0, len(unpaired) - 1, 2):
            pairs.append([unpaired[i], unpaired[i + 1]])
        if len(unpaired) % 2 == 1 and len(pairs) > 0:
            pairs[-1].append(unpaired[-1])

    return pairs


def create_pairing_message(
    pairs: list[list[dict]], topics_text: str = "", use_names: bool = False
) -> str:
    """
    Create a formatted Slack message for the pairings.

    Args:
        pairs: List of pairs/trios from create_pairs()
        topics_text: Optional conversation topics text to include
        use_names: If True, show names instead of Slack mention IDs (for preview)

    Returns:
        Formatted message string
    """
    message_parts = [
        "☕ *Happy Tuesday, Coffee Lovers!* ☕\n",
        "It's time for our weekly Random Coffee pairings! 🎉\n\n",
        "Here are this week's wonderful pairings:\n\n",
    ]

    def fmt(member: dict) -> str:
        return member["name"] if use_names else f"<@{member['id']}>"

    for i, group in enumerate(pairs, 1):
        if len(group) == 2:
            message_parts.append(f"{i}. {fmt(group[0])} & {fmt(group[1])} ☕\n")
        elif len(group) == 3:
            message_parts.append(
                f"{i}. {fmt(group[0])}, {fmt(group[1])} & {fmt(group[2])} ☕ (trio!)\n"
            )
        else:
            message_parts.append(
                f"{i}. {fmt(group[0])} - You're flying solo this week! 💙\n"
            )

    if topics_text:
        message_parts.append(topics_text)

    message_parts.extend(
        [
            "\n✨ *Here's the idea:* ✨\n",
            "Tomorrow (Wednesday) would be a lovely day for a coffee chat! "
            "It's totally optional and there's no pressure at all. 💛\n\n",
            "📅 Feel free to schedule a quick 15-30 minute call whenever works best for both of you.\n",
            "💬 Chat about anything - hobbies, weekend plans, fun projects, or just say hi!\n",
            "🤝 If this week doesn't work out, no worries! There's always next Tuesday.\n\n",
            "Have a wonderful week, everyone! 🌟",
        ]
    )

    return "".join(message_parts)


def format_pairs_preview(pairs: list[list[dict]]) -> str:
    """
    Create a human-readable preview of pairings (for testing).

    Args:
        pairs: List of pairs/trios from create_pairs()

    Returns:
        Formatted preview string
    """
    lines = ["Pairing Preview:", "=" * 40]
    for i, group in enumerate(pairs, 1):
        names = [m["name"] for m in group]
        group_type = "trio" if len(group) == 3 else "pair"
        lines.append(f"{i}. {' & '.join(names)} ({group_type})")
    lines.append("=" * 40)
    lines.append(f"Total groups: {len(pairs)}")
    return "\n".join(lines)


def run_pairing_test(
    members: Optional[list[dict]] = None,
    slack_token: Optional[str] = None,
    channel: Optional[str] = None,
    blocked_pairs: Optional[set[tuple[str, str]]] = None,
    history_days: int = 40,
) -> tuple[list[list[dict]], str]:
    """
    Run the pairing algorithm for testing purposes.

    Either provide members directly, or provide slack_token and channel
    to fetch members from Slack.

    Args:
        members: Optional list of member dicts to use directly
        slack_token: Optional Slack token for fetching members
        channel: Optional channel name for fetching members
        blocked_pairs: Optional set of blocked pairs (if not provided, fetched from channel)
        history_days: Number of days to look back for pairing history

    Returns:
        Tuple of (pairs, preview_message)
    """
    client = None
    if members is None:
        if slack_token and channel:
            client = WebClient(token=slack_token)
            members = get_channel_members(client, channel)
        else:
            raise ValueError(
                "Either provide 'members' list or both 'slack_token' and 'channel'"
            )

    if len(members) < 2:
        raise ValueError(f"Not enough members to create pairs (found {len(members)})")

    # Fetch blocked pairs from history if not provided
    if blocked_pairs is None and client and channel:
        blocked_pairs = fetch_recent_pairs(client, channel, days=history_days)

    pairs = create_pairs(members, blocked_pairs)
    preview = format_pairs_preview(pairs)

    return pairs, preview


if __name__ == "__main__":
    import argparse
    import os
    from dotenv import load_dotenv

    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Test the Random Coffee pairing algorithm"
    )
    parser.add_argument(
        "--token",
        "-t",
        help="Slack API token (or set SLACK_BOT_TOKEN env var)",
    )
    parser.add_argument(
        "--channel",
        "-c",
        help="Slack channel to fetch members from",
    )
    parser.add_argument(
        "--mock",
        "-m",
        type=int,
        help="Use mock data with N members instead of fetching from Slack",
    )
    parser.add_argument(
        "--show-message",
        action="store_true",
        help="Show the full Slack message that would be posted",
        default=True,
    )
    args = parser.parse_args()

    if args.mock:
        # Generate mock members for testing
        members = [
            {"id": f"U{i:04d}", "name": f"Test User {i}"}
            for i in range(1, args.mock + 1)
        ]
        print(f"Using {len(members)} mock members\n")
    else:
        token = args.token or os.environ.get("SLACK_BOT_TOKEN")
        if not token:
            print(
                "Error: No Slack token. Use --token, set SLACK_BOT_TOKEN, or use --mock"
            )
            exit(1)
        if not args.channel:
            print("Error: No channel specified. Use --channel or use --mock")
            exit(1)
        members = None

    try:
        if members:
            pairs, preview = run_pairing_test(members=members)
        else:
            pairs, preview = run_pairing_test(slack_token=token, channel=args.channel)

        print(preview)

        if args.show_message:
            print("\n" + "=" * 40)
            print("Full Slack Message (with names for preview):")
            print("=" * 40)
            message = create_pairing_message(pairs, use_names=True)
            print(message)

    except Exception as e:
        print(f"Error: {e}")
        exit(1)
