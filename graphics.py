import os, aiohttp, textwrap, urllib.request, asyncio, re
from PIL import Image, ImageDraw, ImageFont

THUMB_DIR = './downloads/thumbnails'
if not os.path.exists(THUMB_DIR): os.makedirs(THUMB_DIR)

TEMPLATE_PATH = f"{THUMB_DIR}/template.png" 
FONT_BOLD = os.path.join(os.path.dirname(__file__), "Montserrat-Black.ttf")

if not os.path.exists(FONT_BOLD):
    try: urllib.request.urlretrieve("https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Black.ttf", FONT_BOLD)
    except: pass

def clean_html(raw_html):
    if not raw_html: return "No synopsis available."
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html).replace('\n', ' ').strip()

async def fetch_anime_by_title(search_title):
    query = '''
    query ($search: String) {
      Media (search: $search, type: ANIME) {
        title { english romaji }
        description(asHtml: false)
        genres episodes status format averageScore duration
        startDate { year month day }
        endDate { year month day }
        coverImage { extraLarge large }
      }
    }
    '''
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post('https://graphql.anilist.co', json={'query': query, 'variables': {'search': search_title}}, timeout=10) as resp:
                data = await resp.json()
                if data and 'data' in data and data['data']['Media']:
                    anime = data['data']['Media']
                    start = f"{anime['startDate'].get('year', '')}-{anime['startDate'].get('month', '')}-{anime['startDate'].get('day', '')}" if anime.get('startDate') and anime['startDate'].get('year') else "N/A"
                    end = f"{anime['endDate'].get('year', '')}-{anime['endDate'].get('month', '')}-{anime['endDate'].get('day', '')}" if anime.get('endDate') and anime['endDate'].get('year') else "N/A"
                    return {
                        'title': anime['title'].get('english') or anime['title'].get('romaji') or search_title,
                        'poster_url': anime['coverImage'].get('extraLarge') or anime['coverImage'].get('large'),
                        'genres': anime.get('genres', []),
                        'synopsis': clean_html(anime.get('description')),
                        'episodes': anime.get('episodes') or "Ongoing",
                        'status': anime.get('status', 'ONGOING'),
                        'format': anime.get('format', 'TV'),
                        'rating': f"{anime.get('averageScore')}%" if anime.get('averageScore') else "N/A",
                        'duration': anime.get('duration', 'N/A'),
                        'start_date': start,
                        'end_date': end
                    }
        except Exception as e:
            print(f"⚠️ AniList Error: {e}")
    return None

async def download_image(url, filename):
    if not url: return None
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                with open(filename, 'wb') as f: f.write(await resp.read())
                return filename
    return None

def get_dominant_color(image):
    tiny_img = image.resize((1, 1), resample=Image.Resampling.LANCZOS)
    dominant_color = tiny_img.getpixel((0, 0))
    return dominant_color[:3] if len(dominant_color) == 4 else dominant_color

def build_custom_thumbnail(poster_path, title, genres, synopsis, episodes, output_path):
    bg_color = (246, 184, 173) 
    poster = None
    if os.path.exists(poster_path):
        poster = Image.open(poster_path).convert("RGBA")
        raw_color = get_dominant_color(poster)
        bg_color = tuple(min(255, int(c * 1.3)) for c in raw_color) 

    img = Image.new('RGBA', (1280, 720), color=bg_color)
    if poster:
        tw, th = 444, 628
        poster = poster.resize((tw, th), Image.Resampling.LANCZOS)
        mask = Image.new("L", (tw, th), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle((0, 0, tw, th), radius=20, fill=255)
        img.paste(poster, (815, 53), mask)

    if os.path.exists(TEMPLATE_PATH):
        template = Image.open(TEMPLATE_PATH).convert("RGBA").resize((1280, 720))
        img.paste(template, (0, 0), template)

    draw = ImageDraw.Draw(img)
    try:
        font_t = ImageFont.truetype(FONT_BOLD, 30)
        font_s = ImageFont.truetype(FONT_BOLD, 6) 
        font_e = ImageFont.truetype(FONT_BOLD, 60)
        font_g = ImageFont.truetype(FONT_BOLD, 15)
    except: font_t = font_s = font_e = font_g = ImageFont.load_default()

    draw.text((89, 266), textwrap.fill(title, width=45), font=font_t, fill=(0, 0, 0))
    g_coords = [(100, 620), (100, 649), (100, 678)]
    for i, g in enumerate(genres[:3]): draw.text(g_coords[i], g, font=font_g, fill=(255, 255, 255))
    draw.text((321, 621), textwrap.fill(synopsis, width=60)[:400] + "...", font=font_s, fill=(255, 255, 255))
    draw.text((655, 615), str(episodes), font=font_e, fill=(255, 255, 255))

    img.convert('RGB').save(output_path, quality=95)
    return output_path

async def create_thumbnail(poster_url, title, genres, synopsis, episodes):
    if not poster_url: return None
    clean_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
    raw_poster = f"{THUMB_DIR}/raw_{clean_title}.jpg"
    final_thumb = f"{THUMB_DIR}/thumb_{clean_title}.jpg"
    if not await download_image(poster_url, raw_poster): return None
    await asyncio.get_running_loop().run_in_executor(None, build_custom_thumbnail, raw_poster, title, genres, synopsis, episodes, final_thumb)
    if os.path.exists(raw_poster): os.remove(raw_poster)
    return final_thumb

# Legacy Fallbacks
async def fetch_poster_bytes(*args, **kwargs): return None
def generate_thumbnail(*args, **kwargs): return None
