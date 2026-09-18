from telethon.sync import TelegramClient

api_id = '39111225'
api_hash = 'Y8d6b777cfce01184cd4a0cb7b227030a'
group_username = 'https://t.me/+MW5TAtGSogg2Nzgy' # e.g., '@mygroup'

# This will ask for your phone number and login code the first time you run it
with TelegramClient('my_account', api_id, api_hash) as client:
    print("Extracting members...")
    members = client.get_participants(group_username)
    
    # This formats the output perfectly for our bot script
    ids = {user.id for user in members}
    print(f"known_members = {ids}")
