from flask import Flask, request, url_for, session, redirect, render_template
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from flask_session import Session
import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import base64  
from base64 import b64encode

app = Flask(__name__, static_folder='static')

app.config['SECRET_KEY'] = os.urandom(64)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './.flask_session/'
Session(app)

@app.route('/')
def login():
    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(scope="playlist-read-private playlist-modify-public playlist-modify-private",
                                               cache_handler=cache_handler,
                                               show_dialog=True)

    if request.args.get("code"):
        # Step 2. Being redirected from Spotify auth page
        auth_manager.get_access_token(request.args.get("code"))
        return redirect('/')

    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        # Step 1. Display sign in link when no token
        auth_url = auth_manager.get_authorize_url()
        return render_template("login.html", auth_url=auth_url)

    # Step 3. Signed in, display data
    spotify = spotipy.Spotify(auth_manager=auth_manager)
    return redirect(url_for('repeatreceipts', _external=True))

@app.route('/repeatreceipts')
def repeatreceipts():
    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return redirect('/')

    sp = spotipy.Spotify(auth_manager=auth_manager)
    
    #finds wrapped playlists
    wrappedPlaylists = searchList(scrapeLoop(sp))
    
    #links to be passed into HTML
    wrappedLinks = {
            '2022': 'w2022',
            '2021': 'w2021',
            '2020': 'w2020',
            '2019': 'w2019',
            '2018': 'w2018',
            '2017': 'w2017',
            '2016': 'w2016'
        }
    
    #if playlist is found, remove link from dictionary    
    for item in wrappedPlaylists:
        if item['name'].split(' ')[-1] in wrappedLinks:
            wrappedLinks.pop(item['name'].split(' ')[-1])
    
    #string of years because easier to pass into HTML
    years = []
    for playlist in wrappedPlaylists:
        year = playlist['name'][-4:]
        years.append(year)
        years.sort()
    years_string = ', '.join(years)
        
    #data processing
    rawdata = splitlist(cleanList(loopAllYears(wrappedPlaylists,sp)))
    
    #formatting data to get passed into HTML
    def maindata(inputdata):
        rows = []
        count = 0
        for item in inputdata:
            count+=1
            rows.append({
                'count': count,
                'image': item['image'],
                'name' : item['name'],
                'artist' : item['artist'],
                'rank': round(item['avgrank']),
                'ocurrences': len(item['years']),
                'years': (', '.join(item['years'])),
                'artistlink': item['artistlink'],
                'tracklink': item['tracklink'],
                'albumlink': item['albumlink'],

            })  
        return rows
    
    #funstats
    if not rawdata:
        return None
    else:
        artistlist=[]
        years=[]
        gapCount = 0
        gap = []
        gapYears = []
        sameRank = []
        for i in rawdata:
            artistlist.append(i['artist'])
            years.append(i['years'])
            for k in range (len(i['years'])-1):
                tempgap=(abs(int(i['years'][k])-int(i['years'][k+1])))
                if tempgap>=gapCount and tempgap > 1:
                    if tempgap>gapCount:
                        gap.clear()
                    gapCount=tempgap
                    gapYears=[(i['years'][k]),(i['years'][k+1])]
                    gaptext=[i['name'],i['artist'],gapCount,' and '.join(gapYears)]
                    gap.append(gaptext)
        favArt = max(set(artistlist),key=artistlist.count)
        favArtistCount = artistlist.count(favArt)
        favArtist = [favArt,favArtistCount]
        #most popular year
        years = [element for innerList in years for element in innerList]
        favY = max(set(years),key=years.count)
        favYearCount = years.count(favY)
        favYear = [favY,favYearCount]
        #ranked same both years
        for i in rawdata:
            if len(i['rank'])==1:
                rank_share = {'name': i['name'], 'artist': i['artist'], 'rank': i['rank'][0], 'years': ', '.join(i['years'])}
                sameRank.append(rank_share)
        funStats= {
            "topArtist": favArtist,
            "topYear": favYear,
            "sharedRank" : sameRank,
            "biggestGap": gap 
        }
    
    #share image generation
    # Create an image with the specified dimensions
    image = Image.new('RGB', (1080, 1920), color = (18, 18, 18))
    draw = ImageDraw.Draw(image, 'RGBA')
    
    #fonts
    font_path = os.path.join('static', 'fonts')
    titlefont = ImageFont.truetype(os.path.join(font_path, 'Inter-Black.ttf'), 80)
    morefont = ImageFont.truetype(os.path.join(font_path, "Inter-Bold.ttf"), 40)
    songfont = ImageFont.truetype(os.path.join(font_path, "Inter-Bold.ttf"), 40)
    artistfont = ImageFont.truetype(os.path.join(font_path, "Inter-Medium.ttf"), 32)
    yearfont = ImageFont.truetype(os.path.join(font_path, "Inter-Light.ttf"), 24)
    rankfont = ImageFont.truetype(os.path.join(font_path, "Inter-Black.ttf"), 96)
    
    # Draw constants
    draw.ellipse((389, 711, 389+1004, 711+1004), fill=(29, 185, 84, 13))
    draw.ellipse((-196, 305, -196+1052, 305+1052), fill=(29, 185, 84, 13))
    draw.ellipse((-283, 1141, -283+802, 1141+802), fill=(29, 185, 84, 13))
    draw.text((126,190), "Repeat Beats", font=titlefont, fill=(29,185,84))
    draw.text((444,1813), "repeatreceipts.onrender.com", font=songfont, fill=(29,185,84, 196))
    # loop through relavent image data
    pos=0
    for i in range (0,5):
        #get image from rawdata
        response=requests.get(rawdata[i]['image'])
        #resize
        albumart=(Image.open(BytesIO(response.content)).resize((210,210)))
        #y positioning
        ypos = 384+(pos*265)
        #paste image into canvas
        image.paste(albumart,(226,ypos))
        #text
        #song title
        songtitle=rawdata[i]['name']
        songtitle = (songtitle[:20] + '...') if len(songtitle) > 20 else songtitle
        draw.text((478,ypos+49), songtitle, font=songfont, fill=(255,255,255))
        #song artist
        draw.text((478,ypos+105), rawdata[i]['artist'], font=artistfont, fill=(255,255,255))
        #song year
        draw.text((478,ypos+157), (', '.join(rawdata[i]['years'])), font=yearfont, fill=(255,255,255))
        #song rank
        draw.text((120,ypos+47), f"{i+1}", font=rankfont, fill=(255,255,255))
        #increment positioning
        pos+=1
    #Wites plus ## more...
    moresongs = (len(rawdata)-5)
    draw.text((116,1709), f"Plus {moresongs} more...", font=morefont, fill=(179,179,179))
    # Save the image
    image_io = BytesIO()
    image.save(image_io, 'PNG')
    dataurl = 'data:image/png;base64,' + b64encode(image_io.getvalue()).decode('ascii')

    
    #stops HTML conditions from breaking
    if rawdata:
        inputrows = maindata(rawdata)
    else:
        inputrows=None
        
    return render_template("index.html", rows=inputrows, funStats=funStats, years_string=years_string, wrappedPlaylists=wrappedPlaylists,wrappedLinks=wrappedLinks, shareimage=dataurl)


