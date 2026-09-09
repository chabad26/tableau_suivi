import os

import discord
from dotenv import load_dotenv

from app.database import create_discord_proposal
from app.discord_parser import parse_proposal


load_dotenv()


TOKEN = os.getenv(
    "DISCORD_BOT_TOKEN"
)

CHANNEL_ID_RAW = os.getenv(
    "DISCORD_CHANNEL_ID"
)


if not CHANNEL_ID_RAW:
    raise RuntimeError(
        "DISCORD_CHANNEL_ID absent du fichier .env"
    )


CHANNEL_ID = int(
    CHANNEL_ID_RAW
)


intents = discord.Intents.default()

intents.message_content = True


client = discord.Client(
    intents=intents
)


@client.event
async def on_ready() -> None:
    if client.user is None:
        return

    print(
        f"🤖 Connecté en tant que "
        f"{client.user}"
    )

    print(
        f"📡 Salon surveillé : "
        f"{CHANNEL_ID}"
    )


@client.event
async def on_message(
    message: discord.Message,
) -> None:
    if message.author.bot:
        return

    if message.channel.id != CHANNEL_ID:
        return

    content = message.content.strip()

    if not content:
        return

    proposal = parse_proposal(
        content
    )

    note_parts = [
        f"Import Discord",
        f"Auteur : {message.author}",
    ]

    if proposal.url:
        note_parts.append(
            f"Lien : {proposal.url}"
        )

    note = " | ".join(
        note_parts
    )

    application_id = create_discord_proposal(
        company=proposal.company,
        job_title=proposal.job_title,
        note=note,
    )

    await message.reply(
        (
            "✅ Proposition ajoutée au Job Tracker\n"
            f"**#{application_id}** "
            f"{proposal.company} "
            f"• {proposal.job_title}"
        ),
        mention_author=False,
    )


def run_bot() -> None:
    token = TOKEN
    if not token:
        raise RuntimeError(
            "DISCORD_BOT_TOKEN absent du fichier .env"
        )

    client.run(
        token
    )
