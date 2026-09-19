import streamlit as st
import asyncio
import os
import requests
from telethon import TelegramClient
from telethon.sessions import MemorySession  # New import added
from telethon.tl.functions.messages import GetPollVotesRequest

st.set_page_config(page_title="Telegram Purge Bot")
st.title("Group Purge Control")

# Securely fetch credentials from Streamlit Secrets or Environment Variables
API_ID = int(os.environ.get("TELEGRAM_API_ID", 39111225))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "8d6b777cfce01184cd4a0cb7b227030a")
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")

group_id = st.text_input("Target Group Username (e.g., @mygroup)")

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
        st.warning("Please enter a group username.")

# ==========================================
# SECTION 2: Execute Purge
# ==========================================
st.subheader("Day 4: Execute Purge")
poll_message_id = st.text_input("Enter the Message ID from Day 1:")

async def execute_purge(group, msg_id):
    # Patched: Bypasses Streamlit file system restrictions using MemorySession
    client = TelegramClient(MemorySession(), API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    
    voters = set()
    
    for option_byte in [b'0', b'1']:
        try:
            vote_req = await client(GetPollVotesRequest(
                peer=group,
                id=int(msg_id),
                option=option_byte,
                offset='',
                limit=100
            ))
            for vote in vote_req.votes:
                voters.add(vote.peer.user_id)
        except Exception:
            pass 
            
    all_members = await client.get_participants(group)
    all_human_ids = {user.id for user in all_members if not user.bot}
    
    to_kick = all_human_ids - voters
    kicked_count = 0
    
    for uid in to_kick:
        try:
            await client.kick_participant(group, uid)
            kicked_count += 1
        except Exception:
            pass 
            
    await client.send_message(group, f"تم الانتهاء من الفرز. تم حذف {kicked_count} من الأعضاء غير المتفاعلين.")
    await client.disconnect()
    
    return kicked_count, len(voters)

if st.button("Calculate & Purge Non-Voters"):
    if group_id and poll_message_id:
        with st.spinner("Scraping poll results and purging inactive users..."):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            kicked, voted = loop.run_until_complete(execute_purge(group_id, poll_message_id))
            st.success(f"Success! {voted} users voted. {kicked} ghost users were removed.")