@app.route('/makeplaylist')
def makeplaylist():
    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return redirect('/')

    sp = spotipy.Spotify(auth_manager=auth_manager)
    
    wrappedPlaylists = searchList(scrapeLoop(sp))
    rawdata = splitlist(cleanList(loopAllYears(wrappedPlaylists,sp)))
    
    #list of song IDS
    songlist=[]
    for i in rawdata:
        songlist.append("spotify:track:"+i['id'])
    splitsonglist= list(divide_chunks(songlist, 100))
    
    results = (sp.user_playlist_create(sp.current_user()["id"], "Repeat Beats", public=False, collaborative=False, description="The songs you've loved for multiple years."))
    for i in splitsonglist:
        sp.user_playlist_add_tracks(sp.current_user()["id"], results['id'], i)
    return results['external_urls']['spotify']

@app.route('/w2022')
def w2022():
    return redirect('https://open.spotify.com/genre/0JQ5DAwD41iRZZRVB8exON')

@app.route('/w2021')
def w2021():
    return redirect('https://open.spotify.com/genre/2021-page')

@app.route('/w2020')
def w2020():
    return redirect('https://open.spotify.com/genre/2020-page')

@app.route('/w2019')
def w2019():
    return redirect('https://open.spotify.com/genre/2019-page')

@app.route('/w2018')
def w2018():
    return redirect('https://open.spotify.com/genre/2018-page')

@app.route('/w2017')
def w2017():
    return redirect('https://open.spotify.com/genre/2017-page')

@app.route('/w2016')
def w2016():
    return redirect('https://open.spotify.com/genre/2016-page')

#scrapes playlist names and IDs
def nameScraper(json):
    templist=[]
    for i in json['items']:
        tempdict={
        "name": i['name'],
        "id": i['id'],
        }
        templist.append(tempdict)
    return templist

#loops through nameScraper because of 50 offset limit
def scrapeLoop(sp):
    playlistlist=[]
    os=0
    run=True
    while(run):
        capture = nameScraper(sp.user_playlists((sp.me()["id"]),limit=50, offset=os))
        if capture ==[]:
            run=False
        else:
            playlistlist.extend(nameScraper(sp.user_playlists((sp.me()["id"]),limit=50, offset=os)))
            os+=50
    return playlistlist

