import aiohttp

async def fetch_anime_by_title(title):
    """
    Queries AniList for the anime's exact metadata and extra-large cover image.
    """
    query = '''
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        title { english romaji }
        description(asHtml: false)
        coverImage { extraLarge }
        genres
        episodes
        status
      }
    }
    '''
    variables = {"search": title}
    url = 'https://graphql.anilist.co'
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={'query': query, 'variables': variables}) as response:
            if response.status != 200:
                print(f"[-] AniList API Error: {response.status}")
                return None
            data = await response.json()
            
    if 'errors' in data or not data['data']['Media']:
        print(f"[-] No AniList data found for: {title}")
        return None
        
    media = data['data']['Media']
    
    # Clean up the HTML tags sometimes left in AniList descriptions
    synopsis = media['description'] or "No synopsis available."
    synopsis = synopsis.replace('<br>', '\n').replace('<i>', '').replace('</i>', '')
    
    return {
        'title': media['title']['english'] or media['title']['romaji'],
        'poster_url': media['coverImage']['extraLarge'],
        'genres': media['genres'],
        'synopsis': synopsis,
        'episodes': media['episodes'] or "Ongoing",
        'status': media['status']
    }
