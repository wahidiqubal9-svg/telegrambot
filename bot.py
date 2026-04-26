import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters, ChatJoinRequestHandler, ChatMemberHandler
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
WAITING_FOR_CHAT_ID, WAITING_FOR_CHAT_LINK, WAITING_FOR_PRIVATE_CHANNEL, WAITING_FOR_REFERRAL_GOAL, WAITING_FOR_WELCOME_MESSAGE, WAITING_FOR_BROADCAST_MESSAGE, WAITING_FOR_QR_CODE = range(7)

# Conversation states for User panel
WAITING_FOR_PAYMENT_SCREENSHOT = 100

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send the admin panel."""
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("Manage Required Chats", callback_data="admin_manage_chats")],
        [InlineKeyboardButton("Set Private Channel ID", callback_data="admin_set_private")],
        [InlineKeyboardButton("Set Referral Goal", callback_data="admin_set_goal")],
        [InlineKeyboardButton("Set Welcome Message", callback_data="admin_set_welcome")],
        [InlineKeyboardButton("Set Payment QR Code", callback_data="admin_set_qr_code")],
        [InlineKeyboardButton("View Referrer Stats", callback_data="admin_view_referrers")],
        [InlineKeyboardButton("Test private link", callback_data="admin_test_link")],
        [InlineKeyboardButton("Broadcast Messages", callback_data="admin_broadcast_menu")],
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

    elif query.data == "admin_set_qr_code":
        keyboard = [[InlineKeyboardButton("Back", callback_data="admin_back")]]
        await query.edit_message_text("Please send the new QR code image as a photo.", reply_markup=InlineKeyboardMarkup(keyboard))
        return WAITING_FOR_QR_CODE

    elif query.data == "admin_broadcast_menu":
        keyboard = [
            [InlineKeyboardButton("Broadcast to All", callback_data="admin_broadcast_all")],
            [InlineKeyboardButton("Broadcast to Premium Members", callback_data="admin_broadcast_premium")],
            [InlineKeyboardButton("Broadcast to Regulars", callback_data="admin_broadcast_regular")],
            [InlineKeyboardButton("Sync Premium Members", callback_data="admin_sync_premium")],
            [InlineKeyboardButton("Back", callback_data="admin_back")]
        ]
        await query.edit_message_text("Select broadcast target:", reply_markup=InlineKeyboardMarkup(keyboard))
        # Keep conversation active to receive the broadcast message callbacks
        return WAITING_FOR_BROADCAST_MESSAGE

    elif query.data.startswith("admin_broadcast_") and query.data != "admin_broadcast_menu":
        target = query.data.split("_")[-1]
        context.user_data['broadcast_target'] = target

        target_name = "all users"
        if target == "premium":
            target_name = "premium members (in private channel)"
        elif target == "regular":
            target_name = "regular users (not in private channel)"

        keyboard = [[InlineKeyboardButton("Back", callback_data="admin_broadcast_menu")]]
        await query.edit_message_text(f"Please send the message you want to broadcast to {target_name}.", reply_markup=InlineKeyboardMarkup(keyboard))
        return WAITING_FOR_BROADCAST_MESSAGE

    elif query.data == "admin_sync_premium":
        await query.edit_message_text("Starting synchronization of premium members... This may take a while. You will be notified when it is complete.")
        asyncio.create_task(sync_premium_members(context.bot, query.from_user.id))
        return ConversationHandler.END

    elif query.data == "admin_back":
        keyboard = [
            [InlineKeyboardButton("Manage Required Chats", callback_data="admin_manage_chats")],
            [InlineKeyboardButton("Set Private Channel ID", callback_data="admin_set_private")],
            [InlineKeyboardButton("Set Referral Goal", callback_data="admin_set_goal")],
            [InlineKeyboardButton("Set Welcome Message", callback_data="admin_set_welcome")],
            [InlineKeyboardButton("Set Payment QR Code", callback_data="admin_set_qr_code")],
            [InlineKeyboardButton("View Referrer Stats", callback_data="admin_view_referrers")],
            [InlineKeyboardButton("Test private link", callback_data="admin_test_link")],
            [InlineKeyboardButton("Broadcast Messages", callback_data="admin_broadcast_menu")],
            [InlineKeyboardButton("Close", callback_data="admin_close")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Admin Panel:", reply_markup=reply_markup)
        return ConversationHandler.END

    elif query.data == "admin_view_referrers":
        referrers = database.get_all_referrers()

        if not referrers:
            text = "No one has made any successful referrals yet."
        else:
            text = "<b>Referrer Statistics:</b>\n\n"
            for idx, r in enumerate(referrers, 1):
                text += f"{idx}. User ID <code>{r['telegram_id']}</code> - {r['referrals']} referrals\n"
                # Telegram message length limit precaution
                if len(text) > 3500:
                    text += "\n<i>...list truncated due to length...</i>"
                    break

        keyboard = [[InlineKeyboardButton("Back", callback_data="admin_back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
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
    database.set_config("MASTER_INVITE_LINK", "")
    await update.message.reply_text(f"Private Channel ID updated to {chat_id}. Master invite link has been reset. Use /admin to return to the panel.")
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

import asyncio
from telegram.error import TelegramError

async def sync_premium_members(bot, admin_chat_id):
    """Background task to sync the private_channel_members table by checking Telegram API directly."""
    users = database.get_all_users()
    private_channel_id = database.get_config("PRIVATE_CHANNEL_ID")

    if not private_channel_id:
        await bot.send_message(chat_id=admin_chat_id, text="Private Channel ID is not set. Cannot sync.")
        return

    success_count = 0
    fail_count = 0

    for user_id in users:
        try:
            member = await bot.get_chat_member(chat_id=private_channel_id, user_id=user_id)
            if member.status in ['member', 'creator', 'administrator', 'restricted']:
                database.add_private_channel_member(user_id)
                success_count += 1
            else:
                database.remove_private_channel_member(user_id)
        except BadRequest as e:
            # User not in channel or bot doesn't have access
            database.remove_private_channel_member(user_id)
        except Exception as e:
            logger.error(f"Error checking status for {user_id}: {e}")
            fail_count += 1

        await asyncio.sleep(0.05) # Rate limit protection

    await bot.send_message(
        chat_id=admin_chat_id,
        text=f"🔄 <b>Sync Completed!</b>\n\nFound {success_count} premium members.\nFailed checks: {fail_count}",
        parse_mode='HTML'
    )

async def admin_receive_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive broadcast message from admin and send it to target users."""
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    message_text = update.message.text
    if not message_text:
        await update.message.reply_text("Please send text only. Use /admin to return to the panel.")
        return ConversationHandler.END

    target = context.user_data.get('broadcast_target', 'all')

    if target == 'premium':
        users = database.get_all_private_channel_members()
    elif target == 'regular':
        users = database.get_regular_users()
    else:
        users = database.get_all_users()

    if not users:
        await update.message.reply_text("No users found for this target. Use /admin to return to the panel.")
        return ConversationHandler.END

    target_name = "all users"
    if target == "premium":
        target_name = "premium members"
    elif target == "regular":
        target_name = "regular users"

    await update.message.reply_text(f"Starting broadcast to {len(users)} {target_name}... This may take a while. I will notify you when it's done.")

    # Run broadcast in background
    asyncio.create_task(run_broadcast(context.bot, users, message_text, update.message.chat_id))

    return ConversationHandler.END

