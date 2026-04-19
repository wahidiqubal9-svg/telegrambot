import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters, ChatJoinRequestHandler
from telegram.error import BadRequest

import database

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID = 1044834121

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states for Admin panel
WAITING_FOR_CHAT_ID, WAITING_FOR_CHAT_LINK, WAITING_FOR_PRIVATE_CHANNEL, WAITING_FOR_PRIVATE_CHANNEL_LINK, WAITING_FOR_REFERRAL_GOAL, WAITING_FOR_WELCOME_MESSAGE = range(6)

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send the admin panel."""
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("Manage Required Chats", callback_data="admin_manage_chats")],
        [InlineKeyboardButton("Set Private Channel ID", callback_data="admin_set_private")],
        [InlineKeyboardButton("Set Private Join Link", callback_data="admin_set_private_link")],
        [InlineKeyboardButton("Set Referral Goal", callback_data="admin_set_goal")],
        [InlineKeyboardButton("Set Welcome Message", callback_data="admin_set_welcome")],
        [InlineKeyboardButton("Test private link", callback_data="admin_test_link")],
        [InlineKeyboardButton("Close", callback_data="admin_close")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Admin Panel:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Admin Panel:", reply_markup=reply_markup)

    return ConversationHandler.END

async def admin_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin inline buttons."""
    query = update.callback_query
    user_id = query.from_user.id

    if user_id != ADMIN_ID:
        await query.answer("You are not authorized.")
        return ConversationHandler.END

    await query.answer()

    if query.data == "admin_manage_chats":
        chats = database.get_required_chats()
        text = "<b>Current Required Chats:</b>\n"
        keyboard = []
        for chat in chats:
            text += f"• {chat['chat_id']}\n"
            keyboard.append([InlineKeyboardButton(f"Remove {chat['chat_id']}", callback_data=f"admin_remove_chat_{chat['id']}")])

        keyboard.append([InlineKeyboardButton("Add New Chat", callback_data="admin_add_chat")])
        keyboard.append([InlineKeyboardButton("Back", callback_data="admin_back")])

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return ConversationHandler.END

    elif query.data.startswith("admin_remove_chat_"):
        chat_id_db = int(query.data.split("_")[-1])
        database.remove_required_chat(chat_id_db)
        await query.edit_message_text("Chat removed successfully.")
        # Re-trigger manage chats view
        query.data = "admin_manage_chats"
        return await admin_button_callback(update, context)

    elif query.data == "admin_add_chat":
        keyboard = [[InlineKeyboardButton("Back", callback_data="admin_back")]]
        await query.edit_message_text("Please send the chat ID (e.g., @mychannel or -100123456789) of the new required chat.", reply_markup=InlineKeyboardMarkup(keyboard))
        return WAITING_FOR_CHAT_ID

    elif query.data == "admin_set_private":
        current = database.get_config("PRIVATE_CHANNEL_ID", "Not set")
        keyboard = [[InlineKeyboardButton("Back", callback_data="admin_back")]]
        await query.edit_message_text(f"Current Private Channel ID: {current}\n\nPlease send the new Private Channel ID.", reply_markup=InlineKeyboardMarkup(keyboard))
        return WAITING_FOR_PRIVATE_CHANNEL

    elif query.data == "admin_set_private_link":
        current = database.get_config("PRIVATE_JOIN_LINK", "Not set")
        keyboard = [[InlineKeyboardButton("Back", callback_data="admin_back")]]
        await query.edit_message_text(f"Current Private Join Link (Join Request Link): {current}\n\nPlease send the new permanent join request link for the private channel.", reply_markup=InlineKeyboardMarkup(keyboard))
        return WAITING_FOR_PRIVATE_CHANNEL_LINK

    elif query.data == "admin_set_goal":
        current = database.get_config("REQUIRED_REFERRALS", "10")
        keyboard = [[InlineKeyboardButton("Back", callback_data="admin_back")]]
        await query.edit_message_text(f"Current Referral Goal: {current}\n\nPlease send the new referral goal (integer).", reply_markup=InlineKeyboardMarkup(keyboard))
        return WAITING_FOR_REFERRAL_GOAL

    elif query.data == "admin_set_welcome":
        current = database.get_config("WELCOME_MESSAGE", "Not set")
        keyboard = [[InlineKeyboardButton("Back", callback_data="admin_back")]]
        await query.edit_message_text(f"Current Welcome Message:\n\n{current}\n\nPlease send the new welcome message text. You can use {{required_referrals}} as a placeholder to automatically insert the current goal.", reply_markup=InlineKeyboardMarkup(keyboard))
        return WAITING_FOR_WELCOME_MESSAGE

    elif query.data == "admin_back":
        keyboard = [
            [InlineKeyboardButton("Manage Required Chats", callback_data="admin_manage_chats")],
            [InlineKeyboardButton("Set Private Channel ID", callback_data="admin_set_private")],
            [InlineKeyboardButton("Set Private Join Link", callback_data="admin_set_private_link")],
            [InlineKeyboardButton("Set Referral Goal", callback_data="admin_set_goal")],
            [InlineKeyboardButton("Set Welcome Message", callback_data="admin_set_welcome")],
            [InlineKeyboardButton("Test private link", callback_data="admin_test_link")],
            [InlineKeyboardButton("Close", callback_data="admin_close")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Admin Panel:", reply_markup=reply_markup)
        return ConversationHandler.END

    elif query.data == "admin_test_link":
        private_channel_id = database.get_config("PRIVATE_CHANNEL_ID")
        if not private_channel_id:
            await context.bot.send_message(chat_id=user_id, text="The private channel has not been configured yet. Please set it first.")
            return ConversationHandler.END

        try:
            # Generate a single-use invite link for the private channel
            invite_link = await context.bot.create_chat_invite_link(
                chat_id=private_channel_id,
                member_limit=1,
                name="Admin Test Link"
            )
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Here is your test single-use link: {invite_link.invite_link}\n\n⚠️ Note: This link can only be used once."
            )
        except Exception as e:
            logger.error(f"Error creating admin test invite link: {e}")
            await context.bot.send_message(
                chat_id=user_id,
                text="An error occurred while generating the test invite link. Please make sure the bot is an Administrator in the Private Channel with permission to 'Invite Users'."
            )
        return ConversationHandler.END

    elif query.data == "admin_close":
        await query.edit_message_text("Admin panel closed.")
        return ConversationHandler.END

    return ConversationHandler.END

async def admin_receive_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive chat ID from admin."""
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    chat_id = update.message.text.strip()
    context.user_data['temp_chat_id'] = chat_id
    await update.message.reply_text(f"Received chat ID: {chat_id}\n\nNow, please send the invite link for this chat (e.g., https://t.me/mychannel).")
    return WAITING_FOR_CHAT_LINK

async def admin_receive_chat_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive chat link from admin."""
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    link = update.message.text.strip()
    chat_id = context.user_data.get('temp_chat_id')

    if database.add_required_chat(chat_id, link):
        await update.message.reply_text("Required chat added successfully! Use /admin to return to the panel.")
    else:
        await update.message.reply_text("Failed to add chat. It might already exist. Use /admin to return to the panel.")

    return ConversationHandler.END

async def admin_receive_private_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive private channel ID from admin."""
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    chat_id = update.message.text.strip()
    database.set_config("PRIVATE_CHANNEL_ID", chat_id)
    await update.message.reply_text(f"Private Channel ID updated to {chat_id}. Use /admin to return to the panel.")
    return ConversationHandler.END

async def admin_receive_private_channel_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive private channel join request link from admin."""
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    link = update.message.text.strip()
    database.set_config("PRIVATE_JOIN_LINK", link)
    await update.message.reply_text(f"Private Join Link updated successfully. Use /admin to return to the panel.")
    return ConversationHandler.END

async def admin_receive_referral_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive referral goal from admin."""
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    try:
        goal = int(update.message.text.strip())
        if goal <= 0:
            raise ValueError
        database.set_config("REQUIRED_REFERRALS", str(goal))
        await update.message.reply_text(f"Referral goal updated to {goal}. Use /admin to return to the panel.")
    except ValueError:
        await update.message.reply_text("Invalid input. Please send a positive integer. Use /admin to return to the panel.")

    return ConversationHandler.END

async def admin_receive_welcome_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive welcome message from admin."""
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    text = update.message.text.strip()
    database.set_config("WELCOME_MESSAGE", text)
    await update.message.reply_text("Welcome message updated! Use /admin to return to the panel.")
    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    chat_id = update.effective_chat.id

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

    # Delete previous main menu message if it exists
    last_message_id = database.get_last_message_id(user.id)
    if last_message_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_message_id)
        except BadRequest:
            pass # Message might already be deleted

    await send_main_menu(chat_id, user.id, context)

