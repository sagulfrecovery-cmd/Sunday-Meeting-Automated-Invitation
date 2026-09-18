from telegram import Update
from telegram.ext import Application, CommandHandler, PollAnswerHandler, ContextTypes

# Replace these placeholder IDs with the actual 50 User IDs of your group members
KNOWN_MEMBERS = {123456789, 987654321, 111222333} 

voted_users = set()
active_poll_id = None

async def create_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates the attendance poll. Admin sends /vote to trigger this."""
    global active_poll_id
    
    message = await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question="Attendance Check: Are you still active in this group?",
        options=["Yes, I am active"],
        is_anonymous=False, # CRITICAL: Allows the bot to see exactly who voted
        allows_multiple_answers=False
    )
    
    active_poll_id = message.poll.id
    voted_users.clear() # Resets the memory from any previous polls
    
    await update.message.reply_text("Tracking started! Anyone who does not vote will be removed.")

async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Silently logs the User ID whenever someone selects a poll option."""
    answer = update.poll_answer
    
    if answer.poll_id == active_poll_id:
        voted_users.add(answer.user.id)

async def purge_non_voters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Calculates who didn't vote and kicks them."""
    if not active_poll_id:
        await update.message.reply_text("No active poll to purge from.")
        return

    # Subtracts the people who voted from your master list of 50 members
    to_kick = KNOWN_MEMBERS - voted_users
    chat_id = update.effective_chat.id
    
    if not to_kick:
        await update.message.reply_text("No inactive members found. Everyone voted.")
        return

    removed_count = 0
    for user_id in to_kick:
        try:
            # Ban + Unban kicks the user without permanently blacklisting them
            await context.bot.ban_chat_member(chat_id, user_id)
            await context.bot.unban_chat_member(chat_id, user_id)
            removed_count += 1
        except Exception as e:
            print(f"Failed to kick user {user_id}: {e}")

    await update.message.reply_text(f"Purge complete. Removed {removed_count} inactive members.")

if __name__ == "__main__":
    # Insert your actual BotFather token here
    app = Application.builder().token("YOUR_BOT_TOKEN").build()

    # Handlers
    app.add_handler(CommandHandler("vote", create_vote))
    app.add_handler(CommandHandler("purge", purge_non_voters))
    
    # This specific handler is required to listen to poll interactions
    app.add_handler(PollAnswerHandler(handle_poll_answer))

    # ALL_TYPES is required to ensure poll answers are routed correctly
    app.run_polling(allowed_updates=Update.ALL_TYPES)
