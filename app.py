from flask import Flask, request, url_for, session, redirect, render_template
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
import os

app = Flask(__name__, static_folder='static')

app.secret_key = os.getenv("appsecret")
app.config['SESSION_COOKIE_NAME'] = "Session Cookie"

@app.route('/')
def login():
    session.clear()
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    print(auth_url)
    return redirect(auth_url)

@app.route('/authorize')
def authorize():
    session.clear()
    sp_oauth = create_spotify_oauth()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session["token_info"] = token_info
    return redirect(url_for('wrappedRepeats', _external=True))

@app.route('/wrappedRepeats')
def wrappedRepeats():
    session['token_info'], authorized = get_token()
    session.modified = True
    
    if not authorized:
        return redirect('/')
    
    sp = spotipy.Spotify(auth=session.get('token_info').get('access_token'))
    wrappedPlaylists = searchList(scrapeLoop(sp))
    
    wrappedLinks = {
            'Your Top Songs 2022': 'w2022',
            'Your Top Songs 2021': 'w2021',
            'Your Top Songs 2020': 'w2020',
            'Your Top Songs 2019': 'w2019',
            'Your Top Songs 2018': 'w2018',
            'Your Top Songs 2017': 'w2017'
        }
        
    for item in wrappedPlaylists:
        if item['name'] in wrappedLinks:
            wrappedLinks.pop(item['name'])
    
    years = []
    for playlist in wrappedPlaylists:
        year = playlist['name'][-4:]
        years.append(year)
        
    years_string = ', '.join(years)
    
    if len(wrappedPlaylists) <= 1:
        
        return render_template("notenough.html", wrappedPlaylists=wrappedPlaylists,wrappedLinks=wrappedLinks, years_string=years_string)
    
    else:
        global rawdata
        rawdata = splitlist(cleanList(loopAllYears(wrappedPlaylists,sp)))
        
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
                    'years': (', '.join(item['years']))
                })  
            return rows
        
        return render_template("base.html", rows=maindata(rawdata), funStats=funStats(rawdata), years_string=years_string)


@app.route('/makeplaylist')
def makeplaylist():
    session['token_info'], authorized = get_token()
    session.modified = True
    
    if not authorized:
        return redirect('/')
    
    sp = spotipy.Spotify(auth=session.get('token_info').get('access_token'))
    userid = sp.me()["id"]
    songlist=[]
    for i in rawdata:
        songlist.append("spotify:track:"+i['id'])
    playlistid = ((sp.user_playlist_create(userid, "Wrapped Repeats", public=True, collaborative=False, description="The songs you've loved for multiple years."))['id'])
    sp.user_playlist_add_tracks(userid, playlistid, songlist)
    return "Playlist generated!"

@app.route('/followmore')
def followmore():
    session['token_info'], authorized = get_token()
    session.modified = True
    
    if not authorized:
        return redirect('/')
    
    sp = spotipy.Spotify(auth=session.get('token_info').get('access_token'))
    
    wrappedPlaylists = searchList(scrapeLoop(sp))
    
    wrappedLinks = {
            'Your Top Songs 2022': 'w2022',
            'Your Top Songs 2021': 'w2021',
            'Your Top Songs 2020': 'w2020',
            'Your Top Songs 2019': 'w2019',
            'Your Top Songs 2018': 'w2018',
            'Your Top Songs 2017': 'w2017'
        }
        
    for item in wrappedPlaylists:
        if item['name'] in wrappedLinks:
            wrappedLinks.pop(item['name'])
    
    years = []
    for playlist in wrappedPlaylists:
        year = playlist['name'][-4:]
        years.append(year)
        
    years_string = ', '.join(years)
    
    return render_template("notenough.html", wrappedPlaylists=wrappedPlaylists,wrappedLinks=wrappedLinks, years_string=years_string)

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

