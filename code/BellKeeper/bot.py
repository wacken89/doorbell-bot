import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
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
                'Use /help to see available commands.'
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
            
            await update.message.reply_text(
                f'Welcome back {user.username}! Use /help to see available commands.'
            )
        
        # Log the start command
        await log_command(session, user or new_user, "start")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    async with async_session() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = user.scalar_one_or_none()
        
        if user and user.role == UserRole.ADMIN:
            help_text = """
Available commands:
/start - Start the bot
/help - Show this help message
/users - List all users
/toggle_notifications - Toggle notifications for a user
/toggle_user - Enable/disable a user
/remove_user - Remove a user
            """
        else:
            help_text = """
Available commands:
/start - Start the bot
/help - Show this help message
/status - Check your notification status
            """
        await update.message.reply_text(help_text)
        
        # Log the help command
        if user:
            await log_command(session, user, "help")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all users (admin only)."""
    async with async_session() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = user.scalar_one_or_none()
        
        if not user or user.role != UserRole.ADMIN:
            await update.message.reply_text("Sorry, this command is for admins only.")
            return
            
        users = await session.execute(select(User))
        users = users.scalars().all()
        
        response = "Users:\n\n"
        for u in users:
            status = "active" if u.is_active else "disabled"
            notifications = "enabled" if u.notifications_enabled else "disabled"
            response += f"@{u.username} (ID: {u.telegram_id})\n"
            response += f"Status: {status}, Notifications: {notifications}\n\n"
            
        await update.message.reply_text(response)
        
        # Log the users command
        await log_command(session, user, "users")

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

def main():
    """Start the bot."""
    # Create the Application and pass it your bot's token
    application = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("users", list_users))
    application.add_handler(CommandHandler("toggle_notifications", toggle_notifications))

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 