async def run_broadcast(bot, users, message_text, admin_chat_id):
    """Background task to run the broadcast."""
    success_count = 0
    fail_count = 0

    required_referrals = int(database.get_config("REQUIRED_REFERRALS", "10"))
    keyboard = [
        [InlineKeyboardButton(f"🆓 Invite {required_referrals} Friends & Get It Free", callback_data="get_for_free")],
        [InlineKeyboardButton("💸 Get it For ₹300 (No Invites)", callback_data="pay_instantly")],
        [InlineKeyboardButton("💬 Talk to Admin", url="https://t.me/talkTOadminnn_bot")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    for user_id in users:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            success_count += 1
        except TelegramError as e:
            logger.error(f"Failed to send broadcast to {user_id}: {e}")
            fail_count += 1
        except Exception as e:
            logger.error(f"Unexpected error sending broadcast to {user_id}: {e}")
            fail_count += 1

        # Small delay to avoid hitting Telegram rate limits (approx 30 messages per second is limit)
        await asyncio.sleep(0.05)

    try:
        await bot.send_message(
            chat_id=admin_chat_id,
            text=f"📢 <b>Broadcast Completed!</b>\n\n✅ Successful: {success_count}\n❌ Failed: {fail_count}\n\nFailed messages usually mean the user has blocked the bot or their account is deleted.",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Failed to send broadcast summary to admin: {e}")

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles chat join requests by automatically approving users who meet the criteria."""
    join_request = update.chat_join_request
    user_id = join_request.from_user.id

    user_data = database.get_user(user_id)
    if not user_data:
        await join_request.decline()
        return

    is_verified = user_data.get('is_verified', False)
    successful_referrals = database.get_successful_referrals_count(user_id)
    required_referrals = int(database.get_config("REQUIRED_REFERRALS", "10"))

    if is_verified and successful_referrals >= required_referrals:
        try:
            await join_request.approve()
            # Optionally send a success message here if we want
        except Exception as e:
            logger.error(f"Error approving join request for {user_id}: {e}")
    else:
        try:
            await join_request.decline()
        except Exception as e:
            logger.error(f"Error declining join request for {user_id}: {e}")

async def admin_receive_qr_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle receiving the new payment QR code image from the admin."""
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    photo = update.message.photo[-1] # Get the highest resolution photo
    file_id = photo.file_id

    database.set_config("PAYMENT_QR_FILE_ID", file_id)

    keyboard = [[InlineKeyboardButton("Back to Admin Panel", callback_data="admin_close")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "✅ Payment QR code has been successfully updated!",
        reply_markup=reply_markup
    )

    return ConversationHandler.END

async def user_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback when user clicks 'after payment' button."""
    query = update.callback_query
    await query.answer()

    keyboard = [[InlineKeyboardButton("🔙 Cancel & Back", callback_data="start_menu_from_conv")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_caption(
        caption="Please upload the screenshot of your successful payment below. Our admin will verify it shortly.",
        reply_markup=reply_markup
    )
    return WAITING_FOR_PAYMENT_SCREENSHOT

async def start_menu_from_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback to return to start menu from within a conversation and end it."""
    query = update.callback_query
    await query.answer()

    # Delegate sending the main menu to the existing send_main_menu logic
    await send_main_menu(query.message.chat_id, query.from_user.id, context, query=query)

    return ConversationHandler.END


async def receive_payment_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user uploading a payment screenshot."""
    user = update.effective_user
    photo = update.message.photo[-1]
    file_id = photo.file_id

    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="start_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "✅ Your payment screenshot has been submitted! Please wait for the admin to verify it.",
        reply_markup=reply_markup
    )

    # Send to admin
    admin_keyboard = [
        [
            InlineKeyboardButton("✅ Received", callback_data=f"payment_received_{user.id}"),
            InlineKeyboardButton("❌ Didn't Receive", callback_data=f"payment_rejected_{user.id}")
        ]
    ]
    admin_markup = InlineKeyboardMarkup(admin_keyboard)

    username_str = f" (@{user.username})" if user.username else ""
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=file_id,
        caption=f"Payment screenshot submitted by User {user.id}{username_str}.",
        reply_markup=admin_markup
    )

    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    return ConversationHandler.END

async def send_main_menu(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE, query=None) -> None:
    """Send the main menu with inline buttons."""
    required_referrals = int(database.get_config("REQUIRED_REFERRALS", "10"))
    welcome_text = database.get_config("WELCOME_MESSAGE", "Welcome! Please choose an option below.")

    # Replace dynamic placeholder if it exists in the text
    welcome_text = welcome_text.replace("{required_referrals}", str(required_referrals))

    keyboard = [
        [InlineKeyboardButton(f"🆓 Invite {required_referrals} Friends & Get It Free", callback_data="get_for_free")],
        [InlineKeyboardButton("💸 Get it For ₹300 (No Invites)", callback_data="pay_instantly")],
        [InlineKeyboardButton("💬 Talk to Admin", url="https://t.me/talkTOadminnn_bot")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        # Check if the query message is a photo (like QR code). If so, we need to delete it and send a new text message.
        if query.message.photo:
            try:
                await query.message.delete()
            except Exception:
                pass
            sent_message = await context.bot.send_message(
                chat_id=chat_id,
                text=welcome_text,
                reply_markup=reply_markup,
            )
            database.update_last_message_id(user_id, sent_message.message_id)
        else:
            try:
                await query.edit_message_text(
                    text=welcome_text,
                    reply_markup=reply_markup,
                )
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    pass
                else:
                    raise e
    else:
        sent_message = await context.bot.send_message(
            chat_id=chat_id,
            text=welcome_text,
            reply_markup=reply_markup,
        )
        database.update_last_message_id(user_id, sent_message.message_id)

async def track_chats_member_updates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Track member updates to auto-verify users when they join required channels."""
    result = update.chat_member
    if not result:
        return

    user_id = result.new_chat_member.user.id
    status = result.new_chat_member.status
    chat_id = str(result.chat.id)

    # Check for private channel updates
    private_channel_id = str(database.get_config("PRIVATE_CHANNEL_ID", ""))

    # Sometimes chat IDs can be stored as usernames (e.g. @channel) or numbers
    # To be safe, we check if either matches
    private_channel_username = ""
    if result.chat.username:
        private_channel_username = f"@{result.chat.username}"

    if private_channel_id and (chat_id == private_channel_id or private_channel_username == private_channel_id):
        if status in ['member', 'administrator', 'creator', 'restricted']:
            database.add_private_channel_member(user_id)
        elif status in ['left', 'kicked']:
            database.remove_private_channel_member(user_id)

    # We only care if they just became a member/restricted (joined)
    if status not in ['member', 'administrator', 'creator', 'restricted']:
        return

    user_data = database.get_user(user_id)
    if not user_data or user_data['is_verified']:
        return

    # User exists and is unverified. Check if they have now joined all required chats
    required_chats = database.get_required_chats()
    if not required_chats:
        return

    all_subscribed = True
    for chat in required_chats:
        is_sub = await check_subscription(context.bot, user_id, chat['chat_id'])
        if not is_sub:
            all_subscribed = False
            break
        else:
            database.add_user_verified_chat(user_id, chat['chat_id'])

    if all_subscribed:
        database.mark_verified(user_id)

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

async def verify_unverified_referrals(bot, referrer_id: int):
    """Silently check and verify any unverified referrals for a given user."""
    unverified_referrals = database.get_unverified_referrals(referrer_id)
    if not unverified_referrals:
        return

    required_chats = database.get_required_chats()
    if not required_chats:
        return

    for referred_user_id in unverified_referrals:
        all_subscribed = True
        for chat in required_chats:
            is_sub = await check_subscription(bot, referred_user_id, chat['chat_id'])
            if not is_sub:
                all_subscribed = False
                break
            else:
                database.add_user_verified_chat(referred_user_id, chat['chat_id'])

        if all_subscribed:
            database.mark_verified(referred_user_id)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data.startswith("payment_received_") or query.data.startswith("payment_rejected_"):
        if user_id != ADMIN_ID:
            await query.answer("Unauthorized.", show_alert=True)
            return

        target_user_id = int(query.data.split("_")[-1])

        if query.data.startswith("payment_received_"):
            # Provide single-use link
            private_channel_id = database.get_config("PRIVATE_CHANNEL_ID")
            if not private_channel_id:
                await query.edit_message_caption("Payment accepted, but Private Channel ID is not set. Could not generate link.")
                return

            try:
                invite_link = await context.bot.create_chat_invite_link(
                    chat_id=private_channel_id,
                    member_limit=1,
                    name=f"Paid Link User {target_user_id}"
                )

                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=(
                        "✅ <b>Your payment was verified!</b>\n\n"
                        "Here is your single-use invite link to access CoreBTR videos:\n\n"
                        f"{invite_link.invite_link}\n\n"
                        "⚠️ Note: This link will expire after one use. Do not share it!"
                    ),
                    parse_mode='HTML'
                )

                await query.edit_message_caption(f"✅ Payment accepted. Link sent to User {target_user_id}.")
            except Exception as e:
                logger.error(f"Error generating paid link for {target_user_id}: {e}")
                await query.edit_message_caption(f"Payment accepted, but failed to generate link. Check bot permissions.")

        elif query.data.startswith("payment_rejected_"):
            await context.bot.send_message(
                chat_id=target_user_id,
                text="❌ <b>Your payment could not be verified.</b>\n\nPlease ensure you sent the correct screenshot, or contact support.",
                parse_mode='HTML'
            )
            await query.edit_message_caption(f"❌ Payment rejected for User {target_user_id}.")

        return

    if query.data == "get_for_free" or query.data == "verify_subscriptions":
        user_data = database.get_user(user_id)
        if not user_data:
            database.add_user(user_id)
            user_data = database.get_user(user_id)

        all_subscribed = True
        unsubscribed_chats = []

        if user_data['is_verified']:
            # Already verified, only check the chats they originally verified against
            verified_chats = database.get_user_verified_chats(user_id)
            for chat_id in verified_chats:
                is_sub = await check_subscription(context.bot, user_id, chat_id)
                if not is_sub:
                    all_subscribed = False
                    database.mark_unverified(user_id)
                    database.remove_user_verified_chat(user_id, chat_id)
                    # We need the chat details for the unsubscribed chat
                    required_chats = database.get_required_chats()
                    for chat in required_chats:
                        if chat['chat_id'] == chat_id:
                            unsubscribed_chats.append(chat)
                            break
                    break

        if not user_data['is_verified'] or not all_subscribed:
            # Not verified, check against all current required chats
            all_subscribed = True
            unsubscribed_chats = []
            required_chats = database.get_required_chats()
            for chat in required_chats:
                is_sub = await check_subscription(context.bot, user_id, chat['chat_id'])
                if not is_sub:
                    all_subscribed = False
                    unsubscribed_chats.append(chat)
                    database.remove_user_verified_chat(user_id, chat['chat_id'])
                else:
                    database.add_user_verified_chat(user_id, chat['chat_id'])

            if not all_subscribed:
                database.mark_unverified(user_id)

        # Get all required chats to display buttons always
        all_required_chats = database.get_required_chats()

        if all_subscribed:
            if not user_data['is_verified']:
                database.mark_verified(user_id)

            # Show Referral Hub
            bot_username = context.bot.username
            referral_link = f"https://t.me/{bot_username}?start={user_id}"

            hub_text = (
                "✅ <b>You are subscribed!</b>\n\n"
                "👇 Tap on the link below to copy:\n"
                f"<code>{referral_link}</code>\n\n"
                "🎁 How to earn:\n"
                "Share this link with friends. You get 1 successful referral when they join our free channels shown as channel 1 & channel 2!"
            )

            keyboard = []
            for i, chat in enumerate(all_required_chats, start=1):
                keyboard.append([InlineKeyboardButton(f"📢 Subscribe Channel {i}", url=chat['link'])])

            keyboard.extend([
                [InlineKeyboardButton("👤 Check your referrals", callback_data="profile")],
                [InlineKeyboardButton("🎁 Claim free CoreBTR + PDFs", callback_data="get_link")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="start_menu")]
            ])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                text=hub_text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        else:
            keyboard = []
            # Show buttons for all required channels regardless of subscription
            for i, chat in enumerate(all_required_chats, start=1):
                keyboard.append([InlineKeyboardButton(f"📢 Subscribe Channel {i}", url=chat['link'])])

            keyboard.extend([
                [InlineKeyboardButton("🔄 Verify Subscriptions", callback_data="verify_subscriptions")],
                [InlineKeyboardButton("🔙 Back", callback_data="start_menu")]
            ])
            reply_markup = InlineKeyboardMarkup(keyboard)

            msg_text = "Please subscribe to the channels below. Once you subscribe, click 'Verify Subscriptions' to continue."
            if query.data == "verify_subscriptions":
                msg_text = "❌ Verification failed. Please make sure you have joined all the remaining channels below, then click 'Verify Subscriptions'."

            await query.edit_message_text(
                text=msg_text,
                reply_markup=reply_markup
            )

    elif query.data == "pay_instantly":
        qr_file_id = database.get_config("PAYMENT_QR_FILE_ID")

        if not qr_file_id:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="start_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                text="The payment QR code has not been set by the admin yet. Please try again later or contact support.",
                reply_markup=reply_markup
            )
            return

        keyboard = [
            [InlineKeyboardButton("✅ Click here after payment", callback_data="after_payment")],
            [InlineKeyboardButton("🔙 Back", callback_data="start_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # We must delete the current text message and send a photo message
        try:
            await query.message.delete()
        except Exception:
            pass

        sent_msg = await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=qr_file_id,
            caption="Please scan the QR code to pay ₹300.\n\nOnce paid, click the button below to upload your screenshot.",
            reply_markup=reply_markup
        )
        database.update_last_message_id(user_id, sent_msg.message_id)

    elif query.data == "start_menu":
        # Edit the previous callback message to show the main menu
        await send_main_menu(query.message.chat_id, user_id, context, query=query)

    elif query.data == "profile":
        # Perform on-demand check for unverified referrals first
        await verify_unverified_referrals(context.bot, user_id)

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
        # Perform on-demand check for unverified referrals first
        await verify_unverified_referrals(context.bot, user_id)

        user_data = database.get_user(user_id)

        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="start_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        successful_referrals = database.get_successful_referrals_count(user_id)
        required_referrals = int(database.get_config("REQUIRED_REFERRALS", "10"))

        if successful_referrals >= required_referrals:
            try:
                private_channel_id = database.get_config("PRIVATE_CHANNEL_ID")

                if not private_channel_id:
                    await query.edit_message_text(
                        text="The private channel has not been fully configured yet. Please contact an administrator at @talkTOadminnn_bot.",
                        reply_markup=reply_markup
                    )
                    return

                master_invite_link = database.get_config("MASTER_INVITE_LINK")

                if not master_invite_link:
                    try:
                        invite_link = await context.bot.create_chat_invite_link(
                            chat_id=private_channel_id,
                            creates_join_request=True,
                            name="Master Join Link"
                        )
                        master_invite_link = invite_link.invite_link
                        database.set_config("MASTER_INVITE_LINK", master_invite_link)
                    except Exception as e:
                        logger.error(f"Error creating master invite link: {e}")
                        await query.edit_message_text(
                            text="An error occurred while generating the invite link. Please make sure the bot is an Administrator in the Private Channel with permission to 'Invite Users'.",
                            reply_markup=reply_markup
                        )
                        return

                await query.edit_message_text(
                    text=(
                        "🎉 Congratulations! You have reached the required number of referrals.\n\n"
                        f"Here is your link to access CoreBTR videos: {master_invite_link}\n\n"
                        "⚠️ Note: Click the link and request to join. The bot will automatically approve your request!"
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
            WAITING_FOR_REFERRAL_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_referral_goal)],
            WAITING_FOR_WELCOME_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_welcome_message)],
            WAITING_FOR_BROADCAST_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_broadcast_message),
                CallbackQueryHandler(admin_button_callback, pattern="^admin_")
            ],
            WAITING_FOR_QR_CODE: [MessageHandler(filters.PHOTO & ~filters.COMMAND, admin_receive_qr_code)],
        },
        fallbacks=[
            CommandHandler("admin", admin_start),
            CallbackQueryHandler(admin_button_callback, pattern="^admin_")
        ],
        allow_reentry=True
    )
    application.add_handler(admin_conv_handler)

    # User Conversation Handler (for uploading payment screenshots)
    user_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(user_payment_callback, pattern="^after_payment$")
        ],
        states={
            WAITING_FOR_PAYMENT_SCREENSHOT: [MessageHandler(filters.PHOTO & ~filters.COMMAND, receive_payment_screenshot)],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(start_menu_from_conv, pattern="^start_menu_from_conv$")
        ],
        allow_reentry=True
    )
    application.add_handler(user_conv_handler)

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    application.add_handler(ChatMemberHandler(track_chats_member_updates, ChatMemberHandler.CHAT_MEMBER))

    # Trigger /start for any text message that is not a command
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
