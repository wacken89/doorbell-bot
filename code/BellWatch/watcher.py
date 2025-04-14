import os
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from telegram import Bot
from sqlalchemy import select
import asyncio
from dotenv import load_dotenv

from database.database import async_session
from database.models import User, NotificationLog

load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class PhotoHandler(FileSystemEventHandler):
    def __init__(self, watch_path):
        self.watch_path = watch_path
        self.bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
        
    async def send_photo_to_users(self, photo_path):
        """Send photo to all active users with enabled notifications."""
        async with async_session() as session:
            # Get all active users with enabled notifications
            users = await session.execute(
                select(User).where(
                    User.is_active == True,
                    User.notifications_enabled == True
                )
            )
            users = users.scalars().all()
            
            for user in users:
                try:
                    # Send photo
                    with open(photo_path, 'rb') as photo:
                        await self.bot.send_photo(
                            chat_id=user.telegram_id,
                            photo=photo,
                            caption="New doorbell photo!"
                        )
                    
                    # Log successful notification
                    log = NotificationLog(
                        user_id=user.id,
                        photo_path=photo_path,
                        status="success"
                    )
                    session.add(log)
                    
                except Exception as e:
                    logger.error(f"Error sending photo to user {user.username}: {e}")
                    # Log failed notification
                    log = NotificationLog(
                        user_id=user.id,
                        photo_path=photo_path,
                        status="failed",
                        error_message=str(e)
                    )
                    session.add(log)
            
            await session.commit()

    def on_created(self, event):
        if event.is_directory:
            return
            
        # Check if the file is an image
        if event.src_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            logger.info(f"New photo detected: {event.src_path}")
            
            # Wait a bit to ensure the file is completely written
            time.sleep(1)
            
            # Send photo to users
            asyncio.run(self.send_photo_to_users(event.src_path))

def main():
    """Start the file system watcher."""
    watch_path = os.getenv('WATCH_PATH', '/path/to/your/photos')
    
    if not os.path.exists(watch_path):
        os.makedirs(watch_path)
        logger.info(f"Created watch directory: {watch_path}")
    
    event_handler = PhotoHandler(watch_path)
    observer = Observer()
    observer.schedule(event_handler, watch_path, recursive=False)
    observer.start()
    
    logger.info(f"Started watching directory: {watch_path}")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Stopped watching directory")
    
    observer.join()

if __name__ == "__main__":
    main() 