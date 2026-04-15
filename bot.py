import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest

import database

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
if ADMIN_ID:
    ADMIN_ID = int(ADMIN_ID)

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
    required_chats = database.get_all_required_chats()
    required_referrals = database.get_config("required_referrals", "10")

    keyboard = []
    # Add join buttons for each required chat
    for chat in required_chats:
        keyboard.append([InlineKeyboardButton(f"📢 Join {chat['chat_name']}", url=chat['chat_link'])])

    keyboard.extend([
        [InlineKeyboardButton("✅ Verify Subscription", callback_data="verify")],
        [InlineKeyboardButton("👤 My Profile / Referrals", callback_data="profile")],
        [InlineKeyboardButton("🎁 Get Private Link", callback_data="get_link")]
    ])
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "Welcome! To gain access to our exclusive Private Channel, you need to:\n\n"
    for i, chat in enumerate(required_chats, 1):
        text += f"{i}. Join our {chat['chat_name']}\n"

    text += f"{len(required_chats) + 1}. Invite {required_referrals} friends using your referral link who also complete the steps above.\n\n"
    text += "Use the buttons below to navigate."

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to open the admin panel."""
    if not ADMIN_ID or update.effective_user.id != ADMIN_ID:
        return
    context.user_data['admin_action'] = None  # Cancel any pending action
    await send_admin_menu(update.effective_chat.id, context)

async def send_admin_menu(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the admin panel menu."""
    priv_id = database.get_config('private_channel_id', 'Not Set')
    refs = database.get_config('required_referrals', '10')
    chats = database.get_all_required_chats()

    chats_text = "\n".join([f"- {c['chat_name']} ({c['chat_id']})" for c in chats]) if chats else "None"

    text = (
        "🛠 **Admin Panel**\n\n"
        f"**Private Channel ID:** {priv_id}\n"
        f"**Required Referrals:** {refs}\n\n"
        f"**Required Chats:**\n{chats_text}\n\n"
        "Choose an action below:"
    )

    keyboard = [
        [InlineKeyboardButton("✏️ Change Private Channel ID", callback_data="admin_change_priv")],
        [InlineKeyboardButton("🔢 Change Required Referrals", callback_data="admin_change_refs")],
        [InlineKeyboardButton("➕ Add Required Chat", callback_data="admin_add_chat")],
        [InlineKeyboardButton("🗑 Remove Required Chat", callback_data="admin_remove_chat")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text input from the admin for configuration."""
    user_id = update.effective_user.id
    if not ADMIN_ID or user_id != ADMIN_ID:
        return

    action = context.user_data.get('admin_action')
    if not action:
        return

    text = update.message.text

    if action == 'set_private_channel':
        database.set_config('private_channel_id', text)
        await update.message.reply_text(f"✅ Private Channel ID updated to: {text}")
        context.user_data['admin_action'] = None
        await send_admin_menu(update.message.chat_id, context)

    elif action == 'set_referrals':
        if not text.isdigit():
            await update.message.reply_text("❌ Please enter a valid number.")
            return
        database.set_config('required_referrals', text)
        await update.message.reply_text(f"✅ Required referrals updated to: {text}")
        context.user_data['admin_action'] = None
        await send_admin_menu(update.message.chat_id, context)

    elif action == 'add_chat_name':
        context.user_data['new_chat_name'] = text
        context.user_data['admin_action'] = 'add_chat_id'
        await update.message.reply_text("Please enter the Chat ID or Username (e.g. @mychannel or -10012345):")

    elif action == 'add_chat_id':
        context.user_data['new_chat_id'] = text
        context.user_data['admin_action'] = 'add_chat_link'
        await update.message.reply_text("Please enter the Join Link for this chat (e.g. https://t.me/mychannel):")

    elif action == 'add_chat_link':
        name = context.user_data.get('new_chat_name')
        chat_id = context.user_data.get('new_chat_id')
        link = text

        database.add_required_chat(name, chat_id, link)
        await update.message.reply_text(f"✅ Required chat '{name}' added successfully!")

        context.user_data['admin_action'] = None
        context.user_data['new_chat_name'] = None
        context.user_data['new_chat_id'] = None
        await send_admin_menu(update.message.chat_id, context)

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

    # Handle admin callbacks
    if query.data.startswith("admin_"):
        if ADMIN_ID and user_id != ADMIN_ID:
            await query.answer("Not authorized", show_alert=True)
            return

        if query.data == "admin_change_priv":
            context.user_data['admin_action'] = 'set_private_channel'
            await query.message.reply_text("Please send the new Private Channel ID:")
            await query.answer()

        elif query.data == "admin_change_refs":
            context.user_data['admin_action'] = 'set_referrals'
            await query.message.reply_text("Please send the new Required Referrals number:")
            await query.answer()

        elif query.data == "admin_add_chat":
            context.user_data['admin_action'] = 'add_chat_name'
            await query.message.reply_text("Please send a Name for the new required chat (e.g. My Public Group):")
            await query.answer()

        elif query.data == "admin_remove_chat":
            chats = database.get_all_required_chats()
            if not chats:
                await query.answer("No chats to remove.", show_alert=True)
                return

            keyboard = []
            for c in chats:
                keyboard.append([InlineKeyboardButton(f"❌ {c['chat_name']}", callback_data=f"admin_del_chat_{c['id']}")])
            keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="admin_menu")])

            await query.edit_message_text("Select a chat to remove:", reply_markup=InlineKeyboardMarkup(keyboard))

        elif query.data.startswith("admin_del_chat_"):
            chat_id_to_del = int(query.data.split("_")[-1])
            database.remove_required_chat(chat_id_to_del)
            await query.answer("Chat removed!")
            await send_admin_menu(query.message.chat_id, context)

        elif query.data == "admin_menu":
            await query.message.delete()
            await send_admin_menu(query.message.chat_id, context)

        return

    if query.data == "verify":
        # Check subscriptions
        required_chats = database.get_all_required_chats()
        all_subscribed = True

        for chat in required_chats:
            is_subscribed = await check_subscription(context.bot, user_id, chat['chat_id'])
            if not is_subscribed:
                all_subscribed = False
                break

        if all_subscribed:
            # Mark user as verified in DB
            database.mark_verified(user_id)

            # Record the specific chats they verified against
            for chat in required_chats:
                database.add_user_verified_chat(user_id, chat['chat_id'])

            await query.edit_message_text(
                text="✅ Subscription verified! You are now eligible to refer others. Click /start to return to the main menu."
            )
        else:
            database.clear_user_verification(user_id)
            keyboard = []
            for chat in required_chats:
                keyboard.append([InlineKeyboardButton(f"📢 Join {chat['chat_name']}", url=chat['chat_link'])])

            keyboard.append([InlineKeyboardButton("✅ Try Verifying Again", callback_data="verify")])
            keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="start_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                text=(
                    "❌ Verification failed.\n\n"
                    "Please make sure you have joined all required channels/groups using the buttons below.\n\n"
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

        required_referrals = int(database.get_config('required_referrals', '10'))
        is_verified_str = "✅ Yes" if user_data['is_verified'] else "❌ No (Please click 'Verify Subscription')"
        successful_referrals = database.get_successful_referrals_count(user_id)

        await query.edit_message_text(
            text=(
                "👤 <b>Your Profile</b>\n\n"
                f"Status: Subscribed? {is_verified_str}\n"
                f"Successful Referrals: {successful_referrals} / {required_referrals}\n\n"
                f"🔗 <b>Your Referral Link:</b>\n{referral_link}\n\n"
                "(A referral is only counted as 'Successful' when the person you invite subscribes to all required channels and groups.)\n\n"
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

        # Verify the user is STILL subscribed to the channels they originally verified against
        user_verified_chats = database.get_user_verified_chats(user_id)

        # If they somehow have no recorded chats but are "verified", fallback to the global list
        # (This handles backwards compatibility if someone was verified before this update)
        if not user_verified_chats:
             chats_to_check = [c['chat_id'] for c in database.get_all_required_chats()]
        else:
             chats_to_check = user_verified_chats

        all_subscribed = True

        for chat_id_to_check in chats_to_check:
            is_subscribed = await check_subscription(context.bot, user_id, chat_id_to_check)
            if not is_subscribed:
                all_subscribed = False
                break

        if not all_subscribed:
            database.clear_user_verification(user_id)
            await query.edit_message_text(
                text=(
                    "❌ You have left one or more required channels!\n\n"
                    "You must remain subscribed to all required channels and groups to claim your reward.\n\n"
                    "Please go to the main menu and 'Verify Subscription' again."
                )
            )
            return

        required_referrals = int(database.get_config('required_referrals', '10'))
        successful_referrals = database.get_successful_referrals_count(user_id)

        if successful_referrals >= required_referrals:
            private_channel_id = database.get_config('private_channel_id')
            if not private_channel_id:
                await query.edit_message_text("❌ The Private Channel has not been set up by the admin yet.")
                return

            try:
                # Generate a single-use invite link for the private channel
                invite_link = await context.bot.create_chat_invite_link(
                    chat_id=private_channel_id,
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
                    f"You need {required_referrals} successful referrals to get the private link.\n"
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

    # Migrate env variables to DB if DB is empty
    if database.get_config("private_channel_id") is None:
        database.set_config("private_channel_id", os.getenv("PRIVATE_CHANNEL_ID", ""))
    if database.get_config("required_referrals") is None:
        database.set_config("required_referrals", os.getenv("REQUIRED_REFERRALS", "10"))
    if len(database.get_all_required_chats()) == 0:
        # Default fallback to env or hardcoded logic
        database.add_required_chat("Public Channel", os.getenv("PUBLIC_CHANNEL_ID", "@neetpgfmgemcqhourly"), os.getenv("PUBLIC_CHANNEL_LINK", "https://t.me/neetpgfmgemcqhourly"))
        database.add_required_chat("Public Group", os.getenv("PUBLIC_GROUP_ID", "@neetpgpyqhourly"), os.getenv("PUBLIC_GROUP_LINK", "https://t.me/neetpgpyqhourly"))

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
