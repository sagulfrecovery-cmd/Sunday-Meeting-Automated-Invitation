import streamlit as st
import asyncio
import os
import requests
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetPollVotesRequest

st.set_page_config(page_title="Telegram Purge Bot")
st.title("Group Purge Control")

# SECURE CREDENTIALS
API_ID = int(os.environ.get("TELEGRAM_API_ID", 39111225))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "8d6b777cfce01184cd4a0cb7b227030a")
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
SESSION_STRING = os.environ.get("TELEGRAM_SESSION_STRING")

group_id = st.text_input("Target Group ID (e.g., -1002844744618)")

# ==========================================
# SECTION 1: Deploy Poll
# ==========================================
st.subheader("Day 1: Deploy Poll")
if st.button("Send Attendance Poll"):
    if group_id:
        try:
            chat_target = int(group_id)
        except ValueError:
            chat_target = group_id 

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPoll"
        payload = {
            "chat_id": chat_target,
            "question": "يرجى الاجابة على الاستبيان، وسيتم حذف الاعضاء غير المستجيبين، والبقاء في مجموعة زمالة الخليج فقط لأعضاء الزمالة للعلم.",
            "options": [
                "1) أنا عضو في الزمالة وأرغب بحضور اجتماع الأحد للخدمة فيه",
                "2) أنا عضو في الزمالة لكني في المجموعة بهدف الحصول على المساعدة والتواصل مع الأعضاء"
            ],
            "is_anonymous": False 
        }
        res = requests.post(url, json=payload).json()
        
        if res.get("ok"):
            msg_id = res['result']['message_id']
            st.success(f"Poll sent successfully! **Save this Message ID for Day 4: {msg_id}**")
        else:
            st.error(f"Failed to send poll: {res}")
    else:
        st.warning("Please enter a group ID.")

# ==========================================
# SECTION 2: Execute Purge
# ==========================================
st.subheader("Day 4: Execute Purge")
poll_message_id = st.text_input("Enter the Message ID from Day 1:")

async def execute_purge(group_input, msg_id):
    try:
        peer = int(group_input)
    except ValueError:
        peer = group_input
        
    # AUTH UPDATE: Logs in via StringSession to bypass bot API restrictions
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()
    
    group_entity = await client.get_entity(peer)
    
    # SAFETY UPDATE: Verifies the message is actually a poll
    message = await client.get_messages(group_entity, ids=int(msg_id))
    if getattr(message.media, 'poll', None) is None:
        st.error("Error: The provided Message ID is not a poll.")
        await client.disconnect()
        return 0, 0
        
    poll = message.media.poll
    voters = set()
    
    # DYNAMIC FETCH: Pulls the exact byte options directly from the poll
    for answer in poll.answers:
        try:
            vote_req = await client(GetPollVotesRequest(
                peer=group_entity,
                id=int(msg_id),
                option=answer.option,
                offset='',
                limit=100
            ))
            for user in vote_req.users:
                voters.add(user.id)
        except Exception as e:
            st.error(f"Failed to read votes: {e}")
            await client.disconnect()
            return 0, 0
            
    # CRITICAL SAFEGUARD: Aborts completely if no voters are found
    if len(voters) == 0:
        st.warning("Safeguard Triggered: 0 voters detected. The purge has been aborted to prevent an accidental mass kick.")
        await client.disconnect()
        return 0, 0
        
    all_members = await client.get_participants(group_entity)
    all_human_ids = {user.id for user in all_members if not user.bot}
    
    to_kick = all_human_ids - voters
    kicked_count = 0
    
    for uid in to_kick:
        try:
            await client.kick_participant(group_entity, uid)
            kicked_count += 1
        except Exception as e:
            print(f"Failed to kick {uid}: {e}") 
            
    await client.send_message(group_entity, f"تم الانتهاء من الفرز. تم حذف {kicked_count} من الأعضاء غير المتفاعلين.")
    await client.disconnect()
    
    return kicked_count, len(voters)

if st.button("Calculate & Purge Non-Voters"):
    if not group_id or not poll_message_id:
        st.warning("Please ensure BOTH the Group ID and Message ID are filled out.")
    elif not SESSION_STRING:
        st.error("Missing TELEGRAM_SESSION_STRING in Streamlit Secrets.")
    else:
        with st.spinner("Scraping poll results and purging inactive users..."):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                kicked, voted = loop.run_until_complete(execute_purge(group_id, poll_message_id))
                if voted > 0:
                    st.success(f"Success! {voted} users voted and were saved. {kicked} ghost users were removed.")
            except Exception as e:
                st.error(f"An error occurred: {e}")