def get_token():
    token_valid = False
    token_info = session.get("token_info", {})

    # Checking if the session already has a token stored
    if not (session.get('token_info', False)):
        token_valid = False
        return token_info, token_valid

    # Checking if token has expired
    now = int(time.time())
    is_token_expired = session.get('token_info').get('expires_at') - now < 60

    # Refreshing token if it has expired
    if (is_token_expired):
        sp_oauth = create_spotify_oauth()
        token_info = sp_oauth.refresh_access_token(session.get('token_info').get('refresh_token'))

    token_valid = True
    return token_info, token_valid

def create_spotify_oauth():
    return SpotifyOAuth(
        client_id=os.getenv("clientid"),
        client_secret=os.getenv("clientsecret"),
        redirect_uri=url_for('authorize', _external=True),
        scope="playlist-read-private playlist-modify-public playlist-modify-private")

def nameScraper(json):
    templist=[]
    for i in json['items']:
        tempdict={
        "name": i['name'],
        "id": i['id'],
        }
        templist.append(tempdict)
    return templist

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

def searchList(json):
    yourTopList=[]
    for i in json:
        if "Your Top Songs 20" in i['name']:
            tempdict={
            "name": i['name'],
            "id": i['id'],
            }
            yourTopList.append(tempdict)
    return yourTopList

def loopAllYears(json,sp):
    masterList = []
    parsedPlaylists=[]
    for i in json:
        parsedPlaylists.append(playlistParser(i['name'],sp.playlist_tracks(i['id'])))
    
    for i in parsedPlaylists:
        for j in parsedPlaylists:
            masterList.append(playlistCompare(i, j))
    return masterList

def playlistParser(name, json):
    templist=[]
    count = 1
    for i in json['items']:
        if i.get("track").get("album").get('images'):
            image = i.get("track").get("album").get('images')[2].get('url')
        else:
            image = "https://media.wired.com/photos/5a0201b14834c514857a7ed7/master/pass/1217-WI-APHIST-01.jpg"
        
        tempdict={
        "name": i['track']['name'],
        "id": i['track']['id'],
        "artist": i['track']['artists'][0]['name'],
        "years": [],
        "rank" : [count],
        "avgrank" : [],
        "image" : image
        }
        templist.append(tempdict)
        count+=1
    playlistDic={
        "name":name,
        'tracks': templist
    }
    return playlistDic

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

def selectionSort(array, size):
    for ind in range(size):
        min_index = ind
        for j in range(ind + 1, size):
            # select the minimum element in every iteration
            if (array[j]['avgrank']) < (array[min_index]['avgrank']):
                min_index = j
         # swapping the elements to sort the array
        (array[ind], array[min_index]) = (array[min_index], array[ind])
        
def funStats(inlist):
    #most popular artist
    artistlist=[]
    years=[]
    gapCount = 0
    gap = {}
    gapYears = []
    sameRank = []
    for i in inlist:
        artistlist.append(i['artist'])
        years.append(i['years'])
        for k in range (len(i['years'])-1):
            tempgap=(abs(int(i['years'][k])-int(i['years'][k+1])))
            if tempgap>gapCount:
                gap = i
                gapCount=tempgap
                gapYears=[(i['years'][k]),(i['years'][k+1])]
    favArt = max(set(artistlist),key=artistlist.count)
    favArtistCount = artistlist.count(favArt)
    favArtist = [favArt,favArtistCount]
    #most popular year
    years = [element for innerList in years for element in innerList]
    favY = max(set(years),key=years.count)
    favYearCount = years.count(favY)
    favYear = [favY,favYearCount]
    #ranked same both years
    for i in inlist:
        if len(i['rank'])==1:
            rank_share = {'name': i['name'], 'artist': i['artist'], 'rank': i['rank'][0], 'years': ', '.join(i['years'])}
            sameRank.append(rank_share)
    bigGap=[gap['name'],gap['artist'],gapCount,' and '.join(gapYears)]
    funstats= {
        "topArtist": favArtist,
        "topYear": favYear,
        "sharedRank" : sameRank,
        "biggestGap": bigGap 
    }
    return funstats
     
if __name__ == '__main__':
    app.run()