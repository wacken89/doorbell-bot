import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text('Hi! I am a photo sending bot. Use /send_photo to send a photo.')

async def send_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a photo to the chat."""
    try:
        # You can replace this with your photo path
        photo_path = "path/to/your/photo.jpg"
        
        if os.path.exists(photo_path):
            with open(photo_path, 'rb') as photo:
                await update.message.reply_photo(photo=photo)
        else:
            await update.message.reply_text("Sorry, the photo file was not found.")
    except Exception as e:
        logger.error(f"Error sending photo: {e}")
        await update.message.reply_text("Sorry, there was an error sending the photo.")

def main():
    """Start the bot."""
    # Create the Application and pass it your bot's token
    application = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("send_photo", send_photo))

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 