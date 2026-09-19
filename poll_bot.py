import os
from telethon import TelegramClient, events, Button

# SECURED CREDENTIALS
# The script will pull from your server's environment variables to keep your public GitHub safe.
API_ID = int(os.environ.get("TELEGRAM_API_ID", 39111225)) # From image_a3b5aa.png
API_HASH = os.environ.get("TELEGRAM_API_HASH", "8d6b777cfce01184cd4a0cb7b227030a") # From image_a3b5aa.png
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Initialize the bot client using the Account_Removal app credentials
client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

active_users = set()
target_group_id = None

@client.on(events.NewMessage(pattern='/vote'))
async def start_attendance(event):
    """Generates an attendance button. Admin sends /vote to trigger this."""
    global target_group_id, active_users
    
    target_group_id = event.chat_id
    active_users.clear() # Reset memory for a new vote
    
    await event.respond(
        "Attendance Check: Click the button below if you are still active in this group.",
        buttons=Button.inline("Yes, I am active", data=b'active_click')
    )

@client.on(events.CallbackQuery(data=b'active_click'))
async def handle_click(event):
    """Silently logs the User ID when they click the button."""
    active_users.add(event.sender_id)
    # Shows a tiny popup message to the user confirming their click
    await event.answer("Your activity has been logged!", alert=True) 

@client.on(events.NewMessage(pattern='/purge'))
async def execute_purge(event):
    """Scrapes the live member list, subtracts the clickers, and kicks the rest."""
    if not target_group_id:
        await event.respond("Please run /vote first.")
        return

    await event.respond("Scraping current member list...")
    
    # The bot automatically fetches all members itself
    all_members = await client.get_participants(target_group_id)
    
    # Filter out other bots to ensure we only kick real humans
    all_member_ids = {user.id for user in all_members if not user.bot}
    
    # Calculate who didn't click
    to_kick = all_member_ids - active_users
    
    if not to_kick:
        await event.respond("No inactive members found. Everyone responded.")
        return
        
    removed_count = 0
    for user_id in to_kick:
        try:
            # Telethon's kick_participant removes the user from the group
            await client.kick_participant(target_group_id, user_id)
            removed_count += 1
        except Exception as e:
            print(f"Failed to kick {user_id}: {e}")

    await event.respond(f"Purge complete. Removed {removed_count} inactive members.")

if __name__ == '__main__':
    print("Hybrid Bot is online and listening...")
    client.run_until_disconnected()