#searches all user playlists for Your Top Songs Playlists
def searchList(json):
    yourTopList = [
        {"name": i["name"], "id": i["id"]}
        for i in json
        if "Your Top Songs 20" in i["name"]
    ]
    return yourTopList

# dont remember
def loopAllYears(json,sp):
    masterList = []
    parsedPlaylists=[]
    for i in json:
        parsedPlaylists.append(playlistParser(i['name'],sp.playlist_tracks(i['id'])))

    for i in parsedPlaylists:
        for j in parsedPlaylists:
            masterList.append(playlistCompare(i, j))
    return masterList

#returns only data that I care about
def playlistParser(name, json):
    templist=[]
    count = 1
    for i in json['items']:
        if i.get("track").get("album").get('images'):
                image = i.get("track").get("album").get('images')[1].get('url')
        else:
            image = "https://media.wired.com/photos/5a0201b14834c514857a7ed7/master/pass/1217-WI-APHIST-01.jpg"

        tempdict={
        "name": i['track']['name'],
        "id": i['track']['id'],
        "artist": i['track']['artists'][0]['name'],
        "years": [],
        "rank" : [count],
        "avgrank" : [],
        "image" : image,
        "artistlink": i['track']['artists'][0]['external_urls']['spotify'],
        "albumlink": i['track']['album']['external_urls']['spotify'],
        "tracklink": i['track']['external_urls']['spotify']
        }
        templist.append(tempdict)
        count+=1
    playlistDic={
        "name":name,
        'tracks': templist
    }
    return playlistDic

#compares two songs to see if the same
def playlistCompare(dic1, dic2):
    tempList=[]
    year1=((dic1['name']).split('Your Top Songs ')[1])
    year2=((dic2['name']).split('Your Top Songs ')[1])
    if dic1['tracks']==dic2['tracks']:
        return None
    else:
        for i in dic1['tracks']:
            for j in dic2['tracks']:
                if i['name'] == j['name'] and (i['artist'] == j['artist']):
                    i["years"].append(year1)
                    i["years"].append(year2)
                    i["rank"].append((j['rank'][0]))
                    tempList.append(i)
    return tempList

#cleans messy data up into usable data
def cleanList(thislist):
    #remove None
    cleanlist = list(filter(lambda item: item is not None, thislist))
    #removes sublists
    cleanlist = [element for innerList in cleanlist for element in innerList]
    # sort years within dicts
    for i in cleanlist:
        i['years'].sort()
        i['rank'].sort()
    #remove duplicates
    cleanerlist = []
    [cleanerlist.append(x) for x in cleanlist if x not in cleanerlist]  
    cleanlist = sorted(cleanerlist, key=lambda d: d['name'])
    #append years together
    for i in cleanlist:
        for j in cleanlist:
            if i['name']==j['name']:
                if i['years']!=j['years']:
                    i['years'].extend(j['years'])
            if i['name']==j['name']:
                if i['rank']!=j['rank']:
                    i['rank'].extend(j['rank'])
    #remove duplicate years and sort  
    for i in cleanlist:
        i['years'] = [*set(i['years'])]
        i['years'].sort()
        i['rank'] = [*set(i['rank'])]
        i['rank'].sort()
    cleanerlist = []
    [cleanerlist.append(x) for x in cleanlist if x not in cleanerlist]
    for i in cleanerlist:
        for j in cleanerlist:
            if i['name']==j['name']:
                if i['id']!=j['id']:
                    cleanerlist.remove(j)
    for i in cleanerlist:
        i['avgrank']= (sum(i['rank'])/len(i['rank']))
    return cleanerlist

#splits into how often it ocurrs, helpful for ranking
def splitlist(thislist):
    maxyears=0
    for i in thislist:
        if (len(i['years']))>maxyears:
            maxyears=(len(i['years']))
    rankedlist=[]
    for j in range((maxyears), 1, -1):
        templist=[]
        for i in thislist:
            if len(i['years'])==j:
                templist.append(i)
        rankedlist.append(templist)
    
    for i in rankedlist:
        selectionSort(i, len(i))
    cleanlist = [element for innerList in rankedlist for element in innerList]
    return cleanlist

#sorting
def selectionSort(array, size):
    for ind in range(size):
        min_index = ind
        for j in range(ind + 1, size):
            # select the minimum element in every iteration
            if (array[j]['avgrank']) < (array[min_index]['avgrank']):
                min_index = j
         # swapping the elements to sort the array
        (array[ind], array[min_index]) = (array[min_index], array[ind])
        

def divide_chunks(l, n):
    # looping till length l
    for i in range(0, len(l), n):
        yield l[i:i + n]


if __name__ == '__main__':
    app.run(threaded=True, port=int(os.environ.get("PORT",
                                                   os.environ.get("SPOTIPY_REDIRECT_URI", 8080).split(":")[-1])))