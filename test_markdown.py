from telegram.constants import ParseMode

try:
    msg = (
        "👤 <b>Your Profile</b>\n\n"
        f"Status: Subscribed? ✅ Yes\n"
        f"Successful Referrals: 0 / 10\n\n"
        f"🔗 <b>Your Referral Link:</b>\nhttps://t.me/bot?start=123\n\n"
        "(A referral is only counted as 'Successful' when the person you invite subscribes to both our public channel and group.)\n\n"
        "Click /start to return to the main menu."
    )
except Exception as e:
    print(e)
