#(©) Zyric Network
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class AnimeUI:
    @staticmethod
    def generate_release_post(title, status, season, episode, audio, qualities, payloads_dict, force_sub_channel="@AdultxVerse"):
        """
        TYPE A: Episode Release Post
        payloads_dict maps quality to the CodeXBotz Base64 string (e.g., {'720p': 'Z2V0LTEyMzQ1'})
        """
        qualities_str = ", ".join([f"{q}" for q in qualities])
        
        # Matches your exact requested aesthetic
        caption = (
            f"<b>✦ {title}</b>\n\n"
            f"<b>✦ Status :</b> {status}\n"
            f"<b>✦ Season :</b> {season}\n"
            f"<b>✦ Episode :</b> {episode}\n"
            f"<b>✦ Audio :</b> {audio}\n"
            f"<b>✦ Quality :</b> {qualities_str}\n"
            f"➖➖➖➖➖➖➖➖➖➖➖➖\n"
            f"✨ <b>Powered By :</b> {force_sub_channel}"
        )
        
        # Generate inline keyboard dynamically
        buttons = []
        row = []
        for q in qualities:
            if q in payloads_dict:
                # CodeXBotz deep-link format
                bot_link = f"https://t.me/YourBotUsername?start={payloads_dict[q]}" 
                row.append(InlineKeyboardButton(f"{q} ↗️", url=bot_link))
                
                # Keep 2 buttons per row max
                if len(row) == 2:
                    buttons.append(row)
                    row = []
        if row: 
            buttons.append(row)

        return caption, InlineKeyboardMarkup(buttons)

    @staticmethod
    def generate_file_caption(file_name, file_size):
        """
        TYPE B: Automated File Upload & Deletion System Notice
        """
        caption = (
            f"📁 <b>{file_name}</b>\n"
            f"💾 <b>Size:</b> {file_size}\n\n"
            f"<blockquote>⚠️ This File is deleting automatically in 10 minutes. "
            f"Forward in your Saved Messages..! ❞</blockquote>"
        )
        return caption

    @staticmethod
    def generate_info_card(meta_data):
        """
        TYPE C: Anime Information Card
        Accepts the dictionary returned by your existing Image.py (fetch_anime_by_title)
        """
        genres_str = ", ".join(meta_data.get('genres', []))
        
        caption = (
            f"<b>✦ Genres :</b> {genres_str}\n"
            f"<b>✦ Type :</b> {meta_data.get('format', 'TV')}\n"
            f"<b>✦ Average Rating :</b> {meta_data.get('rating', 'N/A')}\n"
            f"<b>✦ Status :</b> {meta_data.get('status', 'ONGOING')}\n"
            f"<b>✦ First aired :</b> {meta_data.get('start_date', 'N/A')}\n\n"
            f"<blockquote><b>✦ Synopsis :</b> {meta_data.get('synopsis', 'No synopsis available.')}</blockquote>"
        )
        return caption
