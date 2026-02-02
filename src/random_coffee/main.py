import os
import time
import schedule
import logging
import argparse
import json

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from random_coffee.topics_generator import (
    generate_conversation_topics,
    format_topics_for_slack,
)
from random_coffee.pairing import (
    get_channel_members,
    create_pairs,
    create_pairing_message,
    fetch_recent_pairs,
)

# Load environment variables from .env file
load_dotenv()


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


def pair_and_notify(client, channel, openai_api_key=None):
    try:
        logger.info(f"Starting pairing process for channel {channel}")

        members = get_channel_members(client, channel)

        if len(members) < 2:
            warning_msg = f"Not enough members in {channel} to create pairs (found {len(members)})"
            logger.warning(warning_msg)
            send_error_to_admin(client, warning_msg, "Pairing Process Warning")
            return

        # Fetch recent pairings to avoid repeating them
        blocked_pairs = fetch_recent_pairs(client, channel, days=30)

        pairs = create_pairs(members, blocked_pairs)
        logger.info(f"Created {len(pairs)} pairs")

        # Generate conversation topics if OpenAI API key is available
        topics_text = ""
        if openai_api_key:
            try:
                logger.info("Generating conversation topics...")
                topics = generate_conversation_topics(openai_api_key)
                topics_text = format_topics_for_slack(topics)
                logger.info(f"Generated {len(topics)} conversation topics")
            except Exception as e:
                logger.error(f"Failed to generate conversation topics: {e}")
                # Continue without topics - don't fail the whole pairing process

        message = create_pairing_message(pairs, topics_text)

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

    # Load OpenAI API key from environment or config
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if config and "openai_api_key" in config:
        openai_api_key = config["openai_api_key"]

    if not openai_api_key:
        logger.warning(
            "No OpenAI API key provided. Conversation topics will not be generated. "
            "Set OPENAI_API_KEY environment variable or include 'openai_api_key' in config."
        )

    channel = args.channel
    pairing_time = args.time

    try:
        client = WebClient(token=token)

        logger.info(f"RandomCoffee bot started")
        logger.info(
            f"Pairings scheduled every Tuesday at {pairing_time} UTC in {channel}"
        )
        if openai_api_key:
            logger.info(
                "OpenAI API key configured - conversation topics will be generated"
            )

        schedule.every().tuesday.at(pairing_time).do(
            pair_and_notify,
            client=client,
            channel=channel,
            openai_api_key=openai_api_key,
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