async def send_main_menu(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE, query=None) -> None:
    """Send the main menu with inline buttons."""
    required_chats = database.get_required_chats()
    required_referrals = int(database.get_config("REQUIRED_REFERRALS", "10"))
    welcome_text = database.get_config("WELCOME_MESSAGE", "Welcome! To gain access to our exclusive Private Channel, you need to:\n\n1. Subscribe to our required channels\n2. Invite {required_referrals} friends using your referral link who also complete step 1.\n\nUse the buttons below to navigate.")

    # Replace dynamic placeholder if it exists in the text
    welcome_text = welcome_text.replace("{required_referrals}", str(required_referrals))

    keyboard = []
    # Add one button per row with dynamic step numbers
    for i, chat in enumerate(required_chats, start=1):
        keyboard.append([InlineKeyboardButton(f"📢 Step {i}: Subscribe Channel {i}", url=chat['link'])])

    verify_step = len(required_chats) + 1

    keyboard.extend([
        [InlineKeyboardButton(f"🔗 Step {verify_step}: Get your refer link", callback_data="get_refer_link")],
        [InlineKeyboardButton("👤 Check your referrals", callback_data="profile")],
        [InlineKeyboardButton("🎁 Get CoreBTR videos", callback_data="get_link")]
    ])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(
            text=welcome_text,
            reply_markup=reply_markup,
        )
    else:
        sent_message = await context.bot.send_message(
            chat_id=chat_id,
            text=welcome_text,
            reply_markup=reply_markup,
        )
        database.update_last_message_id(user_id, sent_message.message_id)

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

    if query.data == "verify" or query.data == "get_refer_link":
        user_data = database.get_user(user_id)
        if not user_data:
            database.add_user(user_id)
            user_data = database.get_user(user_id)

        all_subscribed = True

        if user_data['is_verified']:
            # Already verified, only check the chats they originally verified against
            verified_chats = database.get_user_verified_chats(user_id)
            for chat_id in verified_chats:
                is_sub = await check_subscription(context.bot, user_id, chat_id)
                if not is_sub:
                    all_subscribed = False
                    break
        else:
            # Not verified, check against all current required chats
            required_chats = database.get_required_chats()
            for chat in required_chats:
                is_sub = await check_subscription(context.bot, user_id, chat['chat_id'])
                if not is_sub:
                    all_subscribed = False
                    break
                else:
                    database.add_user_verified_chat(user_id, chat['chat_id'])

        if all_subscribed:
            # Mark user as verified in DB
            if not user_data['is_verified']:
                database.mark_verified(user_id)

            if query.data == "get_refer_link":
                bot_username = context.bot.username
                referral_link = f"https://t.me/{bot_username}?start={user_id}"

                shareable_text = (
                    "🎁 Get Complete CoreBTR videos and Pdfs absolutely free of cost by simply joining the link below.....\n\n"
                    f"👉 Click here to get the videos: {referral_link}\n\n"
                    "📺 Check Demo CoreBTR videos: https://t.me/+WouYXoiPIcE3ZTFl"
                )

                instructions_text = (
                    "⬆️ Forward the message above to your friends to invite them! "
                    "Once they subscribe to the required channels, it will count as a successful referral."
                )

                # Send the two separate messages
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=shareable_text,
                    parse_mode='HTML'
                )
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=instructions_text,
                    parse_mode='HTML'
                )

                # Keep the main menu exactly as it is, or show a brief success message
                keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="start_menu")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    text="✅ Your referral link has been sent below! 👇",
                    reply_markup=reply_markup
                )
            else:
                keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="start_menu")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    text="✅ Subscription verified! You are now eligible to refer others.",
                    reply_markup=reply_markup
                )
        else:
            required_chats = database.get_required_chats()
            keyboard = []
            for i, chat in enumerate(required_chats, start=1):
                keyboard.append([InlineKeyboardButton(f"📢 Step {i}: Subscribe Channel {i}", url=chat['link'])])

            verify_step = len(required_chats) + 1

            keyboard.extend([
                [InlineKeyboardButton(f"🔗 Step {verify_step}: Get your refer link", callback_data="get_refer_link")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="start_menu")]
            ])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                text=(
                    "❌ Verification failed.\n\n"
                    "Please make sure you have joined all our required channels first."
                ),
                reply_markup=reply_markup
            )

    elif query.data == "start_menu":
        # Edit the previous callback message to show the main menu
        await send_main_menu(query.message.chat_id, user_id, context, query=query)

    elif query.data == "profile":
        # Get user stats
        bot_username = context.bot.username
        referral_link = f"https://t.me/{bot_username}?start={user_id}"

        user_data = database.get_user(user_id)
        if not user_data:
            database.add_user(user_id)
            user_data = database.get_user(user_id)

        is_verified_str = "✅ Yes" if user_data['is_verified'] else "❌ No (Please click 'Get your refer link' to verify)"
        successful_referrals = database.get_successful_referrals_count(user_id)
        required_referrals = int(database.get_config("REQUIRED_REFERRALS", "10"))

        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="start_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text=(
                "👤 <b>Your Referrals</b>\n\n"
                f"Status: Subscribed? {is_verified_str}\n"
                f"Successful Referrals: {successful_referrals} / {required_referrals}\n\n"
                f"🔗 <b>Your Referral Link:</b>\n{referral_link}\n\n"
                "(A referral is only counted as 'Successful' when the person you invite subscribes to the required channels.)"
            ),
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    elif query.data == "get_link":
        user_data = database.get_user(user_id)

        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="start_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if user_data and user_data.get('has_claimed_reward'):
            await query.edit_message_text(
                text=(
                    "❌ You have already claimed your reward and received a link.\n\n"
                    "If you lost your link or it expired, please contact the administrators."
                ),
                reply_markup=reply_markup
            )
            return

        successful_referrals = database.get_successful_referrals_count(user_id)

        required_referrals = int(database.get_config("REQUIRED_REFERRALS", "10"))

        if successful_referrals >= required_referrals:
            try:
                private_channel_id = database.get_config("PRIVATE_CHANNEL_ID")
                private_join_link = database.get_config("PRIVATE_JOIN_LINK")

                if not private_channel_id or not private_join_link:
                    await query.edit_message_text(
                        text="The private channel or join link has not been fully configured yet. Please contact an administrator.",
                        reply_markup=reply_markup
                    )
                    return

                # Mark reward as claimed in the database
                database.mark_reward_claimed(user_id)

                await query.edit_message_text(
                    text=(
                        "🎉 Congratulations! You have reached the required number of referrals.\n\n"
                        f"Here is your exclusive link to access CoreBTR videos: {private_join_link}\n\n"
                        "⚠️ Note: Please click the link to 'Request to Join'. The bot will automatically approve your request!"
                    ),
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Error giving invite link: {e}")
                await query.edit_message_text(
                    text="An error occurred while fetching your invite link.",
                    reply_markup=reply_markup
                )
        else:
            await query.edit_message_text(
                text=(
                    f"You need {required_referrals} successful referrals to get access to CoreBTR videos.\n"
                    f"You currently have {successful_referrals}.\n\n"
                    "Share your referral link from 'Check your referrals' to invite more people!"
                ),
                reply_markup=reply_markup
            )

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles chat join requests and approves eligible users."""
    request = update.chat_join_request
    user_id = request.from_user.id
    chat_id = str(request.chat.id)

    private_channel_id = database.get_config("PRIVATE_CHANNEL_ID")

    # Check if the join request is for the configured private channel
    # Note: Sometimes chat.id is an integer, so we compare strings to be safe
    if private_channel_id and str(private_channel_id) == chat_id:
        successful_referrals = database.get_successful_referrals_count(user_id)
        required_referrals = int(database.get_config("REQUIRED_REFERRALS", "10"))

        if successful_referrals >= required_referrals:
            try:
                await request.approve()
                logger.info(f"Approved join request for eligible user {user_id}")
            except Exception as e:
                logger.error(f"Failed to approve join request for {user_id}: {e}")
        else:
            try:
                await request.decline()
                logger.info(f"Declined join request for ineligible user {user_id}")
                # Optionally, notify the user why they were declined
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"❌ Your request to join CoreBTR videos was declined because you have not reached the required {required_referrals} referrals."
                    )
                except Exception:
                    pass # User might have blocked the bot
            except Exception as e:
                logger.error(f"Failed to decline join request for {user_id}: {e}")

def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN or BOT_TOKEN == "123456789:YOUR_BOT_TOKEN_HERE":
        logger.error("Please set the BOT_TOKEN in your .env file!")
        return

    # Initialize database
    database.init_db()

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # Admin Conversation Handler
    admin_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("admin", admin_start),
            CallbackQueryHandler(admin_button_callback, pattern="^admin_")
        ],
        states={
            WAITING_FOR_CHAT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_chat_id)],
            WAITING_FOR_CHAT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_chat_link)],
            WAITING_FOR_PRIVATE_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_private_channel)],
            WAITING_FOR_PRIVATE_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_private_channel_link)],
            WAITING_FOR_REFERRAL_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_referral_goal)],
            WAITING_FOR_WELCOME_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_welcome_message)],
        },
        fallbacks=[
            CommandHandler("admin", admin_start),
            CallbackQueryHandler(admin_button_callback, pattern="^admin_")
        ],
        allow_reentry=True
    )
    application.add_handler(admin_conv_handler)

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Handle chat join requests
    application.add_handler(ChatJoinRequestHandler(handle_join_request))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
