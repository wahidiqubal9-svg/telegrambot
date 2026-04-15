import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import BadRequest

import database

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_CHANNEL_ID = os.getenv("PUBLIC_CHANNEL_ID", "@neetpgfmgemcqhourly")
PUBLIC_CHANNEL_LINK = os.getenv("PUBLIC_CHANNEL_LINK", "https://t.me/neetpgfmgemcqhourly")
PUBLIC_GROUP_ID = os.getenv("PUBLIC_GROUP_ID", "@neetpgpyqhourly")
PUBLIC_GROUP_LINK = os.getenv("PUBLIC_GROUP_LINK", "https://t.me/neetpgpyqhourly")
PRIVATE_CHANNEL_ID = os.getenv("PRIVATE_CHANNEL_ID")
REQUIRED_REFERRALS = int(os.getenv("REQUIRED_REFERRALS", 10))

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user

    # Check if there is a referral argument (e.g. /start 123456789)
    args = context.args
    referred_by = None
    if args and args[0].isdigit():
        referrer_id = int(args[0])
        # Make sure they aren't referring themselves
        if referrer_id != user.id:
            referred_by = referrer_id

    # Add user to database
    database.add_user(user.id, referred_by)

    await send_main_menu(update.effective_chat.id, context)

async def send_main_menu(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the main menu with inline buttons."""
    keyboard = [
        [
            InlineKeyboardButton("📢 Join Channel", url=PUBLIC_CHANNEL_LINK),
            InlineKeyboardButton("💬 Join Group", url=PUBLIC_GROUP_LINK)
        ],
        [InlineKeyboardButton("✅ Verify Subscription", callback_data="verify")],
        [InlineKeyboardButton("👤 My Profile / Referrals", callback_data="profile")],
        [InlineKeyboardButton("🎁 Get Private Link", callback_data="get_link")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "Welcome! To gain access to our exclusive Private Channel, you need to:\n\n"
            "1. Subscribe to our Public Channel\n"
            "2. Join our Public Group\n"
            f"3. Invite {REQUIRED_REFERRALS} friends using your referral link who also complete steps 1 & 2.\n\n"
            "Use the buttons below to navigate."
        ),
        reply_markup=reply_markup,
    )

async def check_subscription(bot, user_id, chat_id) -> bool:
    """Check if a user is a member of a specific chat."""
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        # Status can be 'member', 'creator', 'administrator', or 'restricted' (if they can still read)
        return member.status in ['member', 'creator', 'administrator', 'restricted']
    except BadRequest as e:
        logger.error(f"Error checking membership for user {user_id} in {chat_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data == "verify":
        # Check subscriptions
        in_channel = await check_subscription(context.bot, user_id, PUBLIC_CHANNEL_ID)
        in_group = await check_subscription(context.bot, user_id, PUBLIC_GROUP_ID)

        if in_channel and in_group:
            # Mark user as verified in DB
            database.mark_verified(user_id)
            await query.edit_message_text(
                text="✅ Subscription verified! You are now eligible to refer others. Click /start to return to the main menu."
            )
        else:
            keyboard = [
                [
                    InlineKeyboardButton("📢 Join Channel", url=PUBLIC_CHANNEL_LINK),
                    InlineKeyboardButton("💬 Join Group", url=PUBLIC_GROUP_LINK)
                ],
                [InlineKeyboardButton("✅ Try Verifying Again", callback_data="verify")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="start_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                text=(
                    "❌ Verification failed.\n\n"
                    "Please make sure you have joined both our Public Channel and Public Group using the buttons below.\n\n"
                    "Then try verifying again."
                ),
                reply_markup=reply_markup
            )

    elif query.data == "start_menu":
        # Delete the previous callback message and send the main menu
        await query.message.delete()
        await send_main_menu(user_id, context)

    elif query.data == "profile":
        # Get user stats
        bot_username = context.bot.username
        referral_link = f"https://t.me/{bot_username}?start={user_id}"

        user_data = database.get_user(user_id)
        if not user_data:
            database.add_user(user_id)
            user_data = database.get_user(user_id)

        is_verified_str = "✅ Yes" if user_data['is_verified'] else "❌ No (Please click 'Verify Subscription')"
        successful_referrals = database.get_successful_referrals_count(user_id)

        await query.edit_message_text(
            text=(
                "👤 <b>Your Profile</b>\n\n"
                f"Status: Subscribed? {is_verified_str}\n"
                f"Successful Referrals: {successful_referrals} / {REQUIRED_REFERRALS}\n\n"
                f"🔗 <b>Your Referral Link:</b>\n{referral_link}\n\n"
                "(A referral is only counted as 'Successful' when the person you invite subscribes to both our public channel and group.)\n\n"
                "Click /start to return to the main menu."
            ),
            parse_mode='HTML'
        )

    elif query.data == "get_link":
        user_data = database.get_user(user_id)
        if user_data and user_data.get('has_claimed_reward'):
            await query.edit_message_text(
                text=(
                    "❌ You have already claimed your reward and received a link.\n\n"
                    "If you lost your link or it expired, please contact the administrators.\n\n"
                    "Click /start to return to the main menu."
                )
            )
            return

        successful_referrals = database.get_successful_referrals_count(user_id)

        if successful_referrals >= REQUIRED_REFERRALS:
            try:
                # Generate a single-use invite link for the private channel
                invite_link = await context.bot.create_chat_invite_link(
                    chat_id=PRIVATE_CHANNEL_ID,
                    member_limit=1,
                    name=f"Invite for {user_id}"
                )

                # Mark reward as claimed in the database
                database.mark_reward_claimed(user_id)

                await query.edit_message_text(
                    text=(
                        "🎉 Congratulations! You have reached the required number of referrals.\n\n"
                        f"Here is your exclusive link to the Private Channel: {invite_link.invite_link}\n\n"
                        "⚠️ Note: This link can only be used once. Do not share it with anyone else!"
                    )
                )
            except Exception as e:
                logger.error(f"Error creating invite link: {e}")
                await query.edit_message_text(
                    text=(
                        "An error occurred while generating your invite link. "
                        "Please make sure the bot is an Administrator in the Private Channel with permission to 'Invite Users'."
                        "\n\nClick /start to return to the main menu."
                    )
                )
        else:
            await query.edit_message_text(
                text=(
                    f"You need {REQUIRED_REFERRALS} successful referrals to get the private link.\n"
                    f"You currently have {successful_referrals}.\n\n"
                    "Share your referral link from 'My Profile' to invite more people!\n\n"
                    "Click /start to return to the main menu."
                )
            )

def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN or BOT_TOKEN == "123456789:YOUR_BOT_TOKEN_HERE":
        logger.error("Please set the BOT_TOKEN in your .env file!")
        return

    # Initialize database
    database.init_db()

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
