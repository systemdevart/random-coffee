import os
import time
import schedule
import logging
import argparse
import json
import random

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("random_coffee.log"), logging.StreamHandler()],
)
logger = logging.getLogger("RandomCoffeeBot")

DEFAULT_SLACK_CHANNEL = "#general"
DEFAULT_CONFIG_PATH = "/etc/random_coffee/config.json"
DEFAULT_PAIRING_TIME = "16:00"  # Default time for Tuesday pairings (UTC)
DEFAULT_ERROR_RECIPIENT = "@dchebakov"


def load_config(config_path):
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        logger.debug(f"Loaded configuration from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Error loading config from {config_path}: {str(e)}")
        return None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Monitor GPU memory usage and send alerts to Slack"
    )
    parser.add_argument("--token", "-t", help="Slack API token")
    parser.add_argument(
        "--name",
        "-n",
        help="Machine name for alerts",
    )
    parser.add_argument(
        "--channel", "-c", help="Slack channel", default=DEFAULT_SLACK_CHANNEL
    )
    parser.add_argument(
        "--config",
        help="Path to JSON configuration file",
        default=DEFAULT_CONFIG_PATH,
    )
    parser.add_argument(
        "--time",
        help="Daily pairing time (HH:MM format, 24-hour)",
        default=DEFAULT_PAIRING_TIME,
    )
    return parser.parse_args()


def send_error_to_admin(client, error_msg, context=""):
    try:
        message = (
            f"🚨 *Random Coffee Bot Error* 🚨\n"
            f"{context}\n"
            f"```{error_msg}```\n"
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}"
        )

        client.chat_postMessage(channel=DEFAULT_ERROR_RECIPIENT, text=message)
        logger.info(f"Error notification sent to {DEFAULT_ERROR_RECIPIENT}")

    except Exception as e:
        logger.error(f"Failed to send error notification to admin: {str(e)}")


def get_channel_members(client, channel):
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

            if (
                not user.get("is_bot", False)
                and not user.get("deleted", False)
                and username.lower() != "admin"
            ):
                members.append(
                    {
                        "id": user["id"],
                        "name": user.get("real_name", user.get("name", "Unknown")),
                    }
                )

        logger.info(f"Found {len(members)} members in channel {channel}")
        return members

    except SlackApiError as e:
        error_msg = f"Error fetching channel members: {e.response['error']}"
        logger.error(error_msg)
        send_error_to_admin(
            client, error_msg, f"Failed to fetch members from {channel}"
        )
        return []
    except Exception as e:
        error_msg = f"Unexpected error fetching channel members: {str(e)}"
        logger.error(error_msg)
        send_error_to_admin(
            client, error_msg, f"Failed to fetch members from {channel}"
        )
        return []


def create_pairs(members):
    shuffled = members.copy()
    random.shuffle(shuffled)

    pairs = []
    for i in range(0, len(shuffled) - 1, 2):
        pairs.append([shuffled[i], shuffled[i + 1]])

    if len(shuffled) % 2 == 1 and len(pairs) > 0:
        odd_member = shuffled[-1]
        random_pair_index = random.randint(0, len(pairs) - 1)
        pairs[random_pair_index].append(odd_member)
        logger.info(f"Added odd member to pair {random_pair_index + 1} (now a trio)")

    return pairs


def create_pairing_message(pairs):
    message_parts = [
        "☕ *Happy Tuesday, Coffee Lovers!* ☕\n",
        "It's time for our weekly Random Coffee pairings! 🎉\n\n",
        "Here are this week's wonderful pairings:\n\n",
    ]

    for i, group in enumerate(pairs, 1):
        if len(group) == 2:
            message_parts.append(f"{i}. <@{group[0]['id']}> & <@{group[1]['id']}> ☕\n")
        elif len(group) == 3:
            message_parts.append(
                f"{i}. <@{group[0]['id']}>, <@{group[1]['id']}> & <@{group[2]['id']}> ☕ (trio!)\n"
            )
        else:
            message_parts.append(
                f"{i}. <@{group[0]['id']}> - You're flying solo this week! 💙\n"
            )

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


def pair_and_notify(client, channel):
    try:
        logger.info(f"Starting pairing process for channel {channel}")

        members = get_channel_members(client, channel)

        if len(members) < 2:
            warning_msg = f"Not enough members in {channel} to create pairs (found {len(members)})"
            logger.warning(warning_msg)
            send_error_to_admin(client, warning_msg, "Pairing Process Warning")
            return

        pairs = create_pairs(members)
        logger.info(f"Created {len(pairs)} pairs")

        message = create_pairing_message(pairs)

        client.chat_postMessage(channel=channel, text=message)
        logger.info(f"Pairing notification sent to {channel}")

    except SlackApiError as e:
        error_msg = f"Slack API error in pairing process: {e.response['error']}"
        logger.error(error_msg)
        send_error_to_admin(
            client, error_msg, f"Failed to complete pairing for {channel}"
        )
    except Exception as e:
        error_msg = f"Unexpected error in pairing process: {str(e)}"
        logger.error(error_msg)
        send_error_to_admin(
            client, error_msg, f"Failed to complete pairing for {channel}"
        )


def main():
    args = parse_args()

    token = args.token or os.environ.get("SLACK_BOT_TOKEN")
    config = load_config(args.config)
    if config and "slack_token" in config:
        token = config["slack_token"]

    if not token:
        logger.error(
            "No Slack token provided. Use --token, set SLACK_BOT_TOKEN environment variable, or include in config."
        )
        return

    channel = args.channel
    pairing_time = args.time

    try:
        client = WebClient(token=token)

        logger.info(f"RandomCoffee bot started")
        logger.info(
            f"Pairings scheduled every Tuesday at {pairing_time} UTC in {channel}"
        )

        schedule.every().tuesday.at(pairing_time).do(
            pair_and_notify,
            client=client,
            channel=channel,
        )

        while True:
            schedule.run_pending()
            time.sleep(30)

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        error_msg = f"Fatal error in main loop: {str(e)}"
        logger.error(error_msg)
        try:
            client = WebClient(token=token)
            send_error_to_admin(client, error_msg, "Bot Crashed")
        except:
            pass
        raise


if __name__ == "__main__":
    main()