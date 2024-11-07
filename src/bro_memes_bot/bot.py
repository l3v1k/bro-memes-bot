import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, Chat, constants
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from .utils.url_validator import URLValidator, MediaService
from .utils.downloader import MediaDownloader

# Load environment variables from project root
env_path = Path(__file__).parents[2] / '.env'
load_dotenv(env_path)
TOKEN = os.getenv('BOT_TOKEN')

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize downloader
downloader = MediaDownloader()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    # Only respond to /start in private chats
    if update.message.chat.type != Chat.PRIVATE:
        return
        
    await update.message.reply_text(
        "👋 Hi! I can help you download content from social media.\n\n"
        "Just send me a link from:\n"
        "• Instagram Reels\n"
        "• TikTok Videos\n" 
        "• YouTube Shorts\n"
        "• Twitter Media\n\n"
        "And I'll send the media back to you!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    # Only respond to /help in private chats
    if update.message.chat.type != Chat.PRIVATE:
        return
        
    await update.message.reply_text(
        "Just send me a social media link and I'll download it for you!\n\n"
        "Supported platforms:\n"
        "• Instagram Reels\n"
        "• TikTok Videos\n"
        "• YouTube Shorts\n"
        "• Twitter Media"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages."""
    message_text = update.message.text
    chat_id = update.message.chat_id
    
    # Quick check if message contains any supported URL
    is_valid, service = URLValidator.validate_url(message_text)
    
    # If not a valid media URL, only respond in private chats
    if not is_valid:
        if update.message.chat.type == Chat.PRIVATE:
            await update.message.reply_text(
                "❌ Please send a valid link from supported platforms:\n"
                "• Instagram Reels\n"
                "• TikTok Videos\n"
                "• YouTube Shorts\n"
                "• Twitter Media"
            )
        return
        
    try:
        # Show typing action while processing
        await context.bot.send_chat_action(
            chat_id=chat_id, 
            action=constants.ChatAction.TYPING
        )
        
        if service == MediaService.TWITTER:
            result = await downloader.download_twitter(message_text)
            
            if result:
                status_message = await update.message.reply_text("📥 Downloading Twitter media...")
            else:
                fixed_url = message_text.replace("twitter.com", "fixupx.com").replace("x.com", "fixupx.com")
                await update.message.reply_text(
                    f"No downloadable media found. Here's a better link:\n{fixed_url}"
                )
                return
        else:
            status_message = await update.message.reply_text(
                f"⏳ Processing {service.value} link..."
            )
            
            if service == MediaService.YOUTUBE:
                await status_message.edit_text("📥 Downloading YouTube video...")
                result = await downloader.download_youtube(message_text)
            elif service == MediaService.TIKTOK:
                await status_message.edit_text("📥 Downloading TikTok video...")
                result = await downloader.download_tiktok(message_text)
            elif service == MediaService.INSTAGRAM:
                await status_message.edit_text("📥 Downloading Instagram media...")
                result = await downloader.download_instagram(message_text)
            
        if not result:
            await status_message.edit_text("❌ Failed to download media")
            return
            
        await status_message.edit_text("📤 Uploading to Telegram...")
        
        # Show upload video action while uploading
        await context.bot.send_chat_action(
            chat_id=chat_id, 
            action=constants.ChatAction.UPLOAD_VIDEO
        )
        
        # Create caption
        caption = f"🎥 {result['title']}"
        if result.get('uploader'):
            caption += f"\n👤 {result['uploader']}"
        if result.get('duration'):
            try:
                duration = float(result['duration'])
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                caption += f"\n⏱ {minutes}:{seconds:02d}"
            except (TypeError, ValueError):
                pass
        
        # Send video with periodic upload status updates
        with open(result['file_path'], 'rb') as video_file:
            # Send another upload action as the previous one might have expired
            await context.bot.send_chat_action(
                chat_id=chat_id, 
                action=constants.ChatAction.UPLOAD_VIDEO
            )
            await update.message.reply_video(
                video=video_file,
                caption=caption,
                supports_streaming=True,
                write_timeout=120,
                read_timeout=60,
                connect_timeout=None
            )
        
        # Cleanup
        downloader.cleanup(result['file_path'])
        await status_message.delete()
            
    except Exception as e:
        logger.error(f"Error processing {service.value} link: {str(e)}")
        if service == MediaService.TWITTER:
            fixed_url = message_text.replace("twitter.com", "fixupx.com").replace("x.com", "fixupx.com")
            await update.message.reply_text(
                f"❌ Couldn't download media. Here's a better link:\n{fixed_url}"
            )
        elif service == MediaService.INSTAGRAM and "login required" in str(e).lower():
            await status_message.edit_text(
                "❌ Instagram login required.\n"
                "Please contact bot administrator to configure Instagram authentication."
            )
        else:
            await status_message.edit_text(
                f"❌ Error processing {service.value} link.\n"
                f"Error: {str(e)}"
            )

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TOKEN).build()

    # Command handlers - only respond in private chats
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Message handler - process all text messages but handle them differently based on chat type
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main() 