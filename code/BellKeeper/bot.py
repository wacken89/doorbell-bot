import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import os
from dotenv import load_dotenv

from database.database import async_session
from database.models import User, UserRole, UserActivityLog

load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_admin_keyboard():
    """Create keyboard markup for admin users"""
    keyboard = [
        [KeyboardButton("👥 List Users"), KeyboardButton("🔔 Toggle Notifications")],
        [KeyboardButton("🔄 Toggle User"), KeyboardButton("❌ Remove User")],
        [KeyboardButton("⭐ Promote User"), KeyboardButton("❓ Help")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_user_keyboard():
    """Create keyboard markup for regular users"""
    keyboard = [
        [KeyboardButton("📊 Status"), KeyboardButton("❓ Help")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def log_command(session: AsyncSession, user: User, command: str, args: list = None):
    """Helper function to log user commands"""
    details = f"Command: {command}"
    if args:
        details += f", Arguments: {' '.join(args)}"
    
    activity_log = UserActivityLog(
        user_id=user.id,
        action="command",
        details=details,
        user_agent=user.username
    )
    session.add(activity_log)
    await session.commit()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    async with async_session() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = user.scalar_one_or_none()
        
        if not user:
            # Create new user
            new_user = User(
                telegram_id=update.effective_user.id,
                username=update.effective_user.username,
                role=UserRole.USER
            )
            session.add(new_user)
            await session.commit()
            
            # Log user registration
            activity_log = UserActivityLog(
                user_id=new_user.id,
                action="registration",
                details=f"New user registered with username: {new_user.username}",
                user_agent=update.effective_user.language_code
            )
            session.add(activity_log)
            await session.commit()
            
            await update.message.reply_text(
                'Welcome! You have been registered as a new user. '
                'Use the buttons below to interact with the bot.',
                reply_markup=get_user_keyboard()
            )
        else:
            # Log user login
            activity_log = UserActivityLog(
                user_id=user.id,
                action="login",
                details=f"User logged in with username: {user.username}",
                user_agent=update.effective_user.language_code
            )
            session.add(activity_log)
            await session.commit()
            
            keyboard = get_admin_keyboard() if user.role == UserRole.ADMIN else get_user_keyboard()
            await update.message.reply_text(
                f'Welcome back {user.username}! Use the buttons below to interact with the bot.',
                reply_markup=keyboard
            )
        
        # Log the start command
        await log_command(session, user or new_user, "start")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses and messages"""
    async with async_session() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = user.scalar_one_or_none()
        
        if not user:
            await update.message.reply_text("Please use /start first to register.")
            return
            
        # Log the button press
        await log_command(session, user, f"button_{update.message.text}")
        
        if update.message.text == "❓ Help":
            if user.role == UserRole.ADMIN:
                help_text = """
Available commands:
👥 List Users - View all registered users
🔔 Toggle Notifications - Enable/disable notifications for a user
🔄 Toggle User - Enable/disable a user account
❌ Remove User - Remove a user from the system
⭐ Promote User - Promote a user to admin
❓ Help - Show this help message
                """
            else:
                help_text = """
Available commands:
📊 Status - Check your notification status
❓ Help - Show this help message
                """
            await update.message.reply_text(help_text)
            
        elif update.message.text == "👥 List Users" and user.role == UserRole.ADMIN:
            users = await session.execute(select(User))
            users = users.scalars().all()
            
            response = "👥 Users:\n\n"
            for u in users:
                status = "✅ active" if u.is_active else "❌ disabled"
                notifications = "🔔 enabled" if u.notifications_enabled else "🔕 disabled"
                role = "⭐ admin" if u.role == UserRole.ADMIN else "👤 user"
                response += f"@{u.username} (ID: {u.telegram_id})\n"
                response += f"Status: {status}, Notifications: {notifications}, Role: {role}\n\n"
                
            await update.message.reply_text(response)
            
        elif update.message.text == "📊 Status":
            status = "enabled" if user.notifications_enabled else "disabled"
            response = f"📊 Your Status:\n\n"
            response += f"Notifications: {'🔔 ' + status if user.notifications_enabled else '🔕 ' + status}\n"
            response += f"Account: {'✅ active' if user.is_active else '❌ disabled'}\n"
            response += f"Role: {'⭐ admin' if user.role == UserRole.ADMIN else '👤 user'}"
            
            await update.message.reply_text(response)
            
        elif update.message.text in ["🔔 Toggle Notifications", "🔄 Toggle User", "❌ Remove User", "⭐ Promote User"] and user.role == UserRole.ADMIN:
            await update.message.reply_text(
                "Please use the corresponding command with a user ID:\n\n"
                "🔔 /toggle_notifications <user_id>\n"
                "🔄 /toggle_user <user_id>\n"
                "❌ /remove_user <user_id>\n"
                "⭐ /promote <user_id>"
            )

async def toggle_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle notifications for a user (admin only)."""
    async with async_session() as session:
        admin = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        admin = admin.scalar_one_or_none()
        
        if not admin or admin.role != UserRole.ADMIN:
            await update.message.reply_text("Sorry, this command is for admins only.")
            return
            
        if not context.args:
            await update.message.reply_text("Please provide a user ID. Usage: /toggle_notifications <user_id>")
            return
            
        try:
            user_id = int(context.args[0])
            user = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user.scalar_one_or_none()
            
            if not user:
                await update.message.reply_text("User not found.")
                return
                
            user.notifications_enabled = not user.notifications_enabled
            await session.commit()
            
            status = "enabled" if user.notifications_enabled else "disabled"
            await update.message.reply_text(f"Notifications for user {user.username} have been {status}.")
            
            # Log the toggle_notifications command with the target user
            await log_command(session, admin, "toggle_notifications", [str(user_id)])
            
        except ValueError:
            await update.message.reply_text("Invalid user ID. Please provide a valid number.")
            # Log the failed attempt
            await log_command(session, admin, "toggle_notifications", ["invalid_id"])

async def toggle_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle user account status (admin only)."""
    async with async_session() as session:
        admin = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        admin = admin.scalar_one_or_none()
        
        if not admin or admin.role != UserRole.ADMIN:
            await update.message.reply_text("Sorry, this command is for admins only.")
            return
            
        if not context.args:
            await update.message.reply_text("Please provide a user ID. Usage: /toggle_user <user_id>")
            return
            
        try:
            user_id = int(context.args[0])
            user = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user.scalar_one_or_none()
            
            if not user:
                await update.message.reply_text("User not found.")
                return
                
            user.is_active = not user.is_active
            await session.commit()
            
            status = "enabled" if user.is_active else "disabled"
            await update.message.reply_text(f"User {user.username} has been {status}.")
            
            # Log the toggle_user command
            await log_command(session, admin, "toggle_user", [str(user_id)])
            
        except ValueError:
            await update.message.reply_text("Invalid user ID. Please provide a valid number.")
            # Log the failed attempt
            await log_command(session, admin, "toggle_user", ["invalid_id"])

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a user (admin only)."""
    async with async_session() as session:
        admin = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        admin = admin.scalar_one_or_none()
        
        if not admin or admin.role != UserRole.ADMIN:
            await update.message.reply_text("Sorry, this command is for admins only.")
            return
            
        if not context.args:
            await update.message.reply_text("Please provide a user ID. Usage: /remove_user <user_id>")
            return
            
        try:
            user_id = int(context.args[0])
            user = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user.scalar_one_or_none()
            
            if not user:
                await update.message.reply_text("User not found.")
                return
                
            if user.role == UserRole.ADMIN:
                await update.message.reply_text("Cannot remove an admin user.")
                return
                
            await session.delete(user)
            await session.commit()
            
            await update.message.reply_text(f"User {user.username} has been removed.")
            
            # Log the remove_user command
            await log_command(session, admin, "remove_user", [str(user_id)])
            
        except ValueError:
            await update.message.reply_text("Invalid user ID. Please provide a valid number.")
            # Log the failed attempt
            await log_command(session, admin, "remove_user", ["invalid_id"])

async def promote_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Promote a user to admin (admin only)."""
    async with async_session() as session:
        admin = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        admin = admin.scalar_one_or_none()
        
        if not admin or admin.role != UserRole.ADMIN:
            await update.message.reply_text("Sorry, this command is for admins only.")
            return
            
        if not context.args:
            await update.message.reply_text("Please provide a user ID. Usage: /promote <user_id>")
            return
            
        try:
            user_id = int(context.args[0])
            user = await session.execute(select(User).where(User.telegram_id == user_id))
            user = user.scalar_one_or_none()
            
            if not user:
                await update.message.reply_text("User not found.")
                return
                
            if user.role == UserRole.ADMIN:
                await update.message.reply_text("This user is already an admin.")
                return
                
            user.role = UserRole.ADMIN
            await session.commit()
            
            # Log the promotion
            activity_log = UserActivityLog(
                user_id=user.id,
                action="promotion",
                details=f"User promoted to admin by {admin.username}",
                user_agent=admin.username
            )
            session.add(activity_log)
            await session.commit()
            
            await update.message.reply_text(f"User {user.username} has been promoted to admin.")
            
            # Log the promote command
            await log_command(session, admin, "promote", [str(user_id)])
            
        except ValueError:
            await update.message.reply_text("Invalid user ID. Please provide a valid number.")
            # Log the failed attempt
            await log_command(session, admin, "promote", ["invalid_id"])

def main():
    """Start the bot."""
    # Create the Application and pass it your bot's token
    application = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("toggle_notifications", toggle_notifications))
    application.add_handler(CommandHandler("toggle_user", toggle_user))
    application.add_handler(CommandHandler("remove_user", remove_user))
    application.add_handler(CommandHandler("promote", promote_user))
    
    # Add message handler for buttons
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